import unittest
from urllib.parse import urlparse, parse_qs

import jwt
from flask import url_for, session

from uffd.database import db
from uffd.password_hash import PlaintextPasswordHash
from uffd.remailer import remailer
from uffd.models import DeviceLoginConfirmation, Service, OAuth2Client, OAuth2DeviceLoginInitiation, RemailerMode, OAuth2Key, Session

from tests.utils import dump, UffdTestCase
from tests.models.test_oauth2 import TEST_JWK

class TestViews(UffdTestCase):
	def setUpDB(self):
		db.session.add(OAuth2Client(service=Service(name='test', limit_access=False), client_id='test', client_secret='testsecret', redirect_uris=['http://localhost:5009/callback', 'http://localhost:5009/callback2']))
		db.session.add(OAuth2Client(service=Service(name='test1', access_group=self.get_admin_group()), client_id='test1', client_secret='testsecret1', redirect_uris=['http://localhost:5008/callback']))

	def assert_authorization(self, r, mail=None):
		while True:
			if r.status_code != 302 or r.location.startswith('http://localhost:5009/callback'):
				break
			r = self.client.get(r.location, follow_redirects=False)
		self.assertEqual(r.status_code, 302)
		self.assertTrue(r.location.startswith('http://localhost:5009/callback'))
		args = parse_qs(urlparse(r.location).query)
		self.assertEqual(args['state'], ['teststate'])
		code = args['code'][0]
		r = self.client.post(path=url_for('oauth2.token'),
			data={'grant_type': 'authorization_code', 'code': code, 'redirect_uri': 'http://localhost:5009/callback', 'client_id': 'test', 'client_secret': 'testsecret'}, follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['token_type'], 'Bearer')
		self.assertEqual(r.json['scope'], 'profile')
		token = r.json['access_token']
		r = self.client.get(path=url_for('oauth2.userinfo'), headers=[('Authorization', 'Bearer %s'%token)], follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(r.content_type, 'application/json')
		user = self.get_user()
		self.assertEqual(r.json['id'], user.unix_uid)
		self.assertEqual(r.json['name'], user.displayname)
		self.assertEqual(r.json['nickname'], user.loginname)
		self.assertEqual(r.json['email'], mail or user.primary_email.address)
		self.assertTrue(r.json.get('groups'))

	def test_authorization(self):
		self.login_as('user')
		r = self.client.get(path=url_for('oauth2.authorize', response_type='code', client_id='test', state='teststate', redirect_uri='http://localhost:5009/callback', scope='profile'), follow_redirects=False)
		self.assert_authorization(r)

	def test_authorization_with_remailer(self):
		self.app.config['REMAILER_DOMAIN'] = 'remailer.example.com'
		service = Service.query.filter_by(name='test').one()
		service.remailer_mode = RemailerMode.ENABLED_V1
		db.session.commit()
		self.login_as('user')
		r = self.client.get(path=url_for('oauth2.authorize', response_type='code', client_id='test', state='teststate', redirect_uri='http://localhost:5009/callback', scope='profile'), follow_redirects=False)
		service = Service.query.filter_by(name='test').one()
		self.assert_authorization(r, mail=remailer.build_v1_address(service.id, self.get_user().id))

	def test_authorization_client_secret_rehash(self):
		OAuth2Client.query.delete()
		db.session.add(OAuth2Client(service=Service(name='rehash_test', limit_access=False), client_id='test', client_secret=PlaintextPasswordHash.from_password('testsecret'), redirect_uris=['http://localhost:5009/callback', 'http://localhost:5009/callback2']))
		db.session.commit()
		self.assertIsInstance(OAuth2Client.query.filter_by(client_id='test').one().client_secret, PlaintextPasswordHash)
		self.login_as('user')
		r = self.client.get(path=url_for('oauth2.authorize', response_type='code', client_id='test', state='teststate', redirect_uri='http://localhost:5009/callback', scope='profile'), follow_redirects=False)
		self.assert_authorization(r)
		oauth2_client = OAuth2Client.query.filter_by(client_id='test').one()
		self.assertIsInstance(oauth2_client.client_secret, OAuth2Client.client_secret.method_cls)
		self.assertTrue(oauth2_client.client_secret.verify('testsecret'))

	def test_authorization_without_redirect_uri(self):
		client = OAuth2Client.query.filter_by(client_id='test').one()
		client.redirect_uris.remove('http://localhost:5009/callback2')
		db.session.commit()
		self.login_as('user')
		r = self.client.get(path=url_for('oauth2.authorize', response_type='code', client_id='test', state='teststate', scope='profile'), follow_redirects=False)
		self.assert_authorization(r)

	def test_authorization_without_scope(self):
		self.login_as('user')
		r = self.client.get(path=url_for('oauth2.authorize', response_type='code', client_id='test', state='teststate', redirect_uri='http://localhost:5009/callback'), follow_redirects=False)
		self.assert_authorization(r)

	# Regression test for #115 (OAuth2 authorize endpoint rejects empty scope parameter)
	def test_authorization_empty_scope(self):
		self.login_as('user')
		r = self.client.get(path=url_for('oauth2.authorize', response_type='code', client_id='test', state='teststate', scope='', redirect_uri='http://localhost:5009/callback'), follow_redirects=False)
		self.assert_authorization(r)

	def test_authorization_access_denied(self):
		client = OAuth2Client.query.filter_by(client_id='test').one()
		client.service.limit_access = True
		db.session.commit()
		self.login_as('user')
		r = self.client.get(path=url_for('oauth2.authorize', response_type='code', client_id='test', state='teststate', redirect_uri='http://localhost:5009/callback', scope='profile'), follow_redirects=False)
		self.assertEqual(r.status_code, 403)
		dump('oauth2_authorization_access_denied', r)

	def test_authorization_invalid_scope(self):
		self.login_as('user')
		r = self.client.get(path=url_for('oauth2.authorize', response_type='code', client_id='test', state='teststate', redirect_uri='http://localhost:5009/callback', scope='invalid'), follow_redirects=False)
		self.assertEqual(r.status_code, 400)
		dump('oauth2_authorization_invalid_scope', r)

	def test_authorization_missing_client_id(self):
		self.login_as('user')
		r = self.client.get(path=url_for('oauth2.authorize', response_type='code', state='teststate', redirect_uri='http://localhost:5009/callback', scope='profile'), follow_redirects=False)
		self.assertEqual(r.status_code, 400)
		dump('oauth2_authorization_missing_client_id', r)

	def test_authorization_invalid_client_id(self):
		self.login_as('user')
		r = self.client.get(path=url_for('oauth2.authorize', response_type='code', client_id='invalid_client_id', state='teststate', redirect_uri='http://localhost:5009/callback', scope='profile'), follow_redirects=False)
		self.assertEqual(r.status_code, 400)
		dump('oauth2_authorization_invalid_client_id', r)

	def test_authorization_missing_response_type(self):
		self.login_as('user')
		r = self.client.get(path=url_for('oauth2.authorize', client_id='test', state='teststate', redirect_uri='http://localhost:5009/callback', scope='profile'), follow_redirects=False)
		self.assertEqual(r.status_code, 400)
		dump('oauth2_authorization_missing_response_type', r)

	def test_authorization_invalid_response_type(self):
		self.login_as('user')
		r = self.client.get(path=url_for('oauth2.authorize', response_type='token', client_id='test', state='teststate', redirect_uri='http://localhost:5009/callback', scope='profile'), follow_redirects=False)
		self.assertEqual(r.status_code, 400)
		dump('oauth2_authorization_invalid_response_type', r)

	def test_authorization_devicelogin_start(self):
		ref = url_for('oauth2.authorize', response_type='code', client_id='test', state='teststate', redirect_uri='http://localhost:5009/callback')
		r = self.client.get(path=url_for('session.devicelogin_start', ref=ref), follow_redirects=True)
		# check response
		initiation = OAuth2DeviceLoginInitiation.query.filter_by(id=session['devicelogin_id'], secret=session['devicelogin_secret']).one()
		self.assertEqual(r.status_code, 200)
		self.assertFalse(initiation.expired)
		self.assertEqual(initiation.client.client_id, 'test')
		self.assertIsNotNone(initiation.description)

	def test_authorization_devicelogin_auth(self):
		with self.client.session_transaction() as _session:
			initiation = OAuth2DeviceLoginInitiation(client=OAuth2Client.query.filter_by(client_id='test').one())
			db.session.add(initiation)
			confirmation = DeviceLoginConfirmation(initiation=initiation, session=Session(user=self.get_user()))
			db.session.add(confirmation)
			db.session.commit()
			_session['devicelogin_id'] = initiation.id
			_session['devicelogin_secret'] = initiation.secret
			code = confirmation.code
		self.client.get(path='/')
		ref = url_for('oauth2.authorize', response_type='code', client_id='test', state='teststate', redirect_uri='http://localhost:5009/callback')
		r = self.client.post(path=url_for('session.devicelogin_submit', ref=ref), data={'confirmation-code': code}, follow_redirects=False)
		self.assert_authorization(r)

	def test_authorization_devicelogin_auth_deactivated(self):
		with self.client.session_transaction() as _session:
			initiation = OAuth2DeviceLoginInitiation(client=OAuth2Client.query.filter_by(client_id='test').one())
			db.session.add(initiation)
			confirmation = DeviceLoginConfirmation(initiation=initiation, session=Session(user=self.get_user()))
			db.session.add(confirmation)
			db.session.commit()
			_session['devicelogin_id'] = initiation.id
			_session['devicelogin_secret'] = initiation.secret
			code = confirmation.code
		self.client.get(path='/')
		self.get_user().is_deactivated = True
		db.session.commit()
		ref = url_for('oauth2.authorize', response_type='code', client_id='test', state='teststate', redirect_uri='http://localhost:5009/callback')
		r = self.client.post(path=url_for('session.devicelogin_submit', ref=ref), data={'confirmation-code': code}, follow_redirects=True)
		self.assertIn(b'Device login failed', r.data)

	def get_auth_code(self):
		self.login_as('user')
		r = self.client.get(path=url_for('oauth2.authorize', response_type='code', client_id='test', state='teststate', redirect_uri='http://localhost:5009/callback', scope='profile'), follow_redirects=False)
		while True:
			if r.status_code != 302 or r.location.startswith('http://localhost:5009/callback'):
				break
			r = self.client.get(r.location, follow_redirects=False)
		self.assertEqual(r.status_code, 302)
		self.assertTrue(r.location.startswith('http://localhost:5009/callback'))
		args = parse_qs(urlparse(r.location).query)
		self.assertEqual(args['state'], ['teststate'])
		return args['code'][0]

	def test_token_urlsecret(self):
		r = self.client.post(path=url_for('oauth2.token'),
			data={'grant_type': 'authorization_code', 'code': self.get_auth_code(), 'redirect_uri': 'http://localhost:5009/callback', 'client_id': 'test', 'client_secret': 'testsecret'}, follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['token_type'], 'Bearer')
		self.assertEqual(r.json['scope'], 'profile')

	# Regression test for #114 (OAuth2 token endpoint does not support Basic-Auth)
	def test_token_basicauth(self):
		r = self.client.post(path=url_for('oauth2.token'),
			data={'grant_type': 'authorization_code', 'code': self.get_auth_code(), 'redirect_uri': 'http://localhost:5009/callback'},
			headers={'Authorization': f'Basic dGVzdDp0ZXN0c2VjcmV0'}, follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['token_type'], 'Bearer')
		self.assertEqual(r.json['scope'], 'profile')

	def test_token_invalid_code(self):
		r = self.client.post(path=url_for('oauth2.token'),
			data={'grant_type': 'authorization_code', 'code': 'abcdef', 'redirect_uri': 'http://localhost:5009/callback', 'client_id': 'test', 'client_secret': 'testsecret'}, follow_redirects=True)
		self.assertEqual(r.status_code, 400)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['error'], 'invalid_grant')

	def test_token_code_invalidation(self):
		code = self.get_auth_code()
		r = self.client.post(path=url_for('oauth2.token'),
			data={'grant_type': 'authorization_code', 'code': code, 'redirect_uri': 'http://localhost:5009/callback'},
			headers={'Authorization': f'Basic dGVzdDp0ZXN0c2VjcmV0'}, follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		r = self.client.post(path=url_for('oauth2.token'),
			data={'grant_type': 'authorization_code', 'code': code, 'redirect_uri': 'http://localhost:5009/callback'},
			headers={'Authorization': f'Basic dGVzdDp0ZXN0c2VjcmV0'}, follow_redirects=True)
		self.assertEqual(r.status_code, 400)
		self.assertEqual(r.json['error'], 'invalid_grant')

	def test_token_invalid_client(self):
		r = self.client.post(path=url_for('oauth2.token'),
			data={'grant_type': 'authorization_code', 'code': self.get_auth_code(), 'redirect_uri': 'http://localhost:5009/callback', 'client_id': 'invalid_client', 'client_secret': 'invalid_client_secret'}, follow_redirects=True)
		self.assertEqual(r.status_code, 401)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['error'], 'invalid_client')

	def test_token_unauthorized_client(self):
		r = self.client.post(path=url_for('oauth2.token'),
			data={'grant_type': 'authorization_code', 'code': self.get_auth_code(), 'redirect_uri': 'http://localhost:5009/callback', 'client_id': 'test'}, follow_redirects=True)
		self.assertEqual(r.status_code, 401)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['error'], 'invalid_client')

	def test_token_unsupported_grant_type(self):
		r = self.client.post(path=url_for('oauth2.token'),
			data={'grant_type': 'password', 'code': self.get_auth_code(), 'redirect_uri': 'http://localhost:5009/callback', 'client_id': 'test', 'client_secret': 'testsecret'}, follow_redirects=True)
		self.assertEqual(r.status_code, 400)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['error'], 'unsupported_grant_type')

	def test_token_deactivated_user(self):
		code = self.get_auth_code()
		self.get_user().is_deactivated = True
		db.session.commit()
		r = self.client.post(path=url_for('oauth2.token'),
			data={'grant_type': 'authorization_code', 'code': code, 'redirect_uri': 'http://localhost:5009/callback', 'client_id': 'test', 'client_secret': 'testsecret'}, follow_redirects=True)
		self.assertEqual(r.status_code, 400)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['error'], 'invalid_grant')

	def test_userinfo_invalid_access_token(self):
		token = 'invalidtoken'
		r = self.client.get(path=url_for('oauth2.userinfo'), headers=[('Authorization', 'Bearer %s'%token)], follow_redirects=True)
		self.assertEqual(r.status_code, 401)

	def test_userinfo_deactivated_user(self):
		r = self.client.post(path=url_for('oauth2.token'),
			data={'grant_type': 'authorization_code', 'code': self.get_auth_code(), 'redirect_uri': 'http://localhost:5009/callback', 'client_id': 'test', 'client_secret': 'testsecret'}, follow_redirects=True)
		token = r.json['access_token']
		self.get_user().is_deactivated = True
		db.session.commit()
		r = self.client.get(path=url_for('oauth2.userinfo'), headers=[('Authorization', 'Bearer %s'%token)], follow_redirects=True)
		self.assertEqual(r.status_code, 401)

