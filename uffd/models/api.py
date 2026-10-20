from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship

from uffd.database import db
from uffd.password_hash import PasswordHashAttribute, HighEntropyPasswordHash

class APIClient(db.Model):
	__tablename__ = 'api_client'
	id = Column(Integer, primary_key=True, autoincrement=True)
	service_id = Column(Integer, ForeignKey('service.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	service = relationship('Service', back_populates='api_clients')
	auth_username = Column(String(40), unique=True, nullable=False)
	_auth_password = Column('auth_password', Text(), nullable=False)
	auth_password = PasswordHashAttribute('_auth_password', HighEntropyPasswordHash)

	# Permissions are defined by adding an attribute named "perm_NAME"
	perm_users = Column(Boolean(create_constraint=True), default=False, nullable=False)
	perm_checkpassword = Column(Boolean(create_constraint=True), default=False, nullable=False)
	perm_remailer = Column(Boolean(create_constraint=True), default=False, nullable=False)
	perm_metrics = Column(Boolean(create_constraint=True), default=False, nullable=False)

	@classmethod
	def permission_exists(cls, name):
		return hasattr(cls, 'perm_'+name)

	def has_permission(self, name):
		return getattr(self, 'perm_' + name)
