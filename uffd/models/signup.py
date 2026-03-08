import datetime

from flask_babel import gettext as _
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.hybrid import hybrid_property

from uffd.tasks import cleanup_task
from uffd.utils import token_urlfriendly
from uffd.password_hash import PasswordHashAttribute, LowEntropyPasswordHash
from uffd.database import db
from .user import User

@cleanup_task.delete_by_attribute('expired_and_not_completed')
class Signup(db.Model):
	'''Model that represents a self-signup request

	When a person tries to sign up, an instance with user-provided loginname,
	displayname, mail and password is created. Signup.validate is called to
	validate the request. To ensure that person is in control of the provided
	mail address, a mail with Signup.token is sent to that address. To complete
	the signup, Signup.finish is called with a user-provided password that must
	be equal to the initial password.

	Signup.token requires the password again so that a mistyped-but-valid mail
	address does not allow a third party to complete the signup procedure and
	set a new password with the (also mail-based) password reset functionality.

	As long as they are not completed, signup requests have no effect on each
	other or different parts of the application.'''
	__tablename__ = 'signup'
	id = Column(Integer(), primary_key=True, autoincrement=True)
	token = Column(String(128), default=token_urlfriendly, nullable=False)
	created = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
	loginname = Column(Text)
	displayname = Column(Text)
	mail = Column(Text)
	_password = Column('pwhash', Text)
	password = PasswordHashAttribute('_password', LowEntropyPasswordHash)
	user_id = Column(Integer(), ForeignKey('user.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=True, unique=True)
	user = relationship('User', backref=backref('signups', cascade='all, delete-orphan'))

	type = Column(String(50))
	__mapper_args__ = {
		'polymorphic_identity': 'Signup',
		'polymorphic_on': type
	}

	def set_password(self, value):
		if not User().set_password(value):
			return False
		self.password = value
		return True

	@hybrid_property
	def expired(self):
		if self.created is None:
			return False
		return self.created < datetime.datetime.utcnow() - datetime.timedelta(hours=48)

	@hybrid_property
	def completed(self):
		# pylint: disable=singleton-comparison
		return self.user_id != None

	@hybrid_property
	def expired_and_not_completed(self):
		return db.and_(self.expired, db.not_(self.completed))

	def validate(self): # pylint: disable=too-many-return-statements
		'''Return whether the signup request is valid and Signup.finish is likely to succeed

		:returns: Tuple (valid, errmsg), if the signup request is invalid, `valid`
		          is False and `errmsg` contains a string describing why. Otherwise
		          `valid` is True.'''
		if self.completed or self.expired:
			return False, _('Invalid sign-up request')
		if not User().set_loginname(self.loginname):
			return False, _('Login name is invalid')
		if not User().set_displayname(self.displayname):
			return False, _('Display name is invalid')
		if not User().set_primary_email_address(self.mail):
			return False, _('E-Mail address is invalid')
		if not self.password:
			return False, _('Invalid password')
		if User.query.filter_by(loginname=self.loginname).all():
			return False, _('A user with this login name already exists')
		return True, _('Valid')

	def finish(self, password):
		'''Complete the signup procedure and return the new user

		Signup.finish should only be called on an object that was (at some point)
		successfully validated with Signup.validate!

		:param password: User password

		:returns: Tuple (user, errmsg), if the operation fails, `user` is None and
		          `errmsg` contains a string describing why. Otherwise `user` is a
		          User object.'''
		if self.completed or self.expired:
			return None, _('Invalid sign-up request')
		if not self.password.verify(password):
			return None, _('Wrong password')
		if User.query.filter_by(loginname=self.loginname).all():
			return None, _('A user with this login name already exists')
		# Flush to make sure the flush below does not catch unrelated errors
		db.session.flush()
		user = User(loginname=self.loginname, displayname=self.displayname, primary_email_address=self.mail, password=self.password)
		db.session.add(user)
		try:
			db.session.flush()
		except IntegrityError:
			return None, _('Login name or e-mail address is already in use')
		user.update_groups() # pylint: disable=no-member
		self.user = user
		self.loginname = None
		self.displayname = None
		self.mail = None
		self.password = None
		return user, _('Success')