class TestOIDCConfigurationProfile(UffdTestCase):
	def setUpDB(self):
		db.session.add(OAuth2Key(**TEST_JWK))

	def test_discover_spec(self):
		ISSUER = 'https://sso.example.com'
		r = self.client.get(base_url=ISSUER, path='/.well-known/openid-configuration')

		# OIDC Discovery 1.0 section 4.2:
		# > A successful response MUST use the 200 OK HTTP status code and return a
		# > JSON object using the application/json content type that contains a set
		# > of Claims as its members that are a subset of the Metadata values defined
		# > in Section 3.
		self.assertEqual(r.status_code, 200)
		self.assertEqual(r.content_type, 'application/json')
		self.assertIsInstance(r.json, dict) # also validates JSON syntax

		# OIDC Discovery 1.0 section 4.2:
		# > Claims that return multiple values are represented as JSON arrays.
		# > Claims with zero elements MUST be omitted from the response. 
		for key, value in r.json.items():
			if isinstance(value, list):
				self.assertNotEqual(len(value), 0)

		# OIDC Discovery 1.0 section 3 (REQUIRED metadata values)
		required_fields = {'issuer', 'authorization_endpoint', 'jwks_uri', 'response_types_supported', 'subject_types_supported', 'id_token_signing_alg_values_supported'}
		if 'code' in r.json.get('response_types_supported', []):
			required_fields.add('token_endpoint')
		if 'authorization_code' in r.json.get('grant_types_supported', ['authorization_code', 'implicit']):
			required_fields.add('token_endpoint')
		for field in required_fields:
			self.assertIn(field, r.json)

		# OIDC Discovery 1.0 section 3 (metadata value types)
		bool_fields = ('claims_parameter_supported', 'request_parameter_supported', 'request_uri_parameter_supported', 'require_request_uri_registration')
		list_fields = ('scopes_supported', 'response_types_supported', 'response_modes_supported', 'grant_types_supported', 'acr_values_supported', 'subject_types_supported', 'id_token_signing_alg_values_supported', 'id_token_encryption_alg_values_supported', 'id_token_encryption_enc_values_supported', 'userinfo_signing_alg_values_supported', 'userinfo_encryption_alg_values_supported', 'userinfo_encryption_enc_values_supported', 'request_object_signing_alg_values_supported', 'request_object_encryption_alg_values_supported', 'request_object_encryption_enc_values_supported', 'token_endpoint_auth_methods_supported', 'token_endpoint_auth_signing_alg_values_supported', 'display_values_supported', 'claim_types_supported', 'claims_supported', 'claims_locales_supported', 'ui_locales_supported')
		https_url_fields = ('issuer', 'authorization_endpoint', 'token_endpoint', 'userinfo_endpoint', 'jwks_uri', 'registration_endpoint')
		url_fields = ('service_documentation', 'op_policy_uri', 'op_tos_uri')
		for field in bool_fields:
			if field in r.json:
				self.assertIsInstance(r.json[field], bool)
		for field in list_fields:
			if field in r.json:
				self.assertIsInstance(r.json[field], list)
		for field in https_url_fields:
			if field in r.json:
				self.assertIsInstance(r.json[field], str)
				self.assertTrue(r.json[field].lower().startswith('https://'))
		for field in url_fields:
			if field in r.json:
				self.assertIsInstance(r.json[field], str)
				self.assertTrue(r.json[field].lower().startswith('http'))

		# OIDC Discovery 1.0 section 3 (MUSTs on metadata values except https scheme and jwks_uri)
		self.assertEqual(r.json['issuer'], ISSUER)
		if 'scopes_supported' in r.json:
			self.assertIsInstance(r.json['scopes_supported'], list)
			for item in r.json['scopes_supported']:
				self.assertIsInstance(item, str)
				self.assertRegex(item, r'^[!#-\[\]-~]+$') # 1*( %x21 / %x23-5B / %x5D-7E )
			self.assertIn('openid', r.json['scopes_supported'])
		self.assertIn('RS256', r.json['id_token_signing_alg_values_supported'])
		if 'token_endpoint_auth_signing_alg_values_supported' in r.json:
			self.assertNotIn('none', r.json['token_endpoint_auth_signing_alg_values_supported'])

		# OIDC Discovery 1.0 section 3 (jwks_uri) and RFC7517
		self.assertTrue(r.json['jwks_uri'].startswith(ISSUER)) # Not a requirement by spec, but technically neccessary for this test
		r_jwks = self.client.get(base_url=ISSUER, path=r.json['jwks_uri'][len(ISSUER):])
		self.assertEqual(r_jwks.status_code, 200)
		# The jwks_uri SHOULD include a Cache-Control header in the response that contains a max-age directive ...
		self.assertIn('Cache-Control', r_jwks.headers)
		self.assertIsInstance(r_jwks.json, dict) # also validates JSON syntax
		self.assertIn('keys', r_jwks.json)
		self.assertIsInstance(r_jwks.json['keys'], list)
		has_sign_keys = False
		has_encrypt_keys = False
		kids = set()
		for key in r_jwks.json['keys']:
			self.assertIn('kty', key)
			self.assertIsInstance(key['kty'], str)
			if 'use' in key:
				self.assertIsInstance(key['use'], str)
				if key['use'] == 'sig':
					has_sign_keys = True
				if key['use'] == 'enc':
					has_enc_keys = True
			if 'key_ops' in key:
				self.assertIsInstance(key['key_ops'], list)
				self.assertNotIn('use', key) # SHOULD
				for value in key['key_ops']:
					self.assertIsInstance(value, str)
					self.assertEqual(key['key_ops'].count(value), 1)
				# OIDC: "The JWK Set MUST NOT contain private or symmetric key values."
				self.assertNotIn('decrypt', key['key_ops'])
				self.assertNotIn('sign', key['key_ops'])
				if 'verify' in key['key_ops']:
					has_sign_keys = True
				if 'encrypt' in key['key_ops']:
					has_enc_keys = True
			if 'alg' in key:
				self.assertIsInstance(key['alg'], str)
			if 'kid' in key:
				self.assertIsInstance(key['kid'], str)
				self.assertNotIn(key['kid'], kids) # SHOULD
				kids.add(key['kid'])
			# ignoring everything X.509 related
			# TODO: Validate algorithm-specific part of JWK
		if has_sign_keys and has_encrypt_keys:
			for key in r_jwks.json['keys']:
				self.assertIn('use', key)

