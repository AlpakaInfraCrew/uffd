import urllib.parse
import time
import json

from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for, flash, abort
from flask_babel import gettext as _
from sqlalchemy.exc import IntegrityError
import jwt

from uffd.secure_redirect import secure_local_redirect
from uffd.database import db
from uffd.models import (
	DeviceLoginConfirmation, OAuth2Client, OAuth2Grant, OAuth2Token, OAuth2DeviceLoginInitiation,
	host_ratelimit, format_delay, OAuth2Key,
)

def get_issuer():
	return request.host_url.rstrip('/')

OIDC_SCOPES = {
	# From https://openid.net/specs/openid-connect-core-1_0.html
	'openid': {
		# "The sub (subject) Claim MUST always be returned in the UserInfo Response."
		'sub': None,
	},
	'profile': {
		'name': None,
		'family_name': None,
		'given_name': None,
		'middle_name': None,
		'nickname': None,
		'preferred_username': None,
		'profile': None,
		'picture': None,
		'website': None,
		'gender': None,
		'birthdate': None,
		'zoneinfo': None,
		'locale': None,
		'updated_at': None,
	},
	'email': {
		'email': None,
		'email_verified': None,
	},
	# Custom scopes
	'groups': {
		'groups': None,
	},
}

OIDC_CLAIMS = {
	'sub': lambda service_user: str(service_user.user.unix_uid),
	'name': lambda service_user: service_user.user.displayname,
	'preferred_username': lambda service_user: service_user.user.loginname,
	'email': lambda service_user: service_user.email,
	'email_verified': lambda service_user: service_user.email_verified,
	# RFC 9068 registers the "groups" claim with a syntax taken from SCIM (RFC 7643)
	# that is different from what we use here. The plain list of names syntax we use
	# is far more common in the context of id_token/userinfo claims.
	'groups': lambda service_user: [group.name for group in service_user.user.groups]
}

def render_claims(scopes, claims, service_user):
	claims = dict(claims)
	for scope in scopes:
		claims.update(OIDC_SCOPES.get(scope, {}))
	# This would be a good place to enforce permissions on available claims
	res = {}
	for claim, func in OIDC_CLAIMS.items():
		if claim in claims:
			res[claim] = func(service_user=service_user)
	return res

bp = Blueprint('oauth2', __name__, template_folder='templates')

@bp.route('/.well-known/openid-configuration')
def discover():
	return jsonify({
		'issuer': get_issuer(),
		'authorization_endpoint': url_for('oauth2.authorize', _external=True),
		'token_endpoint': url_for('oauth2.token', _external=True),
		'userinfo_endpoint': url_for('oauth2.userinfo', _external=True),
		'jwks_uri': url_for('oauth2.keys', _external=True),
		'scopes_supported': sorted(OIDC_SCOPES.keys()),
		'response_types_supported': ['code'],
		'grant_types_supported': ['authorization_code'],
		'id_token_signing_alg_values_supported': OAuth2Key.get_available_algorithms(),
		'subject_types_supported': ['public'],
		'token_endpoint_auth_methods_supported': ['client_secret_basic', 'client_secret_post'],
		'claims_supported': sorted(['iat', 'exp', 'aud', 'iss'] + list(OIDC_CLAIMS.keys())),
		'claims_parameter_supported': True,
		'request_uri_parameter_supported': False, # default is True
	})

@bp.route('/oauth2/keys')
def keys():
	return jsonify({
		'keys': [key.public_key_jwks_dict for key in OAuth2Key.query.filter_by(active=True)],
	}), 200, {'Cache-Control': ['max-age=86400, public, must-revalidate, no-transform=true']}

def oauth2_redirect(**extra_args):
	urlparts = urllib.parse.urlparse(request.oauth2_redirect_uri)
	args = urllib.parse.parse_qs(urlparts.query)
	if 'state' in request.args:
		args['state'] = request.args['state']
	for key, value in extra_args.items():
		if value is not None:
			args[key] = [value]
	return redirect(urlparts._replace(query=urllib.parse.urlencode(args, doseq=True)).geturl())

