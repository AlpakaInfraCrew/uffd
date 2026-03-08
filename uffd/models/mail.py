import re

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.associationproxy import association_proxy

from uffd.database import db

class Mail(db.Model):
	# Aliases are looked up by receiver addresses with api.getmails. To emulate
	# the pre-v2/LDAP behavior, the lookup needs to be case-insensitive. To not
	# rely on database-specific behavior, we ensure that all receiver addresses
	# are stored lower-case and convert incoming addresses in api.getmails to
	# lower-case. Note that full emulation of LDAP behavior would also require
	# whitespace normalization. Instead we disallow spaces in receiver addresses.

	# Match ASCII code points 33 (!) to 64 (@) and 91 ([) to 126 (~), i.e. any
	# number of lower-case ASCII letters, digits, symbols
	RECEIVER_REGEX = '[!-@[-~]*'
	RECEIVER_REGEX_COMPILED = re.compile(RECEIVER_REGEX)

	__tablename__ = 'mail'
	id = Column(Integer(), primary_key=True, autoincrement=True)
	uid = Column(String(32), unique=True, nullable=False)
	_receivers = relationship('MailReceiveAddress', cascade='all, delete-orphan')
	receivers = association_proxy('_receivers', 'address')
	_destinations = relationship('MailDestinationAddress', cascade='all, delete-orphan')
	destinations = association_proxy('_destinations', 'address')

	@property
	def invalid_receivers(self):
		return [addr for addr in self.receivers if not re.fullmatch(self.RECEIVER_REGEX_COMPILED, addr)]

class MailReceiveAddress(db.Model):
	__tablename__ = 'mail_receive_address'
	id = Column(Integer(), primary_key=True, autoincrement=True)
	mail_id = Column(Integer(), ForeignKey('mail.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	address = Column(String(128), nullable=False)

	def __init__(self, address):
		self.address = address

class MailDestinationAddress(db.Model):
	__tablename__ = 'mail_destination_address'
	id = Column(Integer(), primary_key=True, autoincrement=True)
	mail_id = Column(Integer(), ForeignKey('mail.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	address = Column(String(128), nullable=False)

	def __init__(self, address):
		self.address = address
