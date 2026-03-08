import functools
import secrets

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_babel import gettext as _

from uffd.sendmail import sendmail
from uffd.database import db
from uffd.models import User, Signup, Ratelimit, host_ratelimit, format_delay
from .session import set_session

bp = Blueprint('signup', __name__, template_folder='templates', url_prefix='/signup/')

signup_ratelimit = Ratelimit('signup', 24*60, 3)
confirm_ratelimit = Ratelimit('signup_confirm', 10*60, 3)

def signup_enabled(func):
	@functools.wraps(func)
	def decorator(*args, **kwargs):
		if not current_app.config['SELF_SIGNUP']:
			flash(_('Sign-up not enabled'))
			return redirect(url_for('index'))
		return func(*args, **kwargs)
	return decorator

@bp.route('/')
@signup_enabled
def signup_start():
	return render_template('signup/start.html')

@bp.route('/check', methods=['POST'])
@signup_enabled
def signup_check():
	if host_ratelimit.get_delay():
		return jsonify({'status': 'ratelimited'})
	host_ratelimit.log()
	if not User().set_loginname(request.form['loginname']):
		return jsonify({'status': 'invalid'})
	if User.query.filter_by(loginname=request.form['loginname']).all():
		return jsonify({'status': 'exists'})
	return jsonify({'status': 'ok'})

@bp.route('/', methods=['POST'])
@signup_enabled
def signup_submit():
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
	signup = Signup(loginname=request.form['loginname'],
	                displayname=request.form['displayname'],
	                mail=request.form['mail'])
	# If the password is invalid, signup.set_password returns False and does not
	# set signup.password. We don't need to check the return value here, because
	# we call signup.verify next and that checks if signup.password is set.
	signup.set_password(request.form['password1'])
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

# signup_confirm* views are always accessible so other modules (e.g. invite) can reuse them
@bp.route('/confirm/<int:signup_id>/<token>')
def signup_confirm(signup_id, token):
	signup = Signup.query.get(signup_id)
	if not signup or not secrets.compare_digest(signup.token, token) or signup.expired or signup.completed:
		flash(_('Invalid sign-up link'))
		return redirect(url_for('index'))
	return render_template('signup/confirm.html', signup=signup)

@bp.route('/confirm/<int:signup_id>/<token>', methods=['POST'])
def signup_confirm_submit(signup_id, token):
	signup = Signup.query.get(signup_id)
	if not signup or not secrets.compare_digest(signup.token, token) or signup.expired or signup.completed:
		flash(_('Invalid sign-up link'))
		return redirect(url_for('index'))
	confirm_delay = confirm_ratelimit.get_delay(token)
	host_delay = host_ratelimit.get_delay()
	if confirm_delay and confirm_delay > host_delay:
		flash(_('Too many failed attempts! Please wait %(delay)s.', delay=format_delay(confirm_delay)), 'error')
		return render_template('signup/confirm.html', signup=signup)
	if host_delay:
		return render_template('signup/confirm.html', signup=signup)
	if not signup.password.verify(request.form['password']):
		host_ratelimit.log()
		confirm_ratelimit.log(token)
		flash(_('Wrong password'), 'error')
		return render_template('signup/confirm.html', signup=signup)
	user, msg = signup.finish(request.form['password'])
	if user is None:
		db.session.rollback()
		flash(msg, 'error')
		return render_template('signup/confirm.html', signup=signup)
	db.session.commit()
	set_session(user)
	flash(_('Your account was successfully created'))
	return redirect(url_for('index'))