class OAuth2Error(Exception):
	ERROR: str

	def __init__(self, error_description=None):
		self.error_description = error_description

	@property
	def params(self):
		res = {'error': self.ERROR}
		if self.error_description:
			res['error_description'] = self.error_description
		return res

# RFC 6749: OAuth 2.0
class InvalidRequestError(OAuth2Error):
	ERROR = 'invalid_request'

class UnsupportedResponseTypeError(OAuth2Error):
	ERROR = 'unsupported_response_type'

class InvalidScopeError(OAuth2Error):
	ERROR = 'invalid_scope'

class InvalidClientError(OAuth2Error):
	ERROR = 'invalid_client'

class UnsupportedGrantTypeError(OAuth2Error):
	ERROR = 'unsupported_grant_type'

class InvalidGrantError(OAuth2Error):
	ERROR = 'invalid_grant'

class AccessDeniedError(OAuth2Error):
	ERROR = 'access_denied'

	def __init__(self, flash_message=None, **kwargs):
		self.flash_message = flash_message
		super().__init__(**kwargs)

# RFC 6750: OAuth 2.0 Bearer Token Usage
class InvalidTokenError(OAuth2Error):
	ERROR = 'invalid_token'

# OpenID Connect Core 1.0
class LoginRequiredError(OAuth2Error):
	ERROR = 'login_required'

	def __init__(self, response=None, flash_message=None, **kwargs):
		self.response = response
		self.flash_message = flash_message
		super().__init__(**kwargs)

class RequestNotSupportedError(OAuth2Error):
	ERROR = 'request_not_supported'

class RequestURINotSupportedError(OAuth2Error):
	ERROR = 'request_uri_not_supported'

def authorize_validate_request():
	request.oauth2_redirect_uri = None
	for param in request.args:
		if len(request.args.getlist(param)) > 1:
			raise InvalidRequestError(error_description=f'Duplicate parameter {param}')

	if 'client_id' not in request.args:
		raise InvalidRequestError(error_description='Required parameter client_id missing')
	client_id = request.args['client_id']
	client = OAuth2Client.query.filter_by(client_id=client_id).one_or_none()
	if not client:
		raise InvalidRequestError(error_description=f'Unknown client {client_id}')

	redirect_uri = request.args.get('redirect_uri')
	if redirect_uri and redirect_uri not in client.redirect_uris:
		raise InvalidRequestError(error_description='Invalid redirect_uri')
	request.oauth2_redirect_uri = redirect_uri or client.default_redirect_uri
	if not request.oauth2_redirect_uri:
		raise InvalidRequestError(error_description='Parameter redirect_uri required')

	if 'response_type' not in request.args:
		raise InvalidRequestError(error_description='Required parameter response_type missing')
	response_type = request.args['response_type']
	if response_type != 'code':
		raise UnsupportedResponseTypeError(error_description='Unsupported response type')

	scopes = {scope for scope in request.args.get('scope', '').split(' ') if scope} or {'profile'}
	if scopes == {'profile'}:
		pass # valid plain OAuth2 scopes
	elif 'openid' in scopes:
		# OIDC core spec: "Scope values used that are not understood by an implementation SHOULD be ignored."
		# Since we don't support some of the optional scope values defined by the
		# spec (phone, address, offline_access), it's probably best to ignore all
		# unknown scopes.
		pass # valid  OIDC scopes
	else:
		raise InvalidScopeError(error_description='Unknown scope')

	return OAuth2Grant(
		client=client,
		# redirect_uri is None if not present in request! This affects token request validation.
		redirect_uri=redirect_uri,
		scopes=scopes,
	)

