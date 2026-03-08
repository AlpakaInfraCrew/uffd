import secrets
import hashlib
import base64
from crypt import crypt # pylint: disable=deprecated-module
import argon2

def build_value(method_name, data):
	return '{' + method_name + '}' + data

def parse_value(value):
	if value is not None and value.startswith('{') and '}' in value:
		method_name, data = value[1:].split('}', 1)
		return method_name.lower(), data
	raise ValueError('Invalid password hash')

class PasswordHashRegistry:
	'''Factory for creating objects of the correct PasswordHash subclass for a
	given password hash value'''

	def __init__(self):
		self.methods = {}

	def register(self, cls):
		assert cls.METHOD_NAME not in self.methods
		self.methods[cls.METHOD_NAME] = cls
		return cls

	def parse(self, value, **kwargs):
		method_name, _ = parse_value(value)
		method_cls = self.methods.get(method_name)
		if method_cls is None:
			raise ValueError(f'Unknown password hash method {method_name}')
		return method_cls(value, **kwargs)

registry = PasswordHashRegistry()

class PasswordHash:
	'''OpenLDAP-/NIS-style password hash

	Instances wrap password hash strings in the form "{METHOD_NAME}DATA".

	Allows gradual migration of password hashing methods by checking
	PasswordHash.needs_rehash every time the password is processed and rehashing
	it with PasswordHash.from_password if needed. For PasswordHash.needs_rehash
	to work, the PasswordHash subclass for the current password hashing method
	is instantiated with target_cls set to the PasswordHash subclass of the
	intended hashing method.

	Instances should be created with PasswordHashRegistry.parse to get the
	appropriate subclass based on the method name in a value.'''

	METHOD_NAME = None

	def __init__(self, value, target_cls=None):
		method_name, data = parse_value(value)
		if method_name != self.METHOD_NAME:
			raise ValueError('Invalid password hash')
		self.value = value
		self.data = data
		self.target_cls = target_cls or type(self)

	@classmethod
	def from_password(cls, password):
		raise NotImplementedError()

	def verify(self, password):
		raise NotImplementedError()

	@property
	def needs_rehash(self):
		return not isinstance(self, self.target_cls)

@registry.register
class PlaintextPasswordHash(PasswordHash):
	'''Pseudo password hash for passwords stored without hashing

	Should only be used for migration of existing plaintext passwords. Add the
	prefix "{plain}" for this.'''

	METHOD_NAME = 'plain'

	@classmethod
	def from_password(cls, password):
		return cls(build_value(cls.METHOD_NAME, password))

	def verify(self, password):
		return secrets.compare_digest(self.data, password)

class HashlibPasswordHash(PasswordHash):
	HASHLIB_ALGORITHM = None

	@classmethod
	def from_password(cls, password):
		ctx = hashlib.new(cls.HASHLIB_ALGORITHM, password.encode())
		return cls(build_value(cls.METHOD_NAME, base64.b64encode(ctx.digest()).decode()))

	def verify(self, password):
		digest = base64.b64decode(self.data.encode())
		ctx = hashlib.new(self.HASHLIB_ALGORITHM, password.encode())
		return secrets.compare_digest(digest, ctx.digest())

class SaltedHashlibPasswordHash(PasswordHash):
	HASHLIB_ALGORITHM = None

	@classmethod
	def from_password(cls, password):
		salt = secrets.token_bytes(8)
		ctx = hashlib.new(cls.HASHLIB_ALGORITHM)
		ctx.update(password.encode())
		ctx.update(salt)
		return cls(build_value(cls.METHOD_NAME, base64.b64encode(ctx.digest()+salt).decode()))

	def verify(self, password):
		data = base64.b64decode(self.data.encode())
		ctx = hashlib.new(self.HASHLIB_ALGORITHM)
		digest = data[:ctx.digest_size]
		salt = data[ctx.digest_size:]
		ctx.update(password.encode())
		ctx.update(salt)
		return secrets.compare_digest(digest, ctx.digest())

@registry.register
class MD5PasswordHash(HashlibPasswordHash):
	METHOD_NAME = 'md5'
	HASHLIB_ALGORITHM = 'md5'

@registry.register
class SaltedMD5PasswordHash(SaltedHashlibPasswordHash):
	METHOD_NAME = 'smd5'
	HASHLIB_ALGORITHM = 'md5'

@registry.register
class SHA1PasswordHash(HashlibPasswordHash):
	METHOD_NAME = 'sha'
	HASHLIB_ALGORITHM = 'sha1'

@registry.register
class SaltedSHA1PasswordHash(SaltedHashlibPasswordHash):
	METHOD_NAME = 'ssha'
	HASHLIB_ALGORITHM = 'sha1'

@registry.register
class SHA256PasswordHash(HashlibPasswordHash):
	METHOD_NAME = 'sha256'
	HASHLIB_ALGORITHM = 'sha256'

