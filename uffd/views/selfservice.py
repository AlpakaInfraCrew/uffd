import secrets

from flask import Blueprint, render_template, session, request, url_for, redirect, flash, current_app, abort
from flask_babel import gettext as _, lazy_gettext
from sqlalchemy.exc import IntegrityError

from uffd.navbar import register_navbar
from uffd.csrf import csrf_protect
from uffd.sendmail import sendmail
from uffd.database import db
from uffd.models import (
	User, UserEmail, PasswordToken, Role, host_ratelimit, Ratelimit, format_delay,
	Session, MFAMethod, TOTPMethod, WebauthnMethod, RecoveryCodeMethod,
)
from uffd.fido2_compat import * # pylint: disable=wildcard-import,unused-wildcard-import

from .session import login_required

bp = Blueprint("selfservice", __name__, template_folder='templates', url_prefix='/self/')

reset_ratelimit = Ratelimit('passwordreset', 1*60*60, 3)

def selfservice_acl_check():
	return request.user and request.user.is_in_group(current_app.config['ACL_SELFSERVICE_GROUP'])

@bp.route("/")
@register_navbar(lazy_gettext('Selfservice'), icon='portrait', blueprint=bp, visible=selfservice_acl_check)
@login_required(selfservice_acl_check)
def index():
	return render_template('selfservice/self.html', user=request.user)

@bp.route("/updateprofile", methods=(['POST']))
@csrf_protect(blueprint=bp)
@login_required(selfservice_acl_check)
def update_profile():
	if request.values['displayname'] != request.user.displayname:
		if request.user.set_displayname(request.values['displayname']):
			flash(_('Display name changed.'))
		else:
			flash(_('Display name is not valid.'))
	db.session.commit()
	return redirect(url_for('selfservice.index'))

@bp.route("/changepassword", methods=(['POST']))
@csrf_protect(blueprint=bp)
@login_required(selfservice_acl_check)
def change_password():
	if not request.values['password1'] == request.values['password2']:
		flash(_('Passwords do not match'))
	else:
		if request.user.set_password(request.values['password1']):
			flash(_('Password changed'))
		else:
			flash(_('Invalid password'))
	db.session.commit()
	return redirect(url_for('selfservice.index'))

@bp.route("/passwordreset", methods=(['GET', 'POST']))
def forgot_password():
	if request.method == 'GET':
		return render_template('selfservice/forgot_password.html')

	loginname = request.values['loginname'].lower()
	mail = request.values['mail']
	reset_delay = reset_ratelimit.get_delay(loginname+'/'+mail)
	host_delay = host_ratelimit.get_delay()
	if reset_delay or host_delay:
		if reset_delay > host_delay:
			flash(_('We received too many password reset requests for this user! Please wait at least %(delay)s.', delay=format_delay(reset_delay)))
		else:
			flash(_('We received too many requests from your ip address/network! Please wait at least %(delay)s.', delay=format_delay(host_delay)))
		return redirect(url_for('.forgot_password'))
	reset_ratelimit.log(loginname+'/'+mail)
	host_ratelimit.log()
	flash(_("We sent a mail to this user's mail address if you entered the correct mail and login name combination"))
	user = User.query.filter_by(loginname=loginname, is_deactivated=False).one_or_none()
	if not user:
		return redirect(url_for('session.login'))
	matches = any(map(lambda email: secrets.compare_digest(email.address, mail), user.verified_emails))
	if not matches:
		return redirect(url_for('session.login'))
	recovery_email = user.recovery_email or user.primary_email
	if recovery_email.address == mail and user.is_in_group(current_app.config['ACL_SELFSERVICE_GROUP']):
		send_passwordreset(user)
	return redirect(url_for('session.login'))

