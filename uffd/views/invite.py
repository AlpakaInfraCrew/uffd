import datetime
import secrets

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, abort
from flask_babel import gettext as _, lazy_gettext, to_utc
import sqlalchemy

from uffd.csrf import csrf_protect
from uffd.sendmail import sendmail
from uffd.navbar import register_navbar
from uffd.database import db
from uffd.models import Role, User, Group, Invite, InviteSignup, InviteGrant, host_ratelimit, format_delay
from .session import login_required
from .signup import signup_ratelimit
from .selfservice import selfservice_acl_check

bp = Blueprint('invite', __name__, template_folder='templates', url_prefix='/invite/')

def invite_acl_check():
	if not request.user:
		return False
	if request.user.is_in_group(current_app.config['ACL_ADMIN_GROUP']):
		return True
	if request.user.is_in_group(current_app.config['ACL_SIGNUP_GROUP']):
		return True
	if Role.query.join(Role.moderator_group).join(Group.members).filter(User.id==request.user.id).count():
		return True
	return False

def view_acl_filter(user):
	if user.is_in_group(current_app.config['ACL_ADMIN_GROUP']):
		return sqlalchemy.true()
	creator_filter = (Invite.creator == user)
	rolemod_filter = Invite.roles.any(Role.moderator_group.has(Group.id.in_([group.id for group in user.groups])))
	return creator_filter | rolemod_filter

def reset_acl_filter(user):
	if user.is_in_group(current_app.config['ACL_ADMIN_GROUP']):
		return sqlalchemy.true()
	return Invite.creator == user

@bp.route('/')
@register_navbar(lazy_gettext('Invites'), icon='link', blueprint=bp, visible=invite_acl_check)
@login_required(invite_acl_check)
def index():
	invites = Invite.query.filter(view_acl_filter(request.user)).all()
	return render_template('invite/list.html', invites=invites)

@bp.route('/new')
@login_required(invite_acl_check)
def new():
	if request.user.is_in_group(current_app.config['ACL_ADMIN_GROUP']):
		allow_signup = True
		roles = Role.query.all()
	else:
		allow_signup = request.user.is_in_group(current_app.config['ACL_SIGNUP_GROUP'])
		roles = Role.query.join(Role.moderator_group).join(Group.members).filter(User.id==request.user.id).all()
	return render_template('invite/new.html', roles=roles, allow_signup=allow_signup)

def parse_datetime_local_input(value):
	return to_utc(datetime.datetime.fromisoformat(value))

@bp.route('/new', methods=['POST'])
@login_required(invite_acl_check)
@csrf_protect(blueprint=bp)
def new_submit():
	invite = Invite(creator=request.user,
	                single_use=(request.values['single-use'] == '1'),
	                valid_until=parse_datetime_local_input(request.values['valid-until']),
	                allow_signup=(request.values.get('allow-signup', '0') == '1'))
	for key, value in request.values.items():
		if key.startswith('role-') and value == '1':
			invite.roles.append(Role.query.get(key[5:]))
	if invite.valid_until > datetime.datetime.utcnow() + datetime.timedelta(days=current_app.config['INVITE_MAX_VALID_DAYS']):
		flash(_('The "Expires After" date is too far in the future'))
		return new()
	if not invite.permitted:
		flash(_('You are not allowed to create invite links with these permissions'))
		return new()
	if not invite.allow_signup and not invite.roles:
		flash(_('Invite link must either allow signing up or grant at least one role'))
		return new()
	db.session.add(invite)
	db.session.commit()
	return redirect(url_for('invite.index'))

@bp.route('/<int:invite_id>/disable', methods=['POST'])
@login_required(invite_acl_check)
@csrf_protect(blueprint=bp)
def disable(invite_id):
	invite = Invite.query.filter(view_acl_filter(request.user)).filter_by(id=invite_id).first_or_404()
	invite.disable()
	db.session.commit()
	return redirect(url_for('.index'))

@bp.route('/<int:invite_id>/reset', methods=['POST'])
@login_required(invite_acl_check)
@csrf_protect(blueprint=bp)
def reset(invite_id):
	invite = Invite.query.filter(reset_acl_filter(request.user)).filter_by(id=invite_id).first_or_404()
	invite.reset()
	db.session.commit()
	return redirect(url_for('.index'))

