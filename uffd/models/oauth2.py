import datetime
import json
import secrets
import base64

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
import jwt

from uffd.database import db, CommaSeparatedList
from uffd.tasks import cleanup_task
from uffd.password_hash import PasswordHashAttribute, HighEntropyPasswordHash
from uffd.utils import token_urlfriendly
from .session import DeviceLoginInitiation, DeviceLoginType
from .service import ServiceUser

# pyjwt v1.7.x compat (Buster/Bullseye)
if not hasattr(jwt, 'get_algorithm_by_name'):
	jwt.get_algorithm_by_name = lambda name: jwt.algorithms.get_default_algorithms()[name]

class OAuth2Client(db.Model):
	__tablename__ = 'oauth2client'
	# Inconsistently named "db_id" instead of "id" because of the naming conflict
	# with "client_id" in the OAuth2 standard
	db_id = Column(Integer, primary_key=True, autoincrement=True)

	service_id = Column(Integer, ForeignKey('service.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	service = relationship('Service', back_populates='oauth2_clients')

	client_id = Column(String(40), unique=True, nullable=False)
	_client_secret = Column('client_secret', Text(), nullable=False)
	client_secret = PasswordHashAttribute('_client_secret', HighEntropyPasswordHash)
	_redirect_uris = relationship('OAuth2RedirectURI', cascade='all, delete-orphan')
	redirect_uris = association_proxy('_redirect_uris', 'uri')
	logout_uris = relationship('OAuth2LogoutURI', cascade='all, delete-orphan')

	@property
	def default_redirect_uri(self):
		return self.redirect_uris[0] if len(self.redirect_uris) == 1 else None

	def access_allowed(self, user):
		service_user = ServiceUser.query.get((self.service_id, user.id))
		return service_user and service_user.has_access

	@property
	def logout_uris_json(self):
		return json.dumps([[item.method, item.uri] for item in self.logout_uris])

class OAuth2RedirectURI(db.Model):
	__tablename__ = 'oauth2redirect_uri'
	id = Column(Integer, primary_key=True, autoincrement=True)
	client_db_id = Column(Integer, ForeignKey('oauth2client.db_id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	uri = Column(String(255), nullable=False)

	def __init__(self, uri):
		self.uri = uri

class OAuth2LogoutURI(db.Model):
	__tablename__ = 'oauth2logout_uri'
	id = Column(Integer, primary_key=True, autoincrement=True)
	client_db_id = Column(Integer, ForeignKey('oauth2client.db_id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	method = Column(String(40), nullable=False, default='GET')
	uri = Column(String(255), nullable=False)

@cleanup_task.delete_by_attribute('expired')
class OAuth2Grant(db.Model):
	__tablename__ = 'oauth2grant'
	id = Column(Integer, primary_key=True, autoincrement=True)

	EXPIRES_IN = 100
	expires = Column(DateTime, nullable=False, default=lambda: datetime.datetime.utcnow() + datetime.timedelta(seconds=OAuth2Grant.EXPIRES_IN))

	session_id = Column(Integer(), ForeignKey('session.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	session = relationship('Session')

	client_db_id = Column(Integer, ForeignKey('oauth2client.db_id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	client = relationship('OAuth2Client')

	_code = Column('code', String(255), nullable=False, default=token_urlfriendly)
	code = property(lambda self: f'{self.id}-{self._code}')
	redirect_uri = Column(String(255), nullable=True)
	nonce = Column(Text(), nullable=True)
	scopes = Column('_scopes', CommaSeparatedList(), nullable=False, default=tuple())

	_claims = Column('claims', Text(), nullable=False, default='{}')

	@property
	def claims(self):
		return json.loads(self._claims)

	@claims.setter
	def claims(self, value):
		assert isinstance(value, dict)
		self._claims = json.dumps(value)

	@property
	def service_user(self):
		return ServiceUser.query.get((self.client.service_id, self.session.user_id))

	@hybrid_property
	def expired(self):
		if self.expires is None:
			return False
		return self.expires < datetime.datetime.utcnow()

	@classmethod
	def get_by_authorization_code(cls, code):
		# pylint: disable=protected-access
		if '-' not in code:
			return None
		grant_id, grant_code = code.split('-', 2)
		grant = cls.query.filter_by(id=grant_id, expired=False).first()
		if not grant or not secrets.compare_digest(grant._code, grant_code):
			return None
		if grant.session.expired or grant.session.user.is_deactivated:
			return None
		if not grant.service_user or not grant.service_user.has_access:
			return None
		return grant

	def make_token(self, **kwargs):
		return OAuth2Token(
			session=self.session,
			client=self.client,
			scopes=self.scopes,
			claims=self.claims,
			**kwargs
		)

# OAuth2Token objects are cleaned-up when the session expires and is
# auto-deleted (or the user manually revokes it).
class OAuth2Token(db.Model):
	__tablename__ = 'oauth2token'
	id = Column(Integer, primary_key=True, autoincrement=True)

	EXPIRES_IN = 3600
	expires = Column(DateTime, nullable=False, default=lambda: datetime.datetime.utcnow() + datetime.timedelta(seconds=OAuth2Token.EXPIRES_IN))

	session_id = Column(Integer(), ForeignKey('session.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	session = relationship('Session')

	client_db_id = Column(Integer, ForeignKey('oauth2client.db_id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	client = relationship('OAuth2Client')

	# currently only bearer is supported
	token_type = Column(String(40), nullable=False, default='bearer')
	_access_token = Column('access_token', String(255), unique=True, nullable=False, default=token_urlfriendly)
	access_token = property(lambda self: f'{self.id}-{self._access_token}')
	_refresh_token = Column('refresh_token', String(255), unique=True, nullable=False, default=token_urlfriendly)
	refresh_token = property(lambda self: f'{self.id}-{self._refresh_token}')
	scopes = Column('_scopes', CommaSeparatedList(), nullable=False, default=tuple())

	_claims = Column('claims', Text(), nullable=False, default='{}')

	@property
	def claims(self):
		return json.loads(self._claims)

	@claims.setter
	def claims(self, value):
		assert isinstance(value, dict)
		self._claims = json.dumps(value)

	@property
	def service_user(self):
		return ServiceUser.query.get((self.client.service_id, self.session.user_id))

	@hybrid_property
	def expired(self):
		return self.expires < datetime.datetime.utcnow()

	@classmethod
	def get_by_access_token(cls, access_token):
		# pylint: disable=protected-access
		if '-' not in access_token:
			return None
		token_id, token_secret = access_token.split('-', 2)
		token = cls.query.filter_by(id=token_id, expired=False).first()
		if not token or not secrets.compare_digest(token._access_token, token_secret):
			return None
		if token.session.expired or token.session.user.is_deactivated:
			return None
		if not token.service_user or not token.service_user.has_access:
			return None
		return token

class OAuth2DeviceLoginInitiation(DeviceLoginInitiation):
	__mapper_args__ = {
		'polymorphic_identity': DeviceLoginType.OAUTH2
	}
	client_db_id = Column('oauth2_client_db_id', Integer, ForeignKey('oauth2client.db_id', onupdate='CASCADE', ondelete='CASCADE'))
	client = relationship('OAuth2Client')

	@property
	def description(self):
		return self.client.service.name

class OAuth2Key(db.Model):
	__tablename__ = 'oauth2_key'
	id = Column(String(64), primary_key=True, default=token_urlfriendly)
	created = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
	active = Column(Boolean(create_constraint=False), default=True, nullable=False)
	algorithm = Column(String(32), nullable=False)
	private_key_jwk = Column(Text(), nullable=False)
	public_key_jwk = Column(Text(), nullable=False)

	def __init__(self, **kwargs):
		if kwargs.get('algorithm') and kwargs.get('private_key') \
				and not kwargs.get('private_key_jwk') \
				and not kwargs.get('public_key_jwk'):
			algorithm = jwt.get_algorithm_by_name(kwargs['algorithm'])
			private_key = kwargs.pop('private_key')
			kwargs['private_key_jwk'] = algorithm.to_jwk(private_key)
			kwargs['public_key_jwk'] = algorithm.to_jwk(private_key.public_key())
		super().__init__(**kwargs)

	@property
	def private_key(self):
		# pylint: disable=protected-access,import-outside-toplevel
		# cryptography performs expensive checks when loading RSA private keys.
		# Since we only load keys we generated ourselves with help of cryptography,
		# these checks are unnecessary.
		import cryptography.hazmat.backends.openssl
		cryptography.hazmat.backends.openssl.backend._rsa_skip_check_key = True
		res = jwt.get_algorithm_by_name(self.algorithm).from_jwk(self.private_key_jwk)
		cryptography.hazmat.backends.openssl.backend._rsa_skip_check_key = False
		return res

	@property
	def public_key(self):
		return jwt.get_algorithm_by_name(self.algorithm).from_jwk(self.public_key_jwk)

	@property
	def public_key_jwks_dict(self):
		res = json.loads(self.public_key_jwk)
		res['kid'] = self.id
		res['alg'] = self.algorithm
		res['use'] = 'sig'
		# RFC7517 4.3 "The "use" and "key_ops" JWK members SHOULD NOT be used together [...]"
		res.pop('key_ops', None)
		return res

	def encode_jwt(self, payload):
		if not self.active:
			raise jwt.exceptions.InvalidKeyError(f'Key {self.id} not active')
		res = jwt.encode(payload, key=self.private_key, algorithm=self.algorithm, headers={'kid': self.id})
		# pyjwt pre-v2 compat (Buster/Bullseye)
		if isinstance(res, bytes):
			res = res.decode()
		return res

	# Hash algorithm for at_hash/c_hash from OpenID Connect Core 1.0 section 3.1.3.6
	def oidc_hash(self, value):
		# pylint: disable=import-outside-toplevel
		from cryptography.hazmat.primitives import hashes
		from cryptography.hazmat.backends import default_backend # Only required for Buster
		hash_alg = jwt.get_algorithm_by_name(self.algorithm).hash_alg
		digest = hashes.Hash(hash_alg(), backend=default_backend())
		digest.update(value)
		return base64.urlsafe_b64encode(
			digest.finalize()[:hash_alg.digest_size // 2]
		).decode('ascii').rstrip('=')

	@classmethod
	def get_preferred_key(cls, algorithm='RS256'):
		return cls.query.filter_by(active=True, algorithm=algorithm).order_by(OAuth2Key.created.desc()).first()

	@classmethod
	def get_available_algorithms(cls):
		return ['RS256']

	@classmethod
	def decode_jwt(cls, data, algorithms=('RS256',), **kwargs):
		headers = jwt.get_unverified_header(data)
		if 'kid' not in headers:
			raise jwt.exceptions.InvalidKeyError('JWT without kid')
		kid = headers['kid']
		key = cls.query.get(kid)
		if not key:
			raise jwt.exceptions.InvalidKeyError(f'Key {kid} not found')
		if not key.active:
			raise jwt.exceptions.InvalidKeyError(f'Key {kid} not active')
		return jwt.decode(data, key=key.public_key, algorithms=algorithms, **kwargs)

	@classmethod
	def generate_rsa_key(cls, public_exponent=65537, key_size=3072):
		# pylint: disable=import-outside-toplevel
		from cryptography.hazmat.primitives.asymmetric import rsa
		from cryptography.hazmat.backends import default_backend # Only required for Buster
		return cls(algorithm='RS256', private_key=rsa.generate_private_key(public_exponent=public_exponent, key_size=key_size, backend=default_backend()))