@bp.route("/token/password/<int:token_id>/<token>", methods=(['POST', 'GET']))
def token_password(token_id, token):
	dbtoken = PasswordToken.query.get(token_id)
	if not dbtoken or not secrets.compare_digest(dbtoken.token, token) or \
			dbtoken.expired:
		flash(_('Link invalid or expired'))
		return redirect(url_for('session.login'))
	if request.method == 'GET':
		return render_template('selfservice/set_password.html', token=dbtoken)
	if not request.values['password1']:
		flash(_('You need to set a password, please try again.'))
		return render_template('selfservice/set_password.html', token=dbtoken)
	if not request.values['password1'] == request.values['password2']:
		flash(_('Passwords do not match, please try again.'))
		return render_template('selfservice/set_password.html', token=dbtoken)
	if not dbtoken.user.is_in_group(current_app.config['ACL_SELFSERVICE_GROUP']):
		abort(403)
	if not dbtoken.user.set_password(request.values['password1']):
		flash(_('Password ist not valid, please try again.'))
		return render_template('selfservice/set_password.html', token=dbtoken)
	db.session.delete(dbtoken)
	db.session.commit()
	flash(_('New password set'))
	return redirect(url_for('session.login'))

@bp.route("/email/new", methods=['POST'])
@login_required(selfservice_acl_check)
@csrf_protect(blueprint=bp)
def add_email():
	email = UserEmail(user=request.user)
	if not email.set_address(request.form['address']):
		flash(_('E-Mail address is invalid'))
		return redirect(url_for('selfservice.index'))
	try:
		db.session.flush()
	except IntegrityError:
		flash(_('E-Mail address already exists'))
		return redirect(url_for('selfservice.index'))

	secret = email.start_verification()
	db.session.add(email)
	db.session.commit()
	if not sendmail(email.address, 'Mail verification', 'selfservice/mailverification.mail.txt', user=request.user, email=email, secret=secret):
		flash(_('E-Mail to "%(mail_address)s" could not be sent!', mail_address=email.address))
	else:
		flash(_('We sent you an email, please verify your mail address.'))
	return redirect(url_for('selfservice.index'))

@bp.route("/email/<int:email_id>/verify/<secret>")
@bp.route("/token/mail_verification/<int:legacy_id>/<secret>")
@login_required(selfservice_acl_check)
def verify_email(secret, email_id=None, legacy_id=None):
	if email_id is not None:
		email = UserEmail.query.get(email_id)
	else:
		email = UserEmail.query.filter_by(verification_legacy_id=legacy_id).one()
	if not email or email.verification_expired:
		flash(_('Link invalid or expired'))
		return redirect(url_for('selfservice.index'))
	if email.user != request.user:
		abort(403, description=_('This link was generated for another user. Login as the correct user to continue.'))
	if not email.finish_verification(secret):
		flash(_('Link invalid or expired'))
		return redirect(url_for('selfservice.index'))
	if legacy_id is not None:
		request.user.primary_email = email
	try:
		db.session.commit()
	except IntegrityError:
		flash(_('E-Mail address is already used by another account'))
		return redirect(url_for('selfservice.index'))
	flash(_('E-Mail address verified'))
	return redirect(url_for('selfservice.index'))

@bp.route("/email/<int:email_id>/retry")
@login_required(selfservice_acl_check)
@csrf_protect(blueprint=bp)
def retry_email_verification(email_id):
	email = UserEmail.query.filter_by(id=email_id, user=request.user, verified=False).first_or_404()
	secret = email.start_verification()
	db.session.commit()
	if not sendmail(email.address, 'E-Mail verification', 'selfservice/mailverification.mail.txt', user=request.user, email=email, secret=secret):
		flash(_('E-Mail to "%(mail_address)s" could not be sent!', mail_address=email.address))
	else:
		flash(_('We sent you an email, please verify your mail address.'))
	return redirect(url_for('selfservice.index'))

