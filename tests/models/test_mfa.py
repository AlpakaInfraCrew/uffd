import unittest
import datetime
import time

from uffd.database import db
from uffd.models import RecoveryCodeMethod, TOTPMethod, WebauthnMethod
from uffd.models.mfa import _hotp

from tests.utils import UffdTestCase

class TestMfaPrimitives(unittest.TestCase):
	def test_hotp(self):
		self.assertEqual(_hotp(5555555, b'\xae\xa3T\x05\x89\xd6\xb76\xf61r\x92\xcc\xb5WZ\xe6)\x05q'), '458290')
		self.assertEqual(_hotp(5555555, b'\xae\xa3T\x05\x89\xd6\xb76\xf61r\x92\xcc\xb5WZ\xe6)\x05q', digits=8), '20458290')
		for digits in range(1, 10):
			self.assertEqual(len(_hotp(1, b'abcd', digits=digits)), digits)
		self.assertEqual(_hotp(1234, b''), '161024')
		self.assertEqual(_hotp(0, b'\x04\x8fM\xcc\x7f\x82\x9c$a\x1b\xb3'), '279354')
		self.assertEqual(_hotp(2**64-1, b'abcde'), '899292')

def get_fido2_test_cred(self):
	try:
		from uffd.fido2_compat import AttestedCredentialData
	except ImportError:
		self.skipTest('fido2 could not be imported')
	# Example public key from webauthn spec 6.5.1.1
	return AttestedCredentialData(bytes.fromhex('00000000000000000000000000000000'+'0040'+'053cbcc9d37a61d3bac87cdcc77ee326256def08ab15775d3a720332e4101d14fae95aeee3bc9698781812e143c0597dc6e180595683d501891e9dd030454c0a'+'A501020326200121582065eda5a12577c2bae829437fe338701a10aaa375e1bb5b5de108de439c08551d2258201e52ed75701163f7f9e40ddf9f341b3dc9ba860af7e0ca7ca7e9eecd0084d19c'))

class TestMfaMethodModels(UffdTestCase):
	def test_common_attributes(self):
		method = TOTPMethod(user=self.get_user(), name='testname')
		self.assertTrue(method.created <= datetime.datetime.utcnow())
		self.assertEqual(method.name, 'testname')
		self.assertEqual(method.user.loginname, 'testuser')
		method.user = self.get_admin()
		self.assertEqual(method.user.loginname, 'testadmin')

	def test_recovery_code_method(self):
		method = RecoveryCodeMethod(user=self.get_user())
		db.session.add(method)
		db.session.commit()
		method_id = method.id
		method_code = method.code_value
		db.session.expunge(method)
		method = RecoveryCodeMethod.query.get(method_id)
		self.assertFalse(hasattr(method, 'code_value'))
		self.assertFalse(method.verify(''))
		self.assertFalse(method.verify('A'*8))
		self.assertTrue(method.verify(method_code))

	def test_totp_method_attributes(self):
		method = TOTPMethod(user=self.get_user(), name='testname')
		raw_key = method.raw_key
		issuer = method.issuer
		accountname = method.accountname
		key_uri = method.key_uri
		self.assertEqual(method.name, 'testname')
		# Restore method with key parameter
		_method = TOTPMethod(user=self.get_user(), key=method.key, name='testname')
		self.assertEqual(_method.name, 'testname')
		self.assertEqual(_method.raw_key, raw_key)
		self.assertEqual(_method.issuer, issuer)
		self.assertEqual(_method.accountname, accountname)
		self.assertEqual(_method.key_uri, key_uri)
		db.session.add(method)
		db.session.commit()
		_method_id = _method.id
		db.session.expunge(_method)
		# Restore method from db
		_method = TOTPMethod.query.get(_method_id)
		self.assertEqual(_method.name, 'testname')
		self.assertEqual(_method.raw_key, raw_key)
		self.assertEqual(_method.issuer, issuer)
		self.assertEqual(_method.accountname, accountname)
		self.assertEqual(_method.key_uri, key_uri)

	def test_totp_method_verify(self):
		method = TOTPMethod(user=self.get_user())
		counter = int(time.time()/30)
		self.assertFalse(method.verify(''))
		self.assertFalse(method.verify(_hotp(counter-2, method.raw_key)))
		self.assertTrue(method.verify(_hotp(counter, method.raw_key)))
		self.assertFalse(method.verify(_hotp(counter+2, method.raw_key)))

	def test_totp_method_verify_reuse(self):
		method = TOTPMethod(user=self.get_user())
		counter = int(time.time()/30)
		self.assertFalse(method.verify(_hotp(counter-2, method.raw_key)))
		self.assertTrue(method.verify(_hotp(counter-1, method.raw_key)))
		self.assertTrue(method.verify(_hotp(counter, method.raw_key)))
		self.assertFalse(method.verify(_hotp(counter-1, method.raw_key)))
		self.assertFalse(method.verify(_hotp(counter, method.raw_key)))

	def test_webauthn_method(self):
		data = get_fido2_test_cred(self)
		method = WebauthnMethod(user=self.get_user(), cred=data, name='testname')
		self.assertEqual(method.name, 'testname')
		db.session.add(method)
		db.session.commit()
		method_id = method.id
		method_cred = method.cred
		db.session.expunge(method)
		_method = WebauthnMethod.query.get(method_id)
		self.assertEqual(_method.name, 'testname')
		self.assertEqual(bytes(method_cred), bytes(_method.cred))
		self.assertEqual(data.credential_id, _method.cred.credential_id)
		self.assertEqual(data.public_key, _method.cred.public_key)
		# We only test (de-)serialization here, as everything else is currently implemented in the views