def authorize_validate_request_oidc(grant):
	nonce = request.args.get('nonce')
	claims = json.loads(request.args['claims']) if 'claims' in request.args else None

	if 'request' in request.args:
		raise RequestNotSupportedError()
	if 'request_uri' in request.args:
		raise RequestURINotSupportedError()

	prompt_values = {value for value in request.args.get('prompt', '').split(' ') if value}
	if 'none' in prompt_values and prompt_values != {'none'}:
		raise InvalidRequestError(error_description='Invalid usage of none prompt parameter value')

	sub_value = None
	if claims and claims.get('id_token', {}).get('sub', {}).get('value') is not None:
		sub_value = claims['id_token']['sub']['value']
	if 'id_token_hint' in request.args:
		try:
			id_token = OAuth2Key.decode_jwt(
				request.args['id_token_hint'],
				issuer=get_issuer(),
				options={'verify_exp': False, 'verify_aud': False}
			)
		except (jwt.exceptions.InvalidTokenError, jwt.exceptions.InvalidKeyError) as err:
			raise InvalidRequestError(error_description='Invalid id_token_hint value') from err
		if sub_value is not None and id_token['sub'] != sub_value:
			raise InvalidRequestError(error_description='Ambiguous sub values in claims and id_token_hint')
		sub_value = id_token['sub']

	# We "MUST only send a positive response if the End-User identified by that
	# sub value has an active session with the Authorization Server or has been
	# Authenticated as a result of the request". However, we currently cannot
	# display the login page if there is already a valid session. So we can only
	# support sub_value in combination with prompt=none for now.
	if sub_value is not None and 'none' not in prompt_values:
		raise InvalidRequestError(error_description='id_token_hint or sub claim value not supported without prompt=none')

	grant.nonce = nonce
	grant.claims = claims
	return grant, sub_value, prompt_values

def authorize_user(client):
	if request.session:
		return request.session

	if 'devicelogin_started' in session:
		del session['devicelogin_started']
		host_delay = host_ratelimit.get_delay()
		if host_delay:
			raise LoginRequiredError(
				flash_message=_(
					'We received too many requests from your ip address/network! Please wait at least %(delay)s.',
					delay=format_delay(host_delay)
				),
				response=redirect(url_for('session.login', ref=request.full_path, devicelogin=True))
			)
		host_ratelimit.log()
		initiation = OAuth2DeviceLoginInitiation(client=client)
		db.session.add(initiation)
		try:
			db.session.commit()
		except IntegrityError as err:
			raise LoginRequiredError(
				flash_message=_('Device login is currently not available. Try again later!'),
				response=redirect(url_for('session.login', ref=request.values['ref'], devicelogin=True))
			) from err
		session['devicelogin_id'] = initiation.id
		session['devicelogin_secret'] = initiation.secret
		raise LoginRequiredError(response=redirect(url_for('session.devicelogin', ref=request.full_path)))
	if 'devicelogin_id' in session and 'devicelogin_secret' in session and 'devicelogin_confirmation' in session:
		initiation = OAuth2DeviceLoginInitiation.query.filter_by(
			id=session['devicelogin_id'],
			secret=session['devicelogin_secret'],
			client=client
		).one_or_none()
		confirmation = DeviceLoginConfirmation.query.get(session['devicelogin_confirmation'])
		del session['devicelogin_id']
		del session['devicelogin_secret']
		del session['devicelogin_confirmation']
		if not initiation or initiation.expired or not confirmation or confirmation.session.user.is_deactivated:
			raise LoginRequiredError(
				flash_message=_('Device login failed'),
				response=redirect(url_for('session.login', ref=request.full_path, devicelogin=True))
			)
		db.session.delete(initiation)
		db.session.commit()
		return confirmation.session

	raise LoginRequiredError(
		flash_message=_('You need to login to access this service'),
		response=redirect(url_for('session.login', ref=request.full_path, devicelogin=True))
	)

