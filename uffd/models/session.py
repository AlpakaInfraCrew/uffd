import datetime
import secrets
import enum

from flask import current_app
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from flask_babel import gettext as _

try:
	from ua_parser import user_agent_parser
	USER_AGENT_PARSER_SUPPORTED = True
except ImportError:
	USER_AGENT_PARSER_SUPPORTED = False

from uffd.database import db
from uffd.utils import token_typeable
from uffd.tasks import cleanup_task
from uffd.password_hash import PasswordHashAttribute, HighEntropyPasswordHash

@cleanup_task.delete_by_attribute('expired')
class Session(db.Model):
	__tablename__ = 'session'

	id = Column(Integer(), primary_key=True, autoincrement=True)
	_secret = Column('secret', Text)
	secret = PasswordHashAttribute('_secret', HighEntropyPasswordHash)

	user_id = Column(Integer(), ForeignKey('user.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	user = relationship('User', back_populates='sessions')
	oauth2_grants = relationship('OAuth2Grant', back_populates='session', cascade='all, delete-orphan')
	oauth2_tokens = relationship('OAuth2Token', back_populates='session', cascade='all, delete-orphan')

	created = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
	last_used = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
	user_agent = Column(Text, nullable=False, default='')
	ip_address = Column(Text)

	@hybrid_property
	def expired(self):
		if self.created is None or self.last_used is None:
			return False
		if self.created < datetime.datetime.utcnow() - datetime.timedelta(seconds=current_app.config['SESSION_LIFETIME_SECONDS']):
			return True
		if self.last_used < datetime.datetime.utcnow() - current_app.permanent_session_lifetime:
			return True
		return False

	@expired.expression
	def expired(cls): # pylint: disable=no-self-argument
		return db.or_(
			cls.created < datetime.datetime.utcnow() - datetime.timedelta(seconds=current_app.config['SESSION_LIFETIME_SECONDS']),
			cls.last_used < datetime.datetime.utcnow() - current_app.permanent_session_lifetime,
		)

	@property
	def user_agent_browser(self):
		# pylint: disable=too-many-return-statements
		if USER_AGENT_PARSER_SUPPORTED and not getattr(self, 'DISABLE_USER_AGENT_PARSER', False):
			family = user_agent_parser.ParseUserAgent(self.user_agent)['family']
			return family if family != 'Other' else _('Unknown')

		if ' OPR/' in self.user_agent:
			return 'Opera'
		if ' Edg/' in self.user_agent:
			return 'Microsoft Edge'
		if ' Safari/' in self.user_agent and ' Chrome/' not in self.user_agent:
			return 'Safari'
		if ' Chrome/' in self.user_agent:
			return 'Chrome'
		if ' Firefox/' in self.user_agent:
			return 'Firefox'
		return _('Unknown')

	@property
	def user_agent_platform(self):
		if USER_AGENT_PARSER_SUPPORTED and not getattr(self, 'DISABLE_USER_AGENT_PARSER', False):
			family = user_agent_parser.ParseOS(self.user_agent)['family']
			return family if family != 'Other' else _('Unknown')

		sysinfo = ([''] + self.user_agent.split('(', 1))[-1].split(')', 0)[0]
		platforms = [
			'Android', 'Linux', 'OpenBSD', 'FreeBSD', 'NetBSD', 'Windows', 'iPhone',
			'iPad', 'Macintosh',
		]
		for platform in platforms:
			if platform in sysinfo:
				return platform
		return _('Unknown')

# Device login provides a convenient and secure way to log into SSO-enabled
# services on a secondary device without entering the user password or
# completing 2FA challenges.
#
# Use-cases:
# * A user wants to log into a single OAuth2-enabled web service on his
#   mobile phone without trusting the device enough to expose his full
#   credentials.
# * A user wants to log into an OAuth2-enabled web service on a secondary
#   device at a busy event location with too little privacy to securely enter
#   his credentials but already has a login session on his laptop.
# * A user wants to log into an OAuth2-enabled service via the web browser
#   on a native mobile app on his phone and cannot use his 2FA method on that
#   device (e.g. FIDO2 token with USB-A) or in the app's web view.

# The mechanism uses two random codes: When the user attempts to authenticate
# with an SSO-enabled service and chooses the "Device Login" option on the SSO
# login page, the SSO generates and displays an initiation code. That code is
# securely bound to the browser session that is used to request it. The user
# logs into the SSO on another device using his credentials and 2FA methods and
# opens a page to authorize the device login attempt. There he enters the
# initiation code. The SSO displays the details of the device login attempt
# (i.e. the name of the service to log into). Once the user authorizes the
# login attempt, the SSO generates a confirmation code and displays it to the
# user. The user enters the confirmation code on the device he wants to log
# in with and proceeds with the authentication.
#
# An attacker might
# * generate initiation codes,
# * observe the displayed/entered initiation code,
# * observe the displayed/entered confirmation code and
# * possibly divert the victims attention and provoke typing errors.
#
# An attacker must not be able to
# * authenticate with an SSO-enabled service as another user or
# * trick a user to authenticate with an SSO-enabled service as the attacker.
#
# An example for the second case would be the Nextcloud mobile app: The app
# integrates closely with the phone's OS and provides features like
# auto-upload of photos, contacts and more. If the app would authenticate
# with an attacker-controlled account, the attacker would have access to
# this data.

class DeviceLoginType(enum.Enum):
	OAUTH2 = 0

@cleanup_task.delete_by_attribute('expired')
class DeviceLoginInitiation(db.Model):
	'''Abstract initiation code class

	An initiation code is generated and displayed when a user chooses
	"Device Login" on the login page. Instances are always bound to a
	specific service, e.g. a client id in case of OAuth2.

	The code attribute is formed out of two independently unique parts
	to ensure that at any time all existing codes differ in at least two
	characters (i.e. mistyping one character can not result in another
	existing and possibly attacker-controlled code).

	An initiation code is securely bound to the session that it was created
	with by storing both id and secret in the authenticated session cookie.'''
	__tablename__ = 'device_login_initiation'

	id = Column(Integer(), primary_key=True, autoincrement=True)
	type = Column(Enum(DeviceLoginType, create_constraint=True), nullable=False)
	code0 = Column(String(32), unique=True, nullable=False, default=lambda: token_typeable(3))
	code1 = Column(String(32), unique=True, nullable=False, default=lambda: token_typeable(3))
	secret = Column(String(128), nullable=False, default=lambda: secrets.token_hex(64))
	confirmations = relationship('DeviceLoginConfirmation', back_populates='initiation', cascade='all, delete-orphan')
	created = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

	__mapper_args__ = {
		'polymorphic_on': type,
	}

	@hybrid_property
	def code(self):
		# Split into two parts, each unique, to ensure that every code differs
		# in more than one character from other existing codes.
		return self.code0 + self.code1

	@hybrid_property
	def expired(self):
		if self.created is None:
			return False
		return self.created < datetime.datetime.utcnow() - datetime.timedelta(minutes=30)

	@property
	def description(self):
		raise NotImplementedError()

class DeviceLoginConfirmation(db.Model):
	'''Confirmation code class

	A confirmation code is generated and displayed when an authenticated user
	enters an initiation code and confirms the device login attempt. Every
	instance is bound to both an initiation code and a login session.

	The code attribute is formed out of two independently unique parts
	to ensure that at any time all existing codes differ in at least two
	characters (i.e. mistyping one character can not result in another
	existing and possibly attacker-controlled code).'''
	__tablename__ = 'device_login_confirmation'

	id = Column(Integer(), primary_key=True, autoincrement=True)
	initiation_id = Column(Integer(), ForeignKey('device_login_initiation.id',
	                       name='fk_device_login_confirmation_initiation_id_',
	                       onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	initiation = relationship('DeviceLoginInitiation', back_populates='confirmations')
	session_id = Column(Integer(), ForeignKey('session.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False, unique=True)
	session = relationship('Session')
	code0 = Column(String(32), nullable=False, default=lambda: token_typeable(1))
	code1 = Column(String(32), nullable=False, default=lambda: token_typeable(1))

	__table_args__ = (
		db.UniqueConstraint('initiation_id', 'code0', name='uq_device_login_confirmation_initiation_id_code0'),
		db.UniqueConstraint('initiation_id', 'code1', name='uq_device_login_confirmation_initiation_id_code1'),
	)

	@hybrid_property
	def code(self):
		# Split into two parts, each unique, to ensure that every code differs
		# in more than one character from other existing codes.
		return self.code0 + self.code1
