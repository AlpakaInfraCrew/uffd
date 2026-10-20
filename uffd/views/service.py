import functools

from flask import Blueprint, render_template, request, url_for, redirect, current_app, abort
from flask_babel import lazy_gettext

from uffd.navbar import register_navbar
from uffd.csrf import csrf_protect
from uffd.database import db
from uffd.models import User, Service, ServiceUser, get_services, Group, OAuth2Client, OAuth2LogoutURI, APIClient, RemailerMode

from .session import login_required

bp = Blueprint('service', __name__, template_folder='templates')

bp.add_app_template_global(RemailerMode, 'RemailerMode')

def admin_acl():
	return request.user and request.user.is_in_group(current_app.config['ACL_ADMIN_GROUP'])

def overview_login_maybe_required(func):
	@functools.wraps(func)
	def decorator(*args, **kwargs):
		if not current_app.config['SERVICES']:
			return login_required(admin_acl)(func)(*args, **kwargs)
		if not current_app.config['SERVICES_PUBLIC']:
			return login_required()(func)(*args, **kwargs)
		return func(*args, **kwargs)
	return decorator

def overview_navbar_visible():
	return get_services(request.user) or admin_acl()

@bp.route('/services/')
@register_navbar(lazy_gettext('Services'), icon='sitemap', blueprint=bp, visible=overview_navbar_visible)
@overview_login_maybe_required
def overview():
	services = get_services(request.user)
	banner = ''
	if request.user or current_app.config['SERVICES_BANNER_PUBLIC']:
		banner = current_app.config['SERVICES_BANNER']
	return render_template('service/overview.html', services=services, banner=banner)

@bp.route('/service/admin')
@login_required(admin_acl)
def index():
	return render_template('service/index.html', services=Service.query.all())

@bp.route('/service/new')
@bp.route('/service/<int:id>')
@login_required(admin_acl)
def show(id=None):
	service = Service() if id is None else Service.query.get_or_404(id)
	remailer_overwrites = []
	if id is not None:
		# pylint: disable=singleton-comparison
		remailer_overwrites = ServiceUser.query.filter(
			ServiceUser.service_id == id,
			ServiceUser.remailer_overwrite_mode != None
		).all()
	all_groups = Group.query.all()
	return render_template('service/show.html', service=service, all_groups=all_groups, remailer_overwrites=remailer_overwrites)

@bp.route('/service/new', methods=['POST'])
@bp.route('/service/<int:id>', methods=['POST'])
@csrf_protect(blueprint=bp)
@login_required(admin_acl)
def edit_submit(id=None):
	if id is None:
		service = Service()
		db.session.add(service)
	else:
		service = Service.query.get_or_404(id)
	service.name = request.form['name']
	if not request.form['access-group']:
		service.limit_access = True
		service.access_group = None
	elif request.form['access-group'] == 'all':
		service.limit_access = False
		service.access_group = None
	else:
		service.limit_access = True
		service.access_group = Group.query.get(request.form['access-group'])
	service.hide_deactivated_users = request.form.get('hide_deactivated_users') == '1'
	service.enable_email_preferences = request.form.get('enable_email_preferences') == '1'
	service.remailer_mode = RemailerMode[request.form['remailer-mode']]
	remailer_overwrite_mode = RemailerMode[request.form['remailer-overwrite-mode']]
	remailer_overwrite_user_ids = [
		User.query.filter_by(loginname=loginname.strip()).one().id
		for loginname in request.form['remailer-overwrite-users'].split(',') if loginname.strip()
	]
	# pylint: disable=singleton-comparison
	service_users = ServiceUser.query.filter(
		ServiceUser.service == service,
		db.or_(
			ServiceUser.user_id.in_(remailer_overwrite_user_ids),
			ServiceUser.remailer_overwrite_mode != None,
		)
	)
	for service_user in service_users:
		if service_user.user_id in remailer_overwrite_user_ids:
			service_user.remailer_overwrite_mode = remailer_overwrite_mode
		else:
			service_user.remailer_overwrite_mode = None
	db.session.commit()
	return redirect(url_for('service.show', id=service.id))

