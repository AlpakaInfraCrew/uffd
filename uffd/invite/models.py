import secrets
import datetime

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from ldapalchemy.dbutils import DBRelationship

from uffd.database import db
from uffd.user.models import User
from uffd.signup.models import Signup

# pylint: disable=E1101
invite_roles = db.Table('invite_roles',
	Column('invite_token', String(128), ForeignKey('invite.token'), primary_key=True),
	Column('role_id', Integer, ForeignKey('role.id'), primary_key=True)
)

class Invite(db.Model):
	__tablename__ = 'invite'
	token = Column(String(128), primary_key=True, default=lambda: secrets.token_hex(20))
	created = Column(DateTime, default=datetime.datetime.now, nullable=False)
	valid_until = Column(DateTime, nullable=False)
	single_use = Column(Boolean, default=True, nullable=False)
	allow_signup = Column(Boolean, default=True, nullable=False)
	used = Column(Boolean, default=False, nullable=False)
	disabled = Column(Boolean, default=False, nullable=False)
	roles = relationship('Role', secondary=invite_roles)
	signups = relationship('InviteSignup', back_populates='invite', lazy=True)
	grants = relationship('InviteGrant', backref='invite', lazy=True)

	@property
	def expired(self):
		return datetime.datetime.now().replace(second=0, microsecond=0) > self.valid_until

	@property
	def voided(self):
		return self.single_use and self.used

	@property
	def active(self):
		return not self.disabled and not self.voided and not self.expired

	def disable(self):
		self.disabled = True

	def reset(self):
		self.disabled = False
		self.used = False

class InviteGrant(db.Model):
	__tablename__ = 'invite_grant'
	id = Column(Integer(), primary_key=True, autoincrement=True)
	invite_token = Column(String(128), ForeignKey('invite.token'), nullable=False)
	user_dn = Column(String(128), nullable=False)
	user = DBRelationship('user_dn', User)

	def apply(self):
		if not self.invite.active:
			return False, 'Invite link is invalid'
		if not self.invite.roles:
			return False, 'Invite link does not grant any roles'
		if set(self.invite.roles).issubset(self.user.roles):
			return False, 'Invite link does not grant any new roles'
		for role in self.invite.roles:
			self.user.roles.add(role)
		self.user.update_groups()
		self.invite.used = True
		return True, 'Success'

class InviteSignup(Signup):
	__tablename__ = 'invite_signup'
	token = Column(String(128), ForeignKey('signup.token'), primary_key=True)
	invite_token = Column(String(128), ForeignKey('invite.token'), nullable=False)
	invite = relationship('Invite', back_populates='signups')

	__mapper_args__ = {
		'polymorphic_identity': 'InviteSignup'
	}

	def validate(self):
		if not self.invite.active or not self.invite.allow_signup:
			return False, 'Invite link is invalid'
		return super().validate()

	def finish(self, password):
		if not self.invite.active or not self.invite.allow_signup:
			return None, 'Invite link is invalid'
		user, msg = super().finish(password)
		if user is not None:
			# super().finish() already added ROLES_BASEROLES
			for role in self.invite.roles:
				user.roles.add(role)
			user.update_groups()
			self.invite.used = True
		return user, msg