@registry.register
class SaltedSHA256PasswordHash(SaltedHashlibPasswordHash):
	METHOD_NAME = 'ssha256'
	HASHLIB_ALGORITHM = 'sha256'

@registry.register
class SHA384PasswordHash(HashlibPasswordHash):
	METHOD_NAME = 'sha384'
	HASHLIB_ALGORITHM = 'sha384'

@registry.register
class SaltedSHA384PasswordHash(SaltedHashlibPasswordHash):
	METHOD_NAME = 'ssha384'
	HASHLIB_ALGORITHM = 'sha384'

@registry.register
class SHA512PasswordHash(HashlibPasswordHash):
	METHOD_NAME = 'sha512'
	HASHLIB_ALGORITHM = 'sha512'

@registry.register
class SaltedSHA512PasswordHash(SaltedHashlibPasswordHash):
	METHOD_NAME = 'ssha512'
	HASHLIB_ALGORITHM = 'sha512'

@registry.register
class CryptPasswordHash(PasswordHash):
	METHOD_NAME = 'crypt'

	@classmethod
	def from_password(cls, password):
		return cls(build_value(cls.METHOD_NAME, crypt(password)))

	def verify(self, password):
		return secrets.compare_digest(crypt(password, self.data), self.data)

@registry.register
class Argon2PasswordHash(PasswordHash):
	METHOD_NAME = 'argon2'

	hasher = argon2.PasswordHasher()

	@classmethod
	def from_password(cls, password):
		return cls(build_value(cls.METHOD_NAME, cls.hasher.hash(password)))

	def verify(self, password):
		try:
			return self.hasher.verify(self.data, password)
		except argon2.exceptions.Argon2Error:
			return False
		except argon2.exceptions.InvalidHash:
			return False

	@property
	def needs_rehash(self):
		return super().needs_rehash or self.hasher.check_needs_rehash(self.data)

class InvalidPasswordHash:
	def __init__(self, value=None):
		self.value = value

	# pylint: disable=unused-argument
	def verify(self, password):
		return False

	@property
	def needs_rehash(self):
		return True

	def __bool__(self):
		return False

# An alternative approach for the behavior of PasswordHashAttribute would be
# to use sqlalchemy.TypeDecorator. A type decorator allows custom encoding and
# decoding of values coming from the database (when query results are loaded)
# and going into the database (when statements are executed).
#
# This has one downside: After setting e.g. user.password to a string value it
# remains a string value until the change is flushed. It is not possible to
# coerce values to PasswordHash objects as soon as they are set.
#
# This is too inconsistent. Code should be able to rely on user.password to
# always behave like a PasswordHash object.

class PasswordHashAttribute:
	'''Descriptor for wrapping an attribute storing a password hash string

	Usage example:

		>>> class User:
		...     # Could e.g. be an SQLAlchemy.Column or just a simple attribute
		...     _passord_hash = None
		...     password = PasswordHashAttribute('_passord_hash', SHA512PasswordHash)
		...
		>>> user = User()
		>>> type(user.password)
		<class 'uffd.password_hash.InvalidPasswordHash'>
		>>>
		>>> user._password_hash = '{plain}my_password'
		>>> type(user.password)
		<class 'uffd.password_hash.InvalidPasswordHash'>
		>>> user.password.needs_rehash
		True
		>>>
		>>> user.password = 'my_password'
		>>> user._passord_hash
		'{sha512}3ajDRohg3LJOIoq47kQgjUPrL1/So6U4uvvTnbT/EUyYKaZL0aRxDgwCH4pBNLai+LF+zMh//nnYRZ4t8pT7AQ=='
		>>> type(user.password)
		<class 'uffd.password_hash.SHA512PasswordHash'>
		>>>
		>>> user.password = None
		>>> user._passord_hash is None
		True
		>>> type(user.password)
		<class 'uffd.password_hash.InvalidPasswordHash'>

	When set to a (plaintext) password the underlying attribute is set to a hash
	value for the password. When set to None the underlying attribute is also set
	to None.'''
	def __init__(self, attribute_name, method_cls):
		self.attribute_name = attribute_name
		self.method_cls = method_cls

	def __get__(self, obj, objtype=None):
		if obj is None:
			return self
		value = getattr(obj, self.attribute_name)
		try:
			return registry.parse(value, target_cls=self.method_cls)
		except ValueError:
			return InvalidPasswordHash(value)

	def __set__(self, obj, value):
		if value is None:
			value = InvalidPasswordHash()
		elif isinstance(value, str):
			value = self.method_cls.from_password(value)
		setattr(obj, self.attribute_name, value.value)

# Hashing method for (potentially) low entropy secrets like user passwords. Is
# usually slow and uses salting to make dictionary attacks difficult.
LowEntropyPasswordHash = Argon2PasswordHash

# Hashing method for high entropy secrets like API keys. The secrets are
# generated instead of user-selected to ensure a high level of entropy. Is
# fast and does not need salting, since dictionary attacks are not feasible
# due to high entropy.
HighEntropyPasswordHash = SHA512PasswordHash