@bp.route('/service/<int:id>/delete')
@csrf_protect(blueprint=bp)
@login_required(admin_acl)
def delete(id):
	service = Service.query.get_or_404(id)
	db.session.delete(service)
	db.session.commit()
	return redirect(url_for('service.index'))

@bp.route('/service/<int:service_id>/oauth2/new')
@bp.route('/service/<int:service_id>/oauth2/<int:db_id>')
@login_required(admin_acl)
def oauth2_show(service_id, db_id=None):
	service = Service.query.get_or_404(service_id)
	client = OAuth2Client() if db_id is None else OAuth2Client.query.filter_by(service_id=service_id, db_id=db_id).first_or_404()
	return render_template('service/oauth2.html', service=service, client=client)

@bp.route('/service/<int:service_id>/oauth2/new', methods=['POST'])
@bp.route('/service/<int:service_id>/oauth2/<int:db_id>', methods=['POST'])
@csrf_protect(blueprint=bp)
@login_required(admin_acl)
def oauth2_submit(service_id, db_id=None):
	service = Service.query.get_or_404(service_id)
	if db_id is None:
		client = OAuth2Client(service=service)
		db.session.add(client)
	else:
		client = OAuth2Client.query.filter_by(service_id=service_id, db_id=db_id).first_or_404()
	client.client_id = request.form['client_id']
	if request.form['client_secret']:
		client.client_secret = request.form['client_secret']
	if not client.client_secret:
		abort(400)
	client.redirect_uris = [x.strip() for x in request.form['redirect_uris'].split('\n') if x.strip()]
	client.logout_uris = []
	for line in request.form['logout_uris'].split('\n'):
		line = line.strip()
		if not line:
			continue
		method, uri = line.split(' ', 2)
		client.logout_uris.append(OAuth2LogoutURI(method=method, uri=uri))
	client.use_uuid_as_sub = request.form.get('use_uuid_as_sub') == '1'
	db.session.commit()
	return redirect(url_for('service.show', id=service.id))

@bp.route('/service/<int:service_id>/oauth2/<int:db_id>/delete')
@csrf_protect(blueprint=bp)
@login_required(admin_acl)
def oauth2_delete(service_id, db_id=None):
	service = Service.query.get_or_404(service_id)
	client = OAuth2Client.query.filter_by(service_id=service_id, db_id=db_id).first_or_404()
	db.session.delete(client)
	db.session.commit()
	return redirect(url_for('service.show', id=service.id))

@bp.route('/service/<int:service_id>/api/new')
@bp.route('/service/<int:service_id>/api/<int:id>')
@login_required(admin_acl)
def api_show(service_id, id=None):
	service = Service.query.get_or_404(service_id)
	client = APIClient() if id is None else APIClient.query.filter_by(service_id=service_id, id=id).first_or_404()
	return render_template('service/api.html', service=service, client=client)

@bp.route('/service/<int:service_id>/api/new', methods=['POST'])
@bp.route('/service/<int:service_id>/api/<int:id>', methods=['POST'])
@csrf_protect(blueprint=bp)
@login_required(admin_acl)
def api_submit(service_id, id=None):
	service = Service.query.get_or_404(service_id)
	if id is None:
		client = APIClient(service=service)
		db.session.add(client)
	else:
		client = APIClient.query.filter_by(service_id=service_id, id=id).first_or_404()
	client.auth_username = request.form['auth_username']
	if request.form['auth_password']:
		client.auth_password = request.form['auth_password']
	if not client.auth_password:
		abort(400)
	client.perm_users = request.form.get('perm_users') == '1'
	client.perm_checkpassword = request.form.get('perm_checkpassword') == '1'
	client.perm_remailer = request.form.get('perm_remailer') == '1'
	client.perm_metrics = request.form.get('perm_metrics') == '1'
	db.session.commit()
	return redirect(url_for('service.show', id=service.id))

@bp.route('/service/<int:service_id>/api/<int:id>/delete')
@csrf_protect(blueprint=bp)
@login_required(admin_acl)
def api_delete(service_id, id=None):
	service = Service.query.get_or_404(service_id)
	client = APIClient.query.filter_by(service_id=service_id, id=id).first_or_404()
	db.session.delete(client)
	db.session.commit()
	return redirect(url_for('service.show', id=service.id))