@bp.route("/email/<int:email_id>/delete", methods=['POST', 'GET'])
@login_required(selfservice_acl_check)
@csrf_protect(blueprint=bp)
def delete_email(email_id):
	email = UserEmail.query.filter_by(id=email_id, user=request.user).first_or_404()
	try:
		db.session.delete(email)
		db.session.commit()
	except IntegrityError:
		flash(_('Cannot delete primary e-mail address'))
		return redirect(url_for('selfservice.index'))
	flash(_('E-Mail address deleted'))
	return redirect(url_for('selfservice.index'))

@bp.route("/email/preferences", methods=['POST'])
@login_required(selfservice_acl_check)
@csrf_protect(blueprint=bp)
def update_email_preferences():
	verified_emails = UserEmail.query.filter_by(user=request.user, verified=True)
	request.user.primary_email = verified_emails.filter_by(id=request.form['primary_email']).one()
	if request.form['recovery_email'] == 'primary':
		request.user.recovery_email = None
	else:
		request.user.recovery_email = verified_emails.filter_by(id=request.form['recovery_email']).one()
	for service_user in request.user.service_users:
		if not service_user.has_email_preferences:
			continue
		value = request.form.get(f'service_{service_user.service.id}_email', 'primary')
		if value == 'primary':
			service_user.service_email = None
		else:
			service_user.service_email = verified_emails.filter_by(id=value).one()
	db.session.commit()
	flash(_('E-Mail preferences updated'))
	return redirect(url_for('selfservice.index'))

@bp.route("/session/<int:session_id>/revoke", methods=(['POST']))
@csrf_protect(blueprint=bp)
@login_required(selfservice_acl_check)
def revoke_session(session_id):
	_session = Session.query.filter_by(id=session_id, user=request.user).first_or_404()
	db.session.delete(_session)
	db.session.commit()
	flash(_('Session revoked'))
	return redirect(url_for('selfservice.index'))

@bp.route("/leaverole/<int:roleid>", methods=(['POST']))
@csrf_protect(blueprint=bp)
@login_required(selfservice_acl_check)
def leave_role(roleid):
	role = Role.query.get_or_404(roleid)
	role.members.remove(request.user)
	request.user.update_groups()
	db.session.commit()
	flash(_('You left role %(role_name)s', role_name=role.name))
	return redirect(url_for('selfservice.index'))

def send_passwordreset(user, new=False):
	PasswordToken.query.filter(PasswordToken.user == user).delete()
	token = PasswordToken(user=user)
	db.session.add(token)
	db.session.commit()

	if new:
		template = 'selfservice/newuser.mail.txt'
		subject = 'Welcome to the %s infrastructure'%current_app.config.get('ORGANISATION_NAME', '')
	else:
		template = 'selfservice/passwordreset.mail.txt'
		subject = 'Password reset'

	email = user.recovery_email or user.primary_email
	if not sendmail(email.address, subject, template, user=user, token=token):
		flash(_('E-Mail to "%(mail_address)s" could not be sent!', mail_address=email.address))

@bp.route('/mfa/', methods=['GET'])
@login_required(selfservice_acl_check)
def setup_mfa():
	return render_template('selfservice/setup_mfa.html')

@bp.route('/mfa/setup/disable', methods=['GET'])
@login_required(selfservice_acl_check)
def disable_mfa():
	return render_template('selfservice/disable_mfa.html')

@bp.route('/mfa/setup/disable', methods=['POST'])
@login_required(selfservice_acl_check)
@csrf_protect(blueprint=bp)
def disable_mfa_confirm():
	MFAMethod.query.filter_by(user=request.user).delete()
	db.session.commit()
	request.user.update_groups()
	db.session.commit()
	return redirect(url_for('selfservice.setup_mfa'))

