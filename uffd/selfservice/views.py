import datetime

import smtplib
from email.message import EmailMessage

from flask import Blueprint, render_template, request, url_for, redirect, flash, current_app

from uffd.navbar import register_navbar
from uffd.csrf import csrf_protect
from uffd.user.models import User
from uffd.session import get_current_user, login_required, is_valid_session
from uffd.ldap import loginname_to_dn
from uffd.selfservice.models import PasswordToken, MailToken
from uffd.database import db

bp = Blueprint("selfservice", __name__, template_folder='templates', url_prefix='/self/')

@bp.route("/")
@register_navbar('Selfservice', icon='portrait', blueprint=bp, visible=is_valid_session)
@login_required()
def self_index():
	return render_template('self.html', user=get_current_user())

@bp.route("/update", methods=(['POST']))
@csrf_protect(blueprint=bp)
@login_required()
def self_update():
	user = get_current_user()
	if request.values['displayname'] != user.displayname:
		if user.set_displayname(request.values['displayname']):
			flash('Display name changed.')
		else:
			flash('Display name is not valid.')
	if request.values['password1']:
		if not request.values['password1'] == request.values['password2']:
			flash('Passwords do not match')
		else:
			if user.set_password(request.values['password1']):
				flash('Password changed.')
			else:
				flash('Password could not be set.')
	if request.values['mail'] != user.mail:
		send_mail_verification(user.loginname, request.values['mail'])
		flash('We sent you an email, please verify your mail address.')
	user.to_ldap()
	return redirect(url_for('.self_index'))

@bp.route("/passwordreset", methods=(['GET', 'POST']))
@csrf_protect(blueprint=bp)
def self_forgot_password():
	if request.method == 'GET':
		return render_template('forgot_password.html')

	loginname = request.values['loginname']
	mail = request.values['mail']
	flash("We sent a mail to this users mail address if you entered the correct mail and login name combination")
	user = User.from_ldap_dn(loginname_to_dn(loginname))
	if user and user.mail == mail:
		send_passwordreset(loginname)
	return redirect(url_for('session.login'))

@bp.route("/token/password/<token>", methods=(['POST', 'GET']))
def self_token_password(token):
	session = db.session
	dbtoken = PasswordToken.query.get(token)
	if not dbtoken or dbtoken.created < (datetime.datetime.now() - datetime.timedelta(days=2)):
		flash('Token expired, please try again.')
		if dbtoken:
			session.delete(dbtoken)
			session.commit()
		return redirect(url_for('session.login'))
	if not 'loginname' in request.values:
		flash('Please set a new password.')
		return render_template('set_password.html', token=token)
	if not request.values['loginname'] == dbtoken.loginname:
		flash('That is not the correct login name for this token. Your token is now invalide. Please start the password reset process again')
		session.delete(dbtoken)
		session.commit()
		return redirect(url_for('session.login'))
	if not request.values['password1']:
		flash('Please specify a new password.')
		return render_template('set_password.html', token=token)
	user = User.from_ldap_dn(loginname_to_dn(dbtoken.loginname))
	user.set_password(request.values['password1'])
	user.to_ldap()
	flash('New password set')
	session.delete(dbtoken)
	session.commit()
	return redirect(url_for('session.login'))

@bp.route("/token/mail_verification/<token>")
@login_required()
def self_token_mail(token):
	session = db.session
	dbtoken = MailToken.query.get(token)
	if not dbtoken or dbtoken.created < (datetime.datetime.now() - datetime.timedelta(days=2)):
		flash('Token expired, please try again.')
		if dbtoken:
			session.delete(dbtoken)
			session.commit()
		return redirect(url_for('.self_index'))

	user = User.from_ldap_dn(loginname_to_dn(dbtoken.loginname))
	user.set_mail(dbtoken.newmail)
	user.to_ldap()
	flash('New mail set')
	session.delete(dbtoken)
	session.commit()
	return redirect(url_for('.self_index'))

def send_mail_verification(loginname, newmail):
	session = db.session
	expired_tokens = MailToken.query.filter(MailToken.created < (datetime.datetime.now() - datetime.timedelta(days=2))).all()
	for i in expired_tokens:
		session.delete(i)
	token = MailToken()
	token.loginname = loginname
	token.newmail = newmail
	session.add(token)
	session.commit()

	user = User.from_ldap_dn(loginname_to_dn(loginname))

	msg = EmailMessage()
	msg.set_content(render_template('mailverification.mail.txt', user=user, token=token.token))
	msg['Subject'] = 'Mail verification'
	send_mail(newmail, msg)

def send_passwordreset(loginname):
	session = db.session
	expired_tokens = PasswordToken.query.filter(PasswordToken.created < (datetime.datetime.now() - datetime.timedelta(days=2))).all()
	for i in expired_tokens:
		session.delete(i)
	token = PasswordToken()
	token.loginname = loginname
	session.add(token)
	session.commit()

	user = User.from_ldap_dn(loginname_to_dn(loginname))

	msg = EmailMessage()
	msg.set_content(render_template('passwordreset.mail.txt', user=user, token=token.token))
	msg['Subject'] = 'Password reset'
	send_mail(user.mail, msg)

def send_mail(to_address, msg):
	server = smtplib.SMTP(host=current_app.config['MAIL_SERVER'], port=current_app.config['MAIL_PORT'])
	if current_app.config['MAIL_USE_STARTTLS']:
		server.starttls()
	server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
	msg['From'] = current_app.config['MAIL_FROM_ADDRESS']
	msg['To'] = to_address
	server.send_message(msg)
	server.quit()