@bp.route('/oauth2/authorize')
def authorize():
	is_oidc = 'openid' in request.args.get('scope', '').split(' ')

	try:
		grant = authorize_validate_request()
		sub_value, prompt_values = None, []
		if is_oidc:
			grant, sub_value, prompt_values = authorize_validate_request_oidc(grant)
	except OAuth2Error as err:
		# Correct OAuth2/OIDC error handling would be to redirect back to the
		# client with an error paramter, unless client_id or redirect_uri is
		# invalid. However, uffd never did that before adding OIDC support and
		# many applications fail to correctly handle this case. As a compromise
		# we report errors correctly in OIDC mode and don't in plain OAuth2 mode.
		if is_oidc and request.oauth2_redirect_uri:
			return oauth2_redirect(**err.params)
		return render_template('oauth2/error.html', **err.params), 400

	try:
		_session = authorize_user(grant.client)
		if sub_value is not None and str(_session.user.unix_uid) != sub_value:
			# We only reach this point in OIDC requests with prompt=none, see
			# authorize_validate_request_oidc. So this LoginRequiredError is
			# always returned as a redirect back to the client.
			raise LoginRequiredError()
		if not grant.client.access_allowed(_session.user):
			raise AccessDeniedError(flash_message=_(
				"You don't have the permission to access the service <b>%(service_name)s</b>.",
				service_name=grant.client.service.name
			))
		grant.session = _session
	except LoginRequiredError as err:
		# We abuse LoginRequiredError to signal a redirect to the login page
		if is_oidc and 'none' in prompt_values:
			err.error_description = 'Login required but prompt value set to none'
			return oauth2_redirect(**err.params)
		if err.flash_message:
			flash(err.flash_message)
		return err.response
	except AccessDeniedError as err:
		if is_oidc and request.oauth2_redirect_uri:
			return oauth2_redirect(**err.params)
		abort(403, description=err.flash_message)

	db.session.add(grant)
	db.session.commit()
	return oauth2_redirect(code=grant.code)

def token_authenticate_client():
	for param in ('client_id', 'client_secret'):
		if len(request.form.getlist(param)) > 1:
			raise InvalidRequestError(error_description=f'Duplicate parameter {param}')
	if request.authorization:
		client_id = urllib.parse.unquote(request.authorization.username)
		client_secret = urllib.parse.unquote(request.authorization.password)
		if request.form.get('client_id', client_id) != client_id:
			raise InvalidRequestError(error_description='Ambiguous parameter client_id')
		if 'client_secret' in request.form:
			raise InvalidRequestError(error_description='Ambiguous parameter client_secret')
	elif 'client_id' in request.form and 'client_secret' in request.form:
		client_id = request.form['client_id']
		client_secret = request.form['client_secret']
	else:
		raise InvalidClientError()

	client = OAuth2Client.query.filter_by(client_id=client_id).one_or_none()
	if client is None or not client.client_secret.verify(client_secret):
		raise InvalidClientError()
	if client.client_secret.needs_rehash:
		client.client_secret = client_secret
		db.session.commit()
	return client

def token_validate_request(client):
	for param in ('grant_type', 'code', 'redirect_uri'):
		if len(request.form.getlist(param)) > 1:
			raise InvalidRequestError(error_description=f'Duplicate parameter {param}')
	if 'grant_type' not in request.form:
		raise InvalidRequestError(error_description='Parameter grant_type missing')
	grant_type = request.form['grant_type']
	if grant_type != 'authorization_code':
		raise UnsupportedGrantTypeError()
	if 'code' not in request.form:
		raise InvalidRequestError(error_description='Parameter code missing')
	code = request.form['code']

	grant = OAuth2Grant.get_by_authorization_code(code)
	if not grant or grant.client != client:
		raise InvalidGrantError()
	if grant.redirect_uri and grant.redirect_uri != request.form.get('redirect_uri'):
		raise InvalidRequestError(error_description='Parameter redirect_uri missing or invalid')
	return grant