@bp.route('/mfa/setup/recovery', methods=['POST'])
@login_required(selfservice_acl_check)
@csrf_protect(blueprint=bp)
def setup_mfa_recovery():
	for method in RecoveryCodeMethod.query.filter_by(user=request.user).all():
		db.session.delete(method)
	methods = []
	for _ in range(10):
		method = RecoveryCodeMethod(request.user)
		methods.append(method)
		db.session.add(method)
	db.session.commit()
	return render_template('selfservice/setup_mfa_recovery.html', methods=methods)

@bp.route('/mfa/setup/totp', methods=['GET'])
@login_required(selfservice_acl_check)
def setup_mfa_totp():
	method = TOTPMethod(request.user)
	session['mfa_totp_key'] = method.key
	return render_template('selfservice/setup_mfa_totp.html', method=method, name=request.values['name'])

@bp.route('/mfa/setup/totp', methods=['POST'])
@login_required(selfservice_acl_check)
@csrf_protect(blueprint=bp)
def setup_mfa_totp_finish():
	if not RecoveryCodeMethod.query.filter_by(user=request.user).all():
		flash(_('Generate recovery codes first!'))
		return redirect(url_for('selfservice.setup_mfa'))
	method = TOTPMethod(request.user, name=request.values['name'], key=session.pop('mfa_totp_key'))
	if method.verify(request.form['code']):
		db.session.add(method)
		request.user.update_groups()
		db.session.commit()
		return redirect(url_for('selfservice.setup_mfa'))
	flash(_('Code is invalid'))
	return redirect(url_for('selfservice.setup_mfa_totp', name=request.values['name']))

@bp.route('/mfa/setup/totp/<int:id>/delete')
@login_required(selfservice_acl_check)
@csrf_protect(blueprint=bp)
def delete_mfa_totp(id): #pylint: disable=redefined-builtin
	method = TOTPMethod.query.filter_by(user=request.user, id=id).first_or_404()
	db.session.delete(method)
	request.user.update_groups()
	db.session.commit()
	return redirect(url_for('selfservice.setup_mfa'))

bp.add_app_template_global(WEBAUTHN_SUPPORTED, name='webauthn_supported')

if WEBAUTHN_SUPPORTED:
	@bp.route('/mfa/setup/webauthn/begin', methods=['POST'])
	@login_required(selfservice_acl_check)
	@csrf_protect(blueprint=bp)
	def setup_mfa_webauthn_begin():
		if not RecoveryCodeMethod.query.filter_by(user=request.user).all():
			abort(403)
		methods = WebauthnMethod.query.filter_by(user=request.user).all()
		creds = [method.cred for method in methods]
		server = get_webauthn_server()
		registration_data, state = server.register_begin(
			{
				"id": str(request.user.id).encode(),
				"name": request.user.loginname,
				"displayName": request.user.displayname,
			},
			creds,
			user_verification='discouraged',
		)
		session["webauthn-state"] = state
		return cbor.encode(registration_data)

	@bp.route('/mfa/setup/webauthn/complete', methods=['POST'])
	@login_required(selfservice_acl_check)
	@csrf_protect(blueprint=bp)
	def setup_mfa_webauthn_complete():
		server = get_webauthn_server()
		data = cbor.decode(request.get_data())
		client_data = ClientData(data["clientDataJSON"])
		att_obj = AttestationObject(data["attestationObject"])
		auth_data = server.register_complete(session["webauthn-state"], client_data, att_obj)
		method = WebauthnMethod(request.user, auth_data.credential_data, name=data['name'])
		db.session.add(method)
		request.user.update_groups()
		db.session.commit()
		return cbor.encode({"status": "OK"})

@bp.route('/mfa/setup/webauthn/<int:id>/delete')
@login_required(selfservice_acl_check)
@csrf_protect(blueprint=bp)
def delete_mfa_webauthn(id): #pylint: disable=redefined-builtin
	method = WebauthnMethod.query.filter_by(user=request.user, id=id).first_or_404()
	db.session.delete(method)
	request.user.update_groups()
	db.session.commit()
	return redirect(url_for('selfservice.setup_mfa'))
