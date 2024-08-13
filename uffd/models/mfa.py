import enum
import datetime
import secrets
# imports for totp
import time
import struct
import hmac
import hashlib
import base64
import urllib.parse
from flask import request, current_app
from sqlalchemy import Column, Integer, Enum, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship, backref

from uffd.utils import nopad_b32decode, nopad_b32encode
from uffd.password_hash import PasswordHashAttribute, CryptPasswordHash
from uffd.database import db
from .user import User

User.mfa_recovery_codes = relationship('RecoveryCodeMethod', viewonly=True)
User.mfa_totp_methods = relationship('TOTPMethod', viewonly=True)
User.mfa_webauthn_methods = relationship('WebauthnMethod', viewonly=True)
User.mfa_enabled = property(lambda user: bool(user.mfa_totp_methods or user.mfa_webauthn_methods))

class MFAType(enum.Enum):
	RECOVERY_CODE = 0
	TOTP = 1
	WEBAUTHN = 2

class MFAMethod(db.Model):
	__tablename__ = 'mfa_method'
	id = Column(Integer(), primary_key=True, autoincrement=True)
	type = Column(Enum(MFAType, create_constraint=True), nullable=False)
	created = Column(DateTime(), nullable=False, default=datetime.datetime.utcnow)
	name = Column(String(128))
	user_id = Column(Integer(), ForeignKey('user.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	user = relationship('User', backref=backref('mfa_methods', cascade='all, delete-orphan'))

	__mapper_args__ = {
		'polymorphic_on': type,
	}

	def __init__(self, user, name=None):
		self.user = user
		self.name = name
		self.created = datetime.datetime.utcnow()

class RecoveryCodeMethod(MFAMethod):
	_code = Column('recovery_hash', String(256))
	code = PasswordHashAttribute('_code', CryptPasswordHash)

	__mapper_args__ = {
		'polymorphic_identity': MFAType.RECOVERY_CODE
	}

	def __init__(self, user):
		super().__init__(user, None)
		# self.code_value is not stored and only available on freshly initiated objects
		self.code = self.code_value = secrets.token_hex(8).replace(' ', '').lower()

	def verify(self, code):
		return self.code.verify(code.replace(' ', '').lower())

def _hotp(counter, key, digits=6):
	'''Generates HMAC-based one-time password according to RFC4226

	:param counter: Positive integer smaller than 2**64
	:param key: Bytes object of arbitrary length (should be at least 160 bits)
	:param digits: Length of resulting value (integer between 1 and 9, minimum of 6 is recommended)

	:returns: String object representing human-readable HOTP value'''
	msg = struct.pack('>Q', counter)
	digest = hmac.new(key, msg=msg, digestmod=hashlib.sha1).digest()
	offset = digest[19] & 0x0f
	snum = struct.unpack('>L', digest[offset:offset+4])[0] & 0x7fffffff
	return str(snum % (10**digits)).zfill(digits)

class TOTPMethod(MFAMethod):
	key = Column('totp_key', String(64))
	last_counter = Column('totp_last_counter', Integer())

	__mapper_args__ = {
		'polymorphic_identity': MFAType.TOTP
	}

	def __init__(self, user, name=None, key=None):
		super().__init__(user, name)
		if key is None:
			key = nopad_b32encode(secrets.token_bytes(16)).decode()
		self.key = key

	@property
	def raw_key(self):
		return nopad_b32decode(self.key)

	@property
	def issuer(self):
		return urllib.parse.urlsplit(request.url).hostname

	@property
	def accountname(self):
		return self.user.loginname

	@property
	def key_uri(self):
		issuer = urllib.parse.quote(self.issuer)
		accountname = urllib.parse.quote(self.accountname)
		params = {'secret': self.key, 'issuer': issuer}
		if 'MFA_ICON_URL' in current_app.config:
			params['image'] = current_app.config['MFA_ICON_URL']
		return 'otpauth://totp/%s:%s?%s'%(issuer, accountname, urllib.parse.urlencode(params))

	def verify(self, code):
		'''Verify that code is valid

		Code verification must be rate-limited!

		:param code: String of digits (as entered by the user)

		:returns: True if code is valid, False otherwise'''
		current_counter = int(time.time()/30)
		for counter in (current_counter - 1, current_counter):
			if counter > (self.last_counter or 0):
				valid_code = _hotp(counter, self.raw_key)
				if secrets.compare_digest(code, valid_code):
					self.last_counter = counter
					return True
		return False

class WebauthnMethod(MFAMethod):
	_cred = Column('webauthn_cred', Text())

	__mapper_args__ = {
		'polymorphic_identity': MFAType.WEBAUTHN
	}

	def __init__(self, user, cred, name=None):
		super().__init__(user, name)
		self.cred = cred

	@property
	def cred(self):
		from uffd.fido2_compat import AttestedCredentialData #pylint: disable=import-outside-toplevel
		return AttestedCredentialData(base64.b64decode(self._cred))

	@cred.setter
	def cred(self, newcred):
		self._cred = base64.b64encode(bytes(newcred))