@bp.route('/oauth2/token', methods=['POST'])
def token():
	try:
		client = token_authenticate_client()
		grant = token_validate_request(client)
	except InvalidClientError as err:
		return jsonify(err.params), 401, {'WWW-Authenticate': ['Basic realm="oauth2"']}
	except OAuth2Error as err:
		return jsonify(err.params), 400

	tok = grant.make_token()
	db.session.add(tok)
	db.session.delete(grant)
	db.session.commit()

	resp = {
		'token_type': 'Bearer',
		'access_token': tok.access_token,
		'expires_in': tok.EXPIRES_IN,
		'scope': ' '.join(tok.scopes),
	}
	if 'openid' in tok.scopes:
		key = OAuth2Key.get_preferred_key()
		id_token = render_claims(['openid'], (grant.claims or {}).get('id_token', {}), tok.service_user)
		id_token['iss'] = get_issuer()
		id_token['aud'] = tok.client.client_id
		id_token['iat'] = int(time.time())
		id_token['at_hash'] = key.oidc_hash(tok.access_token.encode('ascii'))
		id_token['exp'] = id_token['iat'] + tok.EXPIRES_IN

		service_user = tok.service_user
		id_token.update(render_claims(tok.scopes, (tok.claims or {}).get('userinfo', {}), service_user))

		if grant.nonce:
			id_token['nonce'] = grant.nonce
		resp['id_token'] = OAuth2Key.get_preferred_key().encode_jwt(id_token)
	else:
		# We don't support the refresh_token grant type. Due to limitations of
		# oauthlib we always returned (disfunctional) refresh tokens in the past.
		# We still do that for non-OIDC clients to not change behavour for
		# existing clients.
		resp['refresh_token'] = tok.refresh_token

	return jsonify(resp), 200, {'Cache-Control': ['no-store']}

def validate_access_token():
	if len(request.headers.getlist('Authorization')) == 1 and 'access_token' not in request.values:
		auth_type, auth_value = (request.headers['Authorization'].split(' ', 1) + [''])[:2]
		if auth_type.lower() != 'bearer':
			raise InvalidRequestError()
		access_token = auth_value
	elif len(request.values.getlist('access_token')) == 1 and 'Authorization' not in request.headers:
		access_token = request.values['access_token']
	else:
		raise InvalidClientError()
	tok = OAuth2Token.get_by_access_token(access_token)
	if not tok:
		raise InvalidTokenError()
	return tok

@bp.route('/oauth2/userinfo', methods=['GET', 'POST'])
def userinfo():
	try:
		tok = validate_access_token()
	except OAuth2Error as err:
		# RFC 6750:
		# If the request lacks any authentication information (e.g., the client
		# was unaware that authentication is necessary or attempted using an
		# unsupported authentication method), the resource server SHOULD NOT
		# include an error code or other error information.
		header = 'Bearer'
		if request.headers.get('Authorization', '').lower().startswith('bearer') or 'access_token' in request.values:
			header += f' error="{err.ERROR}"'
		return '', 401, {'WWW-Authenticate': [header]}

	service_user = tok.service_user
	if 'openid' in tok.scopes:
		resp = render_claims(tok.scopes, (tok.claims or {}).get('userinfo', {}), service_user)
	else:
		resp = {
			'id': service_user.user.unix_uid,
			'name': service_user.user.displayname,
			'nickname': service_user.user.loginname,
			'email': service_user.email,
			'groups': [group.name for group in service_user.user.groups],
		}
	return jsonify(resp), 200, {'Cache-Control': ['private']}

@bp.app_url_defaults
def inject_logout_params(endpoint, values):
	if endpoint != 'oauth2.logout' or not request.session:
		return
	client_ids = set(token.client.client_id for token in request.session.oauth2_tokens)
	if client_ids:
		values['client_ids'] = ','.join(client_ids)

@bp.route('/oauth2/logout')
def logout():
	if not request.values.get('client_ids'):
		return secure_local_redirect(request.values.get('ref', '/'))
	client_ids = request.values['client_ids'].split(',')
	clients = [OAuth2Client.query.filter_by(client_id=client_id).one() for client_id in client_ids]
	return render_template('oauth2/logout.html', clients=clients)