@bp.route('/<int:invite_id>/<token>')
def use(invite_id, token):
	invite = Invite.query.get(invite_id)
	if not invite or not secrets.compare_digest(invite.token, token):
		abort(404)
	if not invite.active:
		flash(_('Invalid invite link'))
		return redirect('/')
	return render_template('invite/use.html', invite=invite)

@bp.route('/<int:invite_id>/<token>/grant', methods=['POST'])
@login_required(selfservice_acl_check)
@csrf_protect(blueprint=bp)
def grant(invite_id, token):
	invite = Invite.query.get(invite_id)
	if not invite or not secrets.compare_digest(invite.token, token):
		abort(404)
	invite_grant = InviteGrant(invite=invite, user=request.user)
	db.session.add(invite_grant)
	success, msg = invite_grant.apply()
	if not success:
		flash(msg)
		return redirect(url_for('selfservice.index'))
	db.session.commit()
	flash(_('Roles successfully updated'))
	return redirect(url_for('selfservice.index'))

@bp.url_defaults
def inject_invite_token(endpoint, values):
	if endpoint in ['invite.signup_submit', 'invite.signup_check']:
		if 'invite_id' in request.view_args:
			values['invite_id'] = request.view_args['invite_id']
		if 'token' in request.view_args:
			values['token'] = request.view_args['token']

@bp.route('/<int:invite_id>/<token>/signup')
def signup_start(invite_id, token):
	invite = Invite.query.get(invite_id)
	if not invite or not secrets.compare_digest(invite.token, token):
		abort(404)
	if not invite.active:
		flash(_('Invalid invite link'))
		return redirect('/')
	if not invite.allow_signup:
		flash(_('Invite link does not allow signing up'))
		return redirect('/')
	return render_template('signup/start.html')

@bp.route('/<int:invite_id>/<token>/signupcheck', methods=['POST'])
def signup_check(invite_id, token):
	if host_ratelimit.get_delay():
		return jsonify({'status': 'ratelimited'})
	host_ratelimit.log()
	invite = Invite.query.get(invite_id)
	if not invite or not secrets.compare_digest(invite.token, token):
		abort(404)
	if not invite.active or not invite.allow_signup:
		return jsonify({'status': 'error'}), 403
	if not User().set_loginname(request.form['loginname']):
		return jsonify({'status': 'invalid'})
	if User.query.filter_by(loginname=request.form['loginname']).all():
		return jsonify({'status': 'exists'})
	return jsonify({'status': 'ok'})

@bp.route('/<int:invite_id>/<token>/signup', methods=['POST'])
def signup_submit(invite_id, token):
	invite = Invite.query.get(invite_id)
	if not invite or not secrets.compare_digest(invite.token, token):
		abort(404)
	if request.form['password1'] != request.form['password2']:
		flash(_('Passwords do not match'), 'error')
		return render_template('signup/start.html')
	signup_delay = signup_ratelimit.get_delay(request.form['mail'])
	host_delay = host_ratelimit.get_delay()
	if signup_delay and signup_delay > host_delay:
		flash(_('Too many sign-up requests with this mail address! Please wait %(delay)s.',
		        delay=format_delay(signup_delay)), 'error')
		return render_template('signup/start.html')
	if host_delay:
		flash(_('Too many requests! Please wait %(delay)s.', delay=format_delay(host_delay)), 'error')
		return render_template('signup/start.html')
	host_ratelimit.log()
	signup = InviteSignup(invite=invite, loginname=request.form['loginname'],
	                      displayname=request.form['displayname'],
	                      mail=request.form['mail'],
	                      password=request.form['password1'])
	valid, msg = signup.validate()
	if not valid:
		flash(msg, 'error')
		return render_template('signup/start.html')
	db.session.add(signup)
	db.session.commit()
	sent = sendmail(signup.mail, 'Confirm your mail address', 'signup/mail.txt', signup=signup)
	if not sent:
		flash(_('Could not send mail'), 'error')
		return render_template('signup/start.html')
	signup_ratelimit.log(request.form['mail'])
	return render_template('signup/submitted.html', signup=signup)
