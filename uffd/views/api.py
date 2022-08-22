import functools
import datetime
from secrets import token_hex

from flask import Blueprint, jsonify, request, abort, Response

from uffd.database import db
from uffd.models import (
	User, ServiceUser, Group, Mail, MailReceiveAddress, MailDestinationAddress, APIClient,
	RecoveryCodeMethod, TOTPMethod, WebauthnMethod, Invite, Role, Service )
from .session import login_ratelimit

bp = Blueprint('api', __name__, template_folder='templates', url_prefix='/api/v1/')

def apikey_required(permission=None):
	# pylint: disable=too-many-return-statements
	if permission is not None:
		assert APIClient.permission_exists(permission)
	def wrapper(func):
		@functools.wraps(func)
		def decorator(*args, **kwargs):
			if not request.authorization or not request.authorization.password:
				return 'Unauthorized', 401, {'WWW-Authenticate': ['Basic realm="api"']}
			client = APIClient.query.filter_by(auth_username=request.authorization.username).first()
			if not client:
				return 'Unauthorized', 401, {'WWW-Authenticate': ['Basic realm="api"']}
			if not client.auth_password.verify(request.authorization.password):
				return 'Unauthorized', 401, {'WWW-Authenticate': ['Basic realm="api"']}
			if client.auth_password.needs_rehash:
				client.auth_password = request.authorization.password
				db.session.commit()
			if permission is not None and not client.has_permission(permission):
				return 'Forbidden', 403
			request.api_client = client
			return func(*args, **kwargs)
		return decorator
	return wrapper

def generate_group_dict(group):
	return {
		'id': group.unix_gid,
		'name': group.name,
		'members': [
			user.loginname
			for user in group.members
			if not user.is_deactivated or not request.api_client.service.hide_deactivated_users
		]
	}

@bp.route('/getgroups', methods=['GET', 'POST'])
@apikey_required('users')
def getgroups():
	if len(request.values) > 1:
		abort(400)
	key = (list(request.values.keys()) or [None])[0]
	values = request.values.getlist(key)
	query = Group.query
	if key is None:
		pass
	elif key == 'id' and len(values) == 1:
		query = query.filter(Group.unix_gid == values[0])
	elif key == 'name' and len(values) == 1:
		query = query.filter(Group.name == values[0])
	elif key == 'member' and len(values) == 1:
		query = query.join(Group.members).filter(User.loginname == values[0])
		if request.api_client.service.hide_deactivated_users:
			query = query.filter(db.not_(User.is_deactivated))
	else:
		abort(400)
	# Single-result queries perform better without eager loading
	if key is None or key == 'member':
		query = query.options(db.selectinload(Group.members))
	return jsonify([generate_group_dict(group) for group in query])

def generate_user_dict(service_user):
	return {
		'id': service_user.user.unix_uid,
		'loginname': service_user.user.loginname,
		'email': service_user.email,
		'displayname': service_user.user.displayname,
		'groups': [group.name for group in service_user.user.groups]
	}

@bp.route('/getusers', methods=['GET', 'POST'])
@apikey_required('users')
def getusers():
	if len(request.values) > 1:
		abort(400)
	key = (list(request.values.keys()) or [None])[0]
	values = request.values.getlist(key)
	query = ServiceUser.query.filter_by(service=request.api_client.service).join(ServiceUser.user)
	if request.api_client.service.hide_deactivated_users:
		query = query.filter(db.not_(User.is_deactivated))
	if key is None:
		pass
	elif key == 'id' and len(values) == 1:
		query = query.filter(User.unix_uid == values[0])
	elif key == 'loginname' and len(values) == 1:
		query = query.filter(User.loginname == values[0])
	elif key == 'email' and len(values) == 1:
		query = ServiceUser.filter_query_by_email(query, values[0])
	elif key == 'group' and len(values) == 1:
		query = query.join(User.groups).filter(Group.name == values[0])
	else:
		abort(400)
	# Single-result queries perform better without eager loading
	if key is None or key == 'group':
		# pylint: disable=no-member
		query = query.options(db.joinedload(ServiceUser.user).selectinload(User.groups))
		query = query.options(db.joinedload(ServiceUser.user).joinedload(User.primary_email))
	return jsonify([generate_user_dict(user) for user in query])

@bp.route('/checkpassword', methods=['POST'])
@apikey_required('checkpassword')
def checkpassword():
	if set(request.values.keys()) != {'loginname', 'password'}:
		abort(400)
	username = request.form['loginname'].lower()
	password = request.form['password']
	login_delay = login_ratelimit.get_delay(username)
	if login_delay:
		return 'Too Many Requests', 429, {'Retry-After': '%d'%login_delay}
	service_user = ServiceUser.query.join(User).filter(
		ServiceUser.service == request.api_client.service,
		User.loginname == username,
	).one_or_none()
	if service_user is None or not service_user.user.password.verify(password):
		login_ratelimit.log(username)
		return jsonify(None)
	if service_user.user.is_deactivated:
		return jsonify(None)
	if service_user.user.password.needs_rehash:
		service_user.user.password = password
		db.session.commit()
	return jsonify(generate_user_dict(service_user))

def generate_mail_dict(mail):
	return {
		'name': mail.uid,
		'receive_addresses': list(mail.receivers),
		'destination_addresses': list(mail.destinations)
	}