class TestOIDCBasicProfile(UffdTestCase):
	def setUpDB(self):
		db.session.add(OAuth2Key(**TEST_JWK))
		db.session.add(OAuth2Client(service=Service(name='test', limit_access=False), client_id='test', client_secret='testsecret', redirect_uris=['https://service/callback']))

	# Helper
	def validate_claim_syntax(self, name, value):
		# Strip language tag
		if '#' in name:
			name = name.split('#')[0]
		str_claims = ('sub', 'name', 'given_name', 'family_name', 'middle_name', 'nickname', 'preferred_username', 'profile', 'picture', 'website', 'email', 'gender', 'birthdate', 'zoneinfo', 'locale', 'phone_number', 'acr')
		if name in str_claims:
			self.assertIsInstance(value, str)
		if name in ('profile', 'picture', 'website'):
			self.assertTrue(value.lower().startswith('http'))
		if name in ('email_verified', 'phone_number_verified'):
			self.assertIsInstance(value, bool)
		if name in ('updated_at', 'auth_time'):
			self.assertTrue(isinstance(value, int) or isinstance(value, float))
		if name == 'address':
			self.assertIsInstance(value, dict)
		if name == 'amr':
			self.assertIsInstance(value, list)
			for item in value:
				self.assertIsInstance(item, str)

	def validate_id_token(self, id_token, nonce='testnonce', client_id='test'):
		headers = jwt.get_unverified_header(id_token)
		self.assertIn('kid', headers)
		self.assertIsInstance(headers['kid'], str)
		# This checks signature and exp
		data = OAuth2Key.decode_jwt(id_token, options={'verify_aud': False})
		self.assertIn('iss', data)
		self.assertIsInstance(data['iss'], str)
		self.assertIn('sub', data)
		self.assertIn('aud', data)
		self.assertIsInstance(data['aud'], str)
		if client_id is not None:
			self.assertEqual(data['aud'], client_id)
		self.assertIn('iat', data)
		self.assertTrue(isinstance(data['iat'], int) or isinstance(data['iat'], float))
		if 'nonce' in data:
			self.assertIsInstance(data['nonce'], str)
		self.assertEqual(data.get('nonce'), nonce)
		if 'azp' in data:
			self.assertIsInstance(data['azp'], str)
		for name, value in data.items():
			self.validate_claim_syntax(name, value)
		return data

	def is_login_page(self, location):
		url = urlparse(location)
		return url.netloc in ('localhost', '') and url.path == url_for('session.login')

	def is_callback(self, location):
		return location.startswith('https://service/callback')

	def do_auth_request(self, client_id='test', state='teststate', nonce='testnonce', redirect_uri='https://service/callback', scope='openid', follow_redirects=True, **kwargs):
		r = self.client.get(path=url_for('oauth2.authorize', client_id=client_id, state=state, nonce=nonce, redirect_uri=redirect_uri, scope=scope, **kwargs), follow_redirects=False)
		while follow_redirects and r.status_code == 302 and not self.is_login_page(r.location) and not self.is_callback(r.location):
			r = self.client.get(path=r.location, follow_redirects=False)
		return r

	def do_login(self, r, loginname='testuser', password='userpassword'):
		self.assertEqual(r.status_code, 302)
		self.assertTrue(self.is_login_page(r.location))
		self.client.get(path=url_for('session.logout'), follow_redirects=True)
		args = parse_qs(urlparse(r.location).query)
		r = self.client.post(path=url_for('session.login', ref=args['ref'][0]), data={'loginname': loginname, 'password': password}, follow_redirects=False)
		while r.status_code == 302 and not self.is_login_page(r.location) and not self.is_callback(r.location):
			r = self.client.get(path=r.location, follow_redirects=False)
		return r

	def validate_auth_response(self, r, state='teststate'):
		self.assertEqual(r.status_code, 302)
		self.assertTrue(self.is_callback(r.location))
		args = parse_qs(urlparse(r.location).query)
		for key in args:
			self.assertNotIn(key, ('error', 'error_description', 'error_uri'))
			self.assertEqual(len(args[key]), 1) # Not generally specified, but still a good check
		if state is not None:
			self.assertIn('state', args)
			self.assertEqual(args['state'], [state])
		else:
			self.assertNotIn('state', args)
		return {key: values[0] for key, values in args.items()}

	def assert_auth_error(self, r, *errors, state='teststate'):
		self.assertEqual(r.status_code, 302)
		self.assertTrue(self.is_callback(r.location))
		args = parse_qs(urlparse(r.location).query)
		for key in args:
			self.assertIn(key, ('error', 'error_description', 'error_uri', 'state'))
			self.assertEqual(len(args[key]), 1)
		self.assertIn('error', args)
		if state is not None:
			self.assertIn('state', args)
			self.assertEqual(args['state'][0], state)
		else:
			self.assertNotIn('state', args)
		if errors:
			self.assertIn(args['error'][0], errors)
		self.assertRegex(args['error'][0], r'^[ -!#-\[\]-~]+$') # 1*( %x20-x21 / %x23-5B / %x5D-7E )
		if 'error_description' in args:
			self.assertRegex(args['error_description'][0], r'^[ -!#-\[\]-~]+$') # 1*( %x20-x21 / %x23-5B / %x5D-7E )
		if 'error_uri' in args:
			self.assertRegex(args['error_uri'][0], r'^[!#-\[\]-~]+$') # 1*( %x21 / %x23-5B / %x5D-7E )

	def do_token_request(self, client_id='test', client_secret='testsecret', redirect_uri='https://service/callback', **kwargs):
		data = {'redirect_uri': redirect_uri, 'client_id': client_id, 'client_secret': client_secret}
		data.update(kwargs)
		return self.client.post(path=url_for('oauth2.token'), data=data, follow_redirects=True)

	def validate_token_response(self, r, nonce='testnonce', client_id='test'):
		self.assertEqual(r.status_code, 200)
		self.assertEqual(r.content_type, 'application/json')
		# OIDC Core 1.0 section 3.1.3.3:
		# > All Token Responses that contain tokens, secrets, or other sensitive
		# > information MUST include the following HTTP response header fields and values:
		# >   Cache-Control: no-store
		self.assertIn('Cache-Control', r.headers)
		self.assertEqual(r.headers['Cache-Control'].lower(), 'no-store')
		for key in r.json:
			self.assertNotIn(key, ('error', 'error_description', 'error_uri'))
		self.assertIn('access_token', r.json)
		self.assertIsInstance(r.json['access_token'], str)
		self.assertIn('token_type', r.json)
		self.assertIsInstance(r.json['token_type'], str)
		# OIDC Core 1.0 section 3.1.3.3:
		# > The OAuth 2.0 token_type response parameter value MUST be Bearer,
		# > [...] unless another Token Type has been negotiated with the Client.
		self.assertEqual(r.json['token_type'].lower(), 'bearer')
		if 'expires_in' in r.json:
			self.assertTrue(isinstance(r.json['expires_in'], int) or isinstance(data['expires_in'], float))
		if 'refresh_token' in r.json:
			self.assertIsInstance(r.json['refresh_token'], str)
		if 'scope' in r.json:
			self.assertIsInstance(r.json['scope'], str)
			# scope       = scope-token *( SP scope-token )
			# scope-token = 1*( %x21 / %x23-5B / %x5D-7E )
			self.assertRegex(r.json['scope'], r'^[!#-\[\]-~]+( [!#-\[\]-~]+)*$')
		self.assertIn('id_token', r.json)
		return self.validate_id_token(r.json['id_token'], nonce=nonce, client_id=client_id)

	def assert_token_error(self, r, *errors):
		self.assertEqual(r.content_type, 'application/json')
		if r.json.get('error', '') == 'invalid_client':
			self.assertEqual(r.status_code, 401)
		else:
			self.assertEqual(r.status_code, 400)
		for key in r.json:
			self.assertIn(key, ('error', 'error_description', 'error_uri'))
		self.assertIn('error', r.json)
		if errors:
			self.assertIn(r.json['error'], errors)
		self.assertRegex(r.json['error'], r'^[ -!#-\[\]-~]+$') # 1*( %x20-x21 / %x23-5B / %x5D-7E )
		if 'error_description' in r.json:
			self.assertRegex(r.json['error_description'], r'^[ -!#-\[\]-~]+$') # 1*( %x20-x21 / %x23-5B / %x5D-7E )
		if 'error_uri' in r.json:
			self.assertRegex(r.json['error_uri'], r'^[!#-\[\]-~]+$') # 1*( %x21 / %x23-5B / %x5D-7E )

	def do_userinfo_request(self, access_token):
		return self.client.get(path=url_for('oauth2.userinfo'), headers=[('Authorization', 'Bearer %s'%access_token)], follow_redirects=True)

	def validate_userinfo_response(self, r):
		self.assertEqual(r.status_code, 200)
		# We ignore everything related to encrypted/signed JWT userinfo here
		self.assertEqual(r.content_type, 'application/json')
		self.assertIn('sub', r.json)
		for name, value in r.json.items():
			self.validate_claim_syntax(name, value)

	def assert_userinfo_error(self, r):
		self.assertEqual(r.status_code, 401)
		self.assertEqual(len(r.headers.getlist('WWW-Authenticate')), 1)
		method, args = (r.headers['WWW-Authenticate'].split(' ', 1) + [''])[:2]
		args = {item.split('=', 1)[0]: item.split('=', 1)[1].strip(' \n"') for item in args.split(',') if item.strip()}
		if 'scope' in args:
			self.assertRegex(args['scope'], r'^[ -!#-\[\]-~]+$') # 1*( %x20-x21 / %x23-5B / %x5D-7E )
		if 'error' in args:
			self.assertRegex(args['error'], r'^[ -!#-\[\]-~]+$') # 1*( %x20-x21 / %x23-5B / %x5D-7E )
		if 'error_description' in args:
			self.assertRegex(args['error_description'], r'^[ -!#-\[\]-~]+$') # 1*( %x20-x21 / %x23-5B / %x5D-7E )

	def test(self):
		self.login_as('user')
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'])
		print(r, repr(r.response), repr(r.json))
		self.assertTrue(False)
		id_token = self.validate_token_response(r)
		self.assertEqual(id_token['sub'], '10000')
		r = self.do_userinfo_request(r.json['access_token'])
		self.validate_userinfo_response(r)
		self.assertEqual(r.json['sub'], '10000')

	def test_notloggedin(self):
		r = self.do_auth_request(response_type='code')
		r = self.do_login(r)
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'])
		id_token = self.validate_token_response(r)
		self.assertEqual(id_token['sub'], '10000')

	def test_no_state(self):
		self.login_as('user')
		r = self.do_auth_request(response_type='code', state=None)
		args = self.validate_auth_response(r, state=None)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'])
		id_token = self.validate_token_response(r)
		self.assertEqual(id_token['sub'], '10000')

	def test_no_nonce(self):
		self.login_as('user')
		r = self.do_auth_request(response_type='code', nonce=None)
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'])
		id_token = self.validate_token_response(r, nonce=None)
		self.assertEqual(id_token['sub'], '10000')

	def test_redirect_uri(self):
		self.login_as('user')
		# No redirect_uri in auth request is fine if there is only one uri registered
		r = self.do_auth_request(response_type='code', redirect_uri=None)
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'], redirect_uri=None)
		id_token = self.validate_token_response(r)
		self.assertEqual(id_token['sub'], '10000')
		# If auth request has redirect_uri, it is required in token request
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'], redirect_uri=None)
		self.assert_token_error(r)
		# If auth request has redirect_uri, it the redirect_uri in the token request must be the same
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'], redirect_uri='https://foobar/callback')
		self.assert_token_error(r)
		# Invalid redirect_uri
		r = self.do_auth_request(response_type='code', redirect_uri='http://foobar/callback')
		self.assertEqual(r.status_code, 400) # No redirect!
		# redirect_uri is required in auth request if there is more than a single uri registered
		client = OAuth2Client.query.one()
		client.redirect_uris.append('https://service/callback2')
		db.session.commit()
		r = self.do_auth_request(response_type='code', redirect_uri=None)
		self.assertEqual(r.status_code, 400) # No redirect!

	def test_auth_errors(self):
		# Missing response_type
		r = self.do_auth_request()
		self.assert_auth_error(r, 'invalid_request')
		# Invalid response_type
		r = self.do_auth_request(response_type='foobar')
		self.assert_auth_error(r, 'unsupported_response_type')
		# Missing client_id
		r = self.do_auth_request(response_type='code', client_id=None)
		self.assertEqual(r.status_code, 400) # No redirect!
		# Invalid client_id
		r = self.do_auth_request(response_type='code', client_id='foobar')
		self.assertEqual(r.status_code, 400) # No redirect!
		# Duplicate parameter
		r = self.do_auth_request(response_type='code', client_id=['test', 'foobar'])
		self.assertEqual(r.status_code, 400) # No redirect!

	def test_access_denied(self):
		Service.query.one().limit_access = True
		db.session.commit()
		self.login_as('user')
		r = self.do_auth_request(response_type='code')
		self.assert_auth_error(r, 'access_denied')

	def test_auth_request_uri(self):
		self.login_as('user')
		r = self.do_auth_request(response_type='code', request_uri='https://localhost/myrequest_uri')
		self.assert_auth_error(r, 'request_uri_not_supported')

	def test_auth_request_unsigned(self):
		self.login_as('user')
		request_params = {
			'response_type': 'code',
			'client_id': 'test',
			'redirect_uri': 'http://service/callback',
			'scope': 'openid',
			'state': 'teststate',
			'nonce': 'testnonce',
			'claims': {
				'userinfo': {
					'name': None,
					'email': {'essential': True},
					'email_verified': {'essential': True},
				},
				'id_token': {
					'email': None,
				}
			}
		}
		r = self.do_auth_request(response_type='code', request=jwt.encode(request_params, algorithm='none', key=None))
		self.assert_auth_error(r, 'request_not_supported')

	def test_token_client_auth(self):
		self.login_as('user')
		# Auth via body -> ACCEPT
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'])
		self.validate_token_response(r)
		# Auth via header -> ACCEPT
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.client.post(
			path=url_for('oauth2.token'),
			data={'redirect_uri': 'https://service/callback', 'grant_type': 'authorization_code', 'code': args['code']},
			headers={'Authorization': f'Basic dGVzdDp0ZXN0c2VjcmV0'},
			follow_redirects=True,
		)
		self.validate_token_response(r)
		# Auth via header, but same client id also in body -> ACCEPT
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.client.post(
			path=url_for('oauth2.token'),
			data={'redirect_uri': 'https://service/callback', 'grant_type': 'authorization_code', 'client_id': 'test', 'code': args['code']},
			headers={'Authorization': f'Basic dGVzdDp0ZXN0c2VjcmV0'},
			follow_redirects=True,
		)
		self.validate_token_response(r)
		# Different client id in body and header -> REJECT
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.client.post(
			path=url_for('oauth2.token'),
			data={'redirect_uri': 'https://service/callback', 'grant_type': 'authorization_code', 'client_id': 'XXXX', 'code': args['code']},
			headers={'Authorization': f'Basic dGVzdDp0ZXN0c2VjcmV0'},
			follow_redirects=True,
		)
		self.assert_token_error(r, 'invalid_request')
		# Duplicate client id in body -> REJECT
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'], client_id=['test', 'XXXX'])
		self.assert_token_error(r, 'invalid_request')
		# Duplicate client secret in body -> REJECT
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'], client_secret=['testsecret', 'XXXXX'])
		self.assert_token_error(r, 'invalid_request')
		# Client secret in body and header -> REJECT
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.client.post(
			path=url_for('oauth2.token'),
			data={'redirect_uri': 'https://service/callback', 'grant_type': 'authorization_code', 'client_id': 'test', 'client_secret': 'testsecret', 'code': args['code']},
			headers={'Authorization': f'Basic dGVzdDp0ZXN0c2VjcmV0'},
			follow_redirects=True,
		)
		self.assert_token_error(r, 'invalid_request')
		# No secret -> REJECT
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'], client_secret=None)
		self.assert_token_error(r, 'invalid_client')
		# No client id but secret -> REJECT
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'], client_id=None)
		self.assert_token_error(r, 'invalid_client')
		# No client id and no secret -> REJECT
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'], client_id=None, client_secret=None)
		self.assert_token_error(r, 'invalid_client')
		# Unknown client id -> REJECT
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'], client_id='XXXX')
		self.assert_token_error(r, 'invalid_client')

	def test_token_errors(self):
		self.login_as('user')
		# Missing grant_type parameter
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(code=args['code'])
		self.assert_token_error(r, 'invalid_request')
		# Missing code parameter
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code')
		self.assert_token_error(r, 'invalid_request')
		# redirect_uri behaviour is already tested in test_redirect_uri
		# Invalid grant type
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='foobar', code=args['code'])
		self.assert_token_error(r, 'unsupported_grant_type')
		# Duplicate code parameter
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=[args['code'], 'XXXXX'])
		self.assert_token_error(r, 'invalid_request')
		# Invalid code parameter
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code='XXXXX')
		self.assert_token_error(r, 'invalid_grant')
		# Invalid code parameter
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'].split('-')[0]+'-XXXXX')
		self.assert_token_error(r, 'invalid_grant')
		# Code was issued to different client
		db.session.add(OAuth2Client(service=Service(name='test2', limit_access=False), client_id='test2', client_secret='testsecret2', redirect_uris=['https://service2/callback']))
		db.session.commit()
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'], client_id='test2', client_secret='testsecret2')
		self.assert_token_error(r, 'invalid_grant')

	def test_userinfo_auth(self):
		self.login_as('user')
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'])
		self.validate_token_response(r)
		access_token = r.json['access_token']
		# GET + Bearer
		r = self.client.get(path=url_for('oauth2.userinfo'), headers=[('Authorization', 'Bearer %s'%access_token)], follow_redirects=True)
		self.validate_userinfo_response(r)
		self.assertEqual(r.json['sub'], '10000')
		# POST + Bearer
		r = self.client.post(path=url_for('oauth2.userinfo'), headers=[('Authorization', 'Bearer %s'%access_token)], follow_redirects=True)
		self.validate_userinfo_response(r)
		self.assertEqual(r.json['sub'], '10000')
		# "Bearer" is case-insensitive
		r = self.client.post(path=url_for('oauth2.userinfo'), headers=[('authorization', 'bearer %s'%access_token)], follow_redirects=True)
		self.validate_userinfo_response(r)
		self.assertEqual(r.json['sub'], '10000')
		# Invalid auth scheme
		r = self.client.post(path=url_for('oauth2.userinfo'), headers=[('Authorization', 'Basic dGVzdDp0ZXN0c2VjcmV0')], follow_redirects=True)
		self.assert_userinfo_error(r)
		# Invalid bearer token
		r = self.client.post(path=url_for('oauth2.userinfo'), headers=[('Authorization', 'Bearer %s-XXXXX'%access_token.split('-')[0])], follow_redirects=True)
		self.assert_userinfo_error(r)
		r = self.client.post(path=url_for('oauth2.userinfo'), headers=[('Authorization', 'Bearer XXXXX')], follow_redirects=True)
		self.assert_userinfo_error(r)
		# POST + body
		r = self.client.post(path=url_for('oauth2.userinfo'), data={'access_token': access_token}, follow_redirects=True)
		self.validate_userinfo_response(r)
		self.assertEqual(r.json['sub'], '10000')
		# GET + query
		r = self.client.get(path=url_for('oauth2.userinfo', access_token=access_token), follow_redirects=True)
		self.validate_userinfo_response(r)
		self.assertEqual(r.json['sub'], '10000')
		# POST + Bearer + body -> REJECT
		r = self.client.post(path=url_for('oauth2.userinfo'), data={'access_token': access_token}, headers=[('Authorization', 'Bearer %s'%access_token)], follow_redirects=True)
		self.assert_userinfo_error(r)
		# No auth -> REJECT
		r = self.client.post(path=url_for('oauth2.userinfo'), follow_redirects=True)
		self.assert_userinfo_error(r)

	def test_scope(self):
		self.login_as('user')
		# Scope values used that are not understood by an implementation SHOULD be ignored.
		r = self.do_auth_request(response_type='code', scope='openid profile email address phone groups foobar')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'])
		id_token = self.validate_token_response(r)
		self.assertEqual(id_token['sub'], '10000')
		r = self.do_userinfo_request(r.json['access_token'])
		self.validate_userinfo_response(r)
		self.assertEqual(r.json['sub'], '10000')
		self.assertEqual(r.json['name'], 'Test User')
		self.assertEqual(r.json['preferred_username'], 'testuser')
		self.assertEqual(r.json['email'], 'test@example.com')
		self.assertEqual(sorted(r.json['groups']), sorted(['users', 'uffd_access']))

	def test_claims(self):
		self.login_as('user')
		# Scope values used that are not understood by an implementation SHOULD be ignored.
		r = self.do_auth_request(response_type='code', claims='{"userinfo": {"name": {"essential": true}}, "id_token": {"preferred_username": {"essential": true}, "email": null}}')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'])
		id_token = self.validate_token_response(r)
		self.assertEqual(id_token['sub'], '10000')
		self.assertEqual(id_token['preferred_username'], 'testuser')
		self.assertEqual(id_token['email'], 'test@example.com')
		self.assertNotIn('name', r.json)
		r = self.do_userinfo_request(r.json['access_token'])
		self.validate_userinfo_response(r)
		self.assertEqual(r.json['sub'], '10000')
		self.assertEqual(r.json['name'], 'Test User')
		self.assertNotIn('email', r.json)

	def test_prompt_none(self):
		r = self.do_auth_request(response_type='code', prompt='none')
		self.assert_auth_error(r, 'login_required')
		self.login_as('user')
		r = self.do_auth_request(response_type='code', prompt='none')
		args = self.validate_auth_response(r)
		self.assertIn('code', args)
		# OIDC Core 1.0 section 3.1.2.1.:
		# > If this parameter contains none with any other value, an error is returned.
		r = self.do_auth_request(response_type='code', prompt='none login')
		self.assert_auth_error(r)

	@unittest.skip('prompt=login is not implemented') # MUST
	def test_prompt_login(self):
		self.login_as('user')
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		self.assertIn('code', args)
		r = self.do_auth_request(response_type='code', prompt='login')
		self.assertEqual(r.status_code, 302)
		self.assertTrue(self.is_login_page(r.location))

	# TODO: max_age

	def test_sub_value(self):
		# Via id_token_hint or claims.id_token.sub.value
		self.login_as('user')
		r = self.do_auth_request(response_type='code', prompt='none')
		args = self.validate_auth_response(r)
		r = self.do_token_request(grant_type='authorization_code', code=args['code'])
		self.validate_token_response(r)
		id_token = r.json['id_token']
		r = self.do_auth_request(response_type='code', prompt='none', id_token_hint=id_token)
		args = self.validate_auth_response(r)
		self.assertIn('code', args)
		r = self.do_auth_request(response_type='code', prompt='none', id_token_hint='XXXXX')
		self.assert_auth_error(r, 'invalid_request')
		r = self.do_auth_request(response_type='code', prompt='none', claims='{"id_token": {"sub": {"value": "10000"}}}')
		args = self.validate_auth_response(r)
		r = self.do_auth_request(response_type='code', prompt='none', claims='{"id_token": {"sub": {"value": "10001"}}}')
		self.assert_auth_error(r, 'login_required')
		# sub value in id_token_hint and claims is the same -> Not ambiguous
		r = self.do_auth_request(response_type='code', prompt='none', id_token_hint=id_token, claims='{"id_token": {"sub": {"value": "10000"}}}')
		args = self.validate_auth_response(r)
		self.assertIn('code', args)
		# sub value in id_token_hint and claims differs -> Ambiguous
		r = self.do_auth_request(response_type='code', prompt='none', id_token_hint=id_token, claims='{"id_token": {"sub": {"value": "10001"}}}')
		self.assert_auth_error(r, 'invalid_request')
		self.login_as('admin')
		r = self.do_auth_request(response_type='code', prompt='none', id_token_hint=id_token)
		self.assert_auth_error(r, 'login_required')

	def test_code_reuse(self):
		self.login_as('user')
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r1 = self.do_token_request(grant_type='authorization_code', code=args['code'])
		self.validate_token_response(r1)
		r2 = self.do_token_request(grant_type='authorization_code', code=args['code'])
		self.assert_token_error(r2, 'invalid_grant')

	@unittest.skip('Token revoking on reuse is not implemented') # SHOULD
	def test_code_reuse_revoke(self):
		self.login_as('user')
		r = self.do_auth_request(response_type='code')
		args = self.validate_auth_response(r)
		r1 = self.do_token_request(grant_type='authorization_code', code=args['code'])
		self.validate_token_response(r1)
		r2 = self.do_token_request(grant_type='authorization_code', code=args['code'])
		self.assert_token_error(r2, 'invalid_grant')
		r = self.do_userinfo_request(r1.json['access_token'])
		self.assert_userinfo_error(r)
