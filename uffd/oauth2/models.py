from flask import current_app
from sqlalchemy import Column, Integer, String, DateTime, Text

from uffd.database import db
from uffd.user.models import User

class OAuth2Client:
	def __init__(self, client_id, client_secret, redirect_uris, required_group=None, logout_urls=None):
		self.client_id = client_id
		self.client_secret = client_secret
		# We only support the Authorization Code Flow for confidential (server-side) clients
		self.client_type = 'confidential'
		self.redirect_uris = redirect_uris
		self.default_scopes = ['profile']
		self.required_group = required_group
		self.logout_urls = []
		for url in (logout_urls or []):
			if isinstance(url, str):
				self.logout_urls.append(['GET', url])
			else:
				self.logout_urls.append(url)

	@classmethod
	def from_id(cls, client_id):
		return OAuth2Client(client_id, **current_app.config['OAUTH2_CLIENTS'][client_id])

	@property
	def default_redirect_uri(self):
		return self.redirect_uris[0]

	def access_allowed(self, user):
		if not self.required_group:
			return True
		user_groups = {group.name for group in user.get_groups()}
		group_sets = self.required_group
		if isinstance(group_sets, str):
			group_sets = [group_sets]
		for group_set in group_sets:
			if isinstance(group_set, str):
				group_set = [group_set]
			if set(group_set) - user_groups == set():
				return True
		return False

class OAuth2Grant(db.Model):
	__tablename__ = 'oauth2grant'
	id = Column(Integer, primary_key=True)

	user_dn = Column(String(128))

	@property
	def user(self):
		return User.from_ldap_dn(self.user_dn)

	@user.setter
	def user(self, newuser):
		self.user_dn = newuser.dn

	client_id = Column(String(40))

	@property
	def client(self):
		return OAuth2Client.from_id(self.client_id)

	@client.setter
	def client(self, newclient):
		self.client_id = newclient.client_id

	code = Column(String(255), index=True, nullable=False)
	redirect_uri = Column(String(255))
	expires = Column(DateTime)

	_scopes = Column(Text)
	@property
	def scopes(self):
		if self._scopes:
			return self._scopes.split()
		return []

	def delete(self):
		db.session.delete(self)
		db.session.commit()
		return self

class OAuth2Token(db.Model):
	__tablename__ = 'oauth2token'
	id = Column(Integer, primary_key=True)

	user_dn = Column(String(128))
	@property
	def user(self):
		return User.from_ldap_dn(self.user_dn)

	@user.setter
	def user(self, newuser):
		self.user_dn = newuser.dn

	client_id = Column(String(40))

	@property
	def client(self):
		return OAuth2Client.from_id(self.client_id)

	@client.setter
	def client(self, newclient):
		self.client_id = newclient.client_id

	# currently only bearer is supported
	token_type = Column(String(40))
	access_token = Column(String(255), unique=True)
	refresh_token = Column(String(255), unique=True)
	expires = Column(DateTime)

	_scopes = Column(Text)
	@property
	def scopes(self):
		if self._scopes:
			return self._scopes.split()
		return []

	def delete(self):
		db.session.delete(self)
		db.session.commit()
		return self