@bp.route('/getmails', methods=['GET', 'POST'])
@apikey_required('mail_aliases')
def getmails():
	if len(request.values) > 1:
		abort(400)
	key = (list(request.values.keys()) or [None])[0]
	values = request.values.getlist(key)
	query = Mail.query
	if key is None:
		pass
	elif key == 'name' and len(values) == 1:
		query = query.filter_by(uid=values[0])
	elif key == 'receive_address' and len(values) == 1:
		query = query.filter(Mail.receivers.any(MailReceiveAddress.address==values[0].lower()))
	elif key == 'destination_address' and len(values) == 1:
		query = query.filter(Mail.destinations.any(MailDestinationAddress.address==values[0]))
	else:
		abort(400)
	return jsonify([generate_mail_dict(mail) for mail in query])

@bp.route('/resolve-remailer', methods=['GET', 'POST'])
@apikey_required('remailer')
def resolve_remailer():
	if list(request.values.keys()) != ['orig_address']:
		abort(400)
	values = request.values.getlist('orig_address')
	if len(values) != 1:
		abort(400)
	service_user = ServiceUser.get_by_remailer_email(values[0])
	if not service_user:
		return jsonify(address=None)
	return jsonify(address=service_user.real_email)

@bp.route('/metrics_prometheus', methods=['GET'])
@apikey_required('metrics')
def prometheus_metrics():
	import pkg_resources #pylint: disable=import-outside-toplevel
	from prometheus_client.core import CollectorRegistry, CounterMetricFamily, InfoMetricFamily #pylint: disable=import-outside-toplevel
	from prometheus_client import PLATFORM_COLLECTOR, generate_latest, CONTENT_TYPE_LATEST #pylint: disable=import-outside-toplevel

	class UffdCollector():
		def collect(self):
			try:
				uffd_version = str(pkg_resources.get_distribution('uffd').version)
			except pkg_resources.DistributionNotFound:
				uffd_version = "unknown"
			yield InfoMetricFamily('uffd_version', 'Various version infos', value={"version": uffd_version})

			user_metric = CounterMetricFamily('uffd_users_total', 'Number of users', labels=['user_type'])
			user_metric.add_metric(['regular'], value=User.query.filter_by(is_service_user=False).count())
			user_metric.add_metric(['service'], User.query.filter_by(is_service_user=True).count())
			yield user_metric

			mfa_auth_metric = CounterMetricFamily('uffd_users_auth_mfa_total', 'mfa stats', labels=['mfa_type'])
			mfa_auth_metric.add_metric(['recoverycode'], value=RecoveryCodeMethod.query.count())
			mfa_auth_metric.add_metric(['totp'], value=TOTPMethod.query.count())
			mfa_auth_metric.add_metric(['webauthn'], value=WebauthnMethod.query.count())
			yield mfa_auth_metric

			yield CounterMetricFamily('uffd_roles_total', 'Number of roles', value=Role.query.count())

			role_members_metric = CounterMetricFamily('uffd_role_members_total', 'Members of a role', labels=['role_name'])
			for role in Role.query.all():
				role_members_metric.add_metric([role.name], value=len(role.members))
			yield role_members_metric

			group_metric = CounterMetricFamily('uffd_groups_total', 'Total number of groups', value=Group.query.count())
			yield group_metric

			invite_metric = CounterMetricFamily('uffd_invites_total', 'Number of invites', labels=['invite_state'])
			invite_metric.add_metric(['used'], value=Invite.query.filter_by(used=True).count())
			invite_metric.add_metric(['expired'], value=Invite.query.filter_by(expired=True).count())
			invite_metric.add_metric(['disabled'], value=Invite.query.filter_by(disabled=True).count())
			invite_metric.add_metric(['voided'], value=Invite.query.filter_by(voided=True).count())
			invite_metric.add_metric([], value=Invite.query.count())
			yield invite_metric

			yield CounterMetricFamily('uffd_services_total', 'Number of services', value=Service.query.count())

	registry = CollectorRegistry(auto_describe=True)
	registry.register(PLATFORM_COLLECTOR)
	registry.register(UffdCollector())
	return Response(response=generate_latest(registry=registry),content_type=CONTENT_TYPE_LATEST)

@bp.route('/sync', methods=['GET'])
@apikey_required('users')
def start_sync():
	sync_token = token_hex(16)
	service_users = ServiceUser.query.filter(
		ServiceUser.service == request.api_client.service,
		db.or_(
			ServiceUser.needs_sync == True,
			ServiceUser.needs_sync == None,
			ServiceUser.last_sync < datetime.datetime.utcnow() - datetime.timedelta(hours=24),
		),
		db.or_(
			ServiceUser.sync_token == None,
			ServiceUser.sync_started < datetime.datetime.utcnow() - datetime.timedelta(seconds=10),
		)
	).order_by(ServiceUser.needs_sync, ServiceUser.last_sync.desc()).limit(10).with_for_update().all()
	for service_user in service_users:
		service_user.sync_started = datetime.datetime.utcnow()
		service_user.sync_token = sync_token
	db.session.commit()
	return jsonify([
		{
			'sync_token': f'{sync_token}-{service_user.user_id}',
			'data': generate_user_dict(service_user),
		}
		for service_user in service_users
	])

@bp.route('/sync', methods=['POST'])
@apikey_required('users')
def finish_sync():
	for result in request.json:
		sync_token, user_id = result['sync_token'].split('-', 1)
		query = ServiceUser.query.filter_by(
			service=request.api_client.service,
			user_id=user_id,
			sync_token=sync_token,
		)
		if result['status'] == 'ok':
			query.update(dict(
				sync_token=None,
				last_sync=datetime.datetime.utcnow(),
				needs_sync=False,
			))
	db.session.commit()
	return 'OK', 200
