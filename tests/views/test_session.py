import time
import unittest

from flask import url_for, request

from uffd.database import db
from uffd.password_hash import PlaintextPasswordHash
from uffd.models import DeviceLoginConfirmation, Service, OAuth2Client, OAuth2DeviceLoginInitiation, User, RecoveryCodeMethod, TOTPMethod
from uffd.models.mfa import _hotp
from uffd.views.session import login_required

from tests.utils import dump, UffdTestCase, db_flush

class TestSession(UffdTestCase):
	def setUpApp(self):
		self.app.config['SESSION_LIFETIME_SECONDS'] = 2

		@self.app.route('/test_login_required')
		@login_required()
		def test_login_required():
			return 'SUCCESS ' + request.user.loginname, 200

		@self.app.route('/test_group_required1')
		@login_required(lambda: request.user.is_in_group('users'))
		def test_group_required1():
			return 'SUCCESS', 200

		@self.app.route('/test_group_required2')
		@login_required(lambda: request.user.is_in_group('notagroup'))
		def test_group_required2():
			return 'SUCCESS', 200

	def setUp(self):
		super().setUp()
		self.assertIsNone(request.user)

	def login(self):
		self.login_as('user')
		self.assertIsNotNone(request.user)

	def assertLoggedIn(self):
		self.assertEqual(self.client.get(path=url_for('test_login_required'), follow_redirects=True).data, b'SUCCESS testuser')

	def assertLoggedOut(self):
		self.assertNotIn(b'SUCCESS', self.client.get(path=url_for('test_login_required'), follow_redirects=True).data)

	def test_login(self):
		self.assertLoggedOut()
		r = self.client.get(path=url_for('session.login'), follow_redirects=True)
		dump('login', r)
		self.assertEqual(r.status_code, 200)
		r = self.login_as('user')
		dump('login_post', r)
		self.assertEqual(r.status_code, 200)
		self.assertLoggedIn()

	def test_login_password_rehash(self):
		self.get_user().password = PlaintextPasswordHash.from_password('userpassword')
		db.session.commit()
		self.assertIsInstance(self.get_user().password, PlaintextPasswordHash)
		db_flush()
		r = self.login_as('user')
		self.assertEqual(r.status_code, 200)
		self.assertLoggedIn()
		self.assertIsInstance(self.get_user().password, User.password.method_cls)
		self.assertTrue(self.get_user().password.verify('userpassword'))

	def test_titlecase_password(self):
		r = self.client.post(path=url_for('session.login'),
			data={'loginname': self.get_user().loginname.title(), 'password': 'userpassword'}, follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		self.assertLoggedIn()

	def test_redirect(self):
		r = self.login_as('user', ref=url_for('test_login_required'))
		self.assertEqual(r.status_code, 200)
		self.assertEqual(r.data, b'SUCCESS testuser')

	def test_wrong_password(self):
		r = self.client.post(path=url_for('session.login'),
							data={'loginname': self.get_user().loginname, 'password': 'wrongpassword'},
							follow_redirects=True)
		dump('login_wrong_password', r)
		self.assertEqual(r.status_code, 200)
		self.assertLoggedOut()

	def test_empty_password(self):
		r = self.client.post(path=url_for('session.login'),
			data={'loginname': self.get_user().loginname, 'password': ''}, follow_redirects=True)
		dump('login_empty_password', r)
		self.assertEqual(r.status_code, 200)
		self.assertLoggedOut()

	# Regression test for #100 (uncatched LDAPSASLPrepError)
	def test_saslprep_invalid_password(self):
		r = self.client.post(path=url_for('session.login'),
			data={'loginname': 'testuser', 'password': 'wrongpassword\n'}, follow_redirects=True)
		dump('login_saslprep_invalid_password', r)
		self.assertEqual(r.status_code, 200)
		self.assertLoggedOut()

	def test_wrong_user(self):
		r = self.client.post(path=url_for('session.login'),
							data={'loginname': 'nouser', 'password': 'userpassword'},
							follow_redirects=True)
		dump('login_wrong_user', r)
		self.assertEqual(r.status_code, 200)
		self.assertLoggedOut()

	def test_empty_user(self):
		r = self.client.post(path=url_for('session.login'),
			data={'loginname': '', 'password': 'userpassword'}, follow_redirects=True)
		dump('login_empty_user', r)
		self.assertEqual(r.status_code, 200)
		self.assertLoggedOut()

	def test_no_access(self):
		r = self.client.post(path=url_for('session.login'),
			data={'loginname': 'testservice', 'password': 'servicepassword'}, follow_redirects=True)
		dump('login_no_access', r)
		self.assertEqual(r.status_code, 200)
		self.assertLoggedOut()

	def test_deactivated(self):
		self.get_user().is_deactivated = True
		db.session.commit()
		r = self.login_as('user')
		dump('login_deactivated', r)
		self.assertEqual(r.status_code, 200)
		self.assertLoggedOut()

	def test_deactivated_after_login(self):
		self.login_as('user')
		self.get_user().is_deactivated = True
		db.session.commit()
		self.assertLoggedOut()

	def test_group_required(self):
		self.login()
		self.assertEqual(self.client.get(path=url_for('test_group_required1'),
										follow_redirects=True).data, b'SUCCESS')
		self.assertNotEqual(self.client.get(path=url_for('test_group_required2'),
											follow_redirects=True).data, b'SUCCESS')

	def test_logout(self):
		self.login()
		r = self.client.get(path=url_for('session.logout'), follow_redirects=True)
		dump('logout', r)
		self.assertEqual(r.status_code, 200)
		self.assertLoggedOut()

	def test_timeout(self):
		self.login()
		time.sleep(3)
		self.assertLoggedOut()

	def test_ratelimit(self):
		for i in range(20):
			self.client.post(path=url_for('session.login'),
							data={'loginname': self.get_user().loginname,
								'password': 'wrongpassword_%i'%i}, follow_redirects=True)
		r = self.login_as('user')
		dump('login_ratelimit', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(request.user)

	def test_deviceauth(self):
		oauth2_client = OAuth2Client(service=Service(name='test', limit_access=False), client_id='test', client_secret='testsecret', redirect_uris=['http://localhost:5009/callback', 'http://localhost:5009/callback2'])
		initiation = OAuth2DeviceLoginInitiation(client=oauth2_client)
		db.session.add(initiation)
		db.session.commit()
		code = initiation.code
		self.login()
		r = self.client.get(path=url_for('session.deviceauth'), follow_redirects=True)
		dump('deviceauth', r)
		self.assertEqual(r.status_code, 200)
		r = self.client.get(path=url_for('session.deviceauth', **{'initiation-code': code}), follow_redirects=True)
		dump('deviceauth_check', r)
		self.assertEqual(r.status_code, 200)
		self.assertIn(b'test', r.data)
		r = self.client.post(path=url_for('session.deviceauth_submit'), data={'initiation-code': code}, follow_redirects=True)
		dump('deviceauth_submit', r)
		self.assertEqual(r.status_code, 200)
		initiation = OAuth2DeviceLoginInitiation.query.filter_by(code=code).one()
		self.assertEqual(len(initiation.confirmations), 1)
		self.assertEqual(initiation.confirmations[0].session.user.loginname, 'testuser')
		self.assertIn(initiation.confirmations[0].code.encode(), r.data)
		r = self.client.get(path=url_for('session.deviceauth_finish'), follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(DeviceLoginConfirmation.query.all(), [])

class TestMfaViews(UffdTestCase):
	def add_recovery_codes(self, count=10):
		user = self.get_user()
		for _ in range(count):
			db.session.add(RecoveryCodeMethod(user=user))
		db.session.commit()

	def add_totp(self):
		db.session.add(TOTPMethod(user=self.get_user(), name='My phone'))
		db.session.commit()

	def test_auth_integration(self):
		self.add_recovery_codes()
		self.add_totp()
		db.session.commit()
		self.assertIsNone(request.user)
		r = self.login_as('user')
		dump('mfa_auth_redirected', r)
		self.assertEqual(r.status_code, 200)
		self.assertIn(b'/mfa/auth', r.data)
		self.assertIsNone(request.user)
		r = self.client.get(path=url_for('session.mfa_auth'), follow_redirects=False)
		dump('mfa_auth', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(request.user)

	def test_auth_disabled(self):
		self.assertIsNone(request.user)
		self.login_as('user')
		r = self.client.get(path=url_for('session.mfa_auth', ref='/redirecttarget'), follow_redirects=False)
		self.assertEqual(r.status_code, 302)
		self.assertTrue(r.location.endswith('/redirecttarget'))
		self.assertIsNotNone(request.user)

	def test_auth_recovery_only(self):
		self.add_recovery_codes()
		self.assertIsNone(request.user)
		self.login_as('user')
		r = self.client.get(path=url_for('session.mfa_auth', ref='/redirecttarget'), follow_redirects=False)
		self.assertEqual(r.status_code, 302)
		self.assertTrue(r.location.endswith('/redirecttarget'))
		self.assertIsNotNone(request.user)

	def test_auth_recovery_code(self):
		self.add_recovery_codes()
		self.add_totp()
		method = RecoveryCodeMethod(user=self.get_user())
		db.session.add(method)
		db.session.commit()
		method_id = method.id
		self.login_as('user')
		r = self.client.get(path=url_for('session.mfa_auth'), follow_redirects=False)
		dump('mfa_auth_recovery_code', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(request.user)
		r = self.client.post(path=url_for('session.mfa_auth_finish', ref='/redirecttarget'), data={'code': method.code_value})
		self.assertEqual(r.status_code, 302)
		self.assertTrue(r.location.endswith('/redirecttarget'))
		self.assertIsNotNone(request.user)
		self.assertEqual(len(RecoveryCodeMethod.query.filter_by(id=method_id).all()), 0)

	def test_auth_totp_code(self):
		self.add_recovery_codes()
		self.add_totp()
		method = TOTPMethod(user=self.get_user(), name='testname')
		raw_key = method.raw_key
		db.session.add(method)
		db.session.commit()
		self.login_as('user')
		r = self.client.get(path=url_for('session.mfa_auth'), follow_redirects=False)
		dump('mfa_auth_totp_code', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(request.user)
		code = _hotp(int(time.time()/30), raw_key)
		r = self.client.post(path=url_for('session.mfa_auth_finish'), data={'code': code}, follow_redirects=True)
		dump('mfa_auth_totp_code_submit', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNotNone(request.user)

	def test_auth_totp_code_reuse(self):
		self.add_recovery_codes()
		self.add_totp()
		method = TOTPMethod(user=self.get_user(), name='testname')
		raw_key = method.raw_key
		db.session.add(method)
		db.session.commit()
		self.login_as('user')
		r = self.client.get(path=url_for('session.mfa_auth'), follow_redirects=False)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(request.user)
		code = _hotp(int(time.time()/30), raw_key)
		r = self.client.post(path=url_for('session.mfa_auth_finish'), data={'code': code}, follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		self.assertIsNotNone(request.user)
		self.login_as('user')
		r = self.client.get(path=url_for('session.mfa_auth'), follow_redirects=False)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(request.user)
		r = self.client.post(path=url_for('session.mfa_auth_finish'), data={'code': code}, follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(request.user)

	def test_auth_empty_code(self):
		self.add_recovery_codes()
		self.add_totp()
		self.login_as('user')
		r = self.client.get(path=url_for('session.mfa_auth'), follow_redirects=False)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(request.user)
		r = self.client.post(path=url_for('session.mfa_auth_finish'), data={'code': ''}, follow_redirects=True)
		dump('mfa_auth_empty_code', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(request.user)

	def test_auth_invalid_code(self):
		self.add_recovery_codes()
		self.add_totp()
		method = TOTPMethod(user=self.get_user(), name='testname')
		raw_key = method.raw_key
		db.session.add(method)
		db.session.commit()
		self.login_as('user')
		r = self.client.get(path=url_for('session.mfa_auth'), follow_redirects=False)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(request.user)
		code = _hotp(int(time.time()/30), raw_key)
		code = str(int(code[0])+1)[-1] + code[1:]
		r = self.client.post(path=url_for('session.mfa_auth_finish'), data={'code': code}, follow_redirects=True)
		dump('mfa_auth_invalid_code', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(request.user)

	def test_auth_ratelimit(self):
		self.add_recovery_codes()
		self.add_totp()
		method = TOTPMethod(user=self.get_user(), name='testname')
		raw_key = method.raw_key
		db.session.add(method)
		db.session.commit()
		self.login_as('user')
		self.assertIsNone(request.user)
		code = _hotp(int(time.time()/30), raw_key)
		inv_code = str(int(code[0])+1)[-1] + code[1:]
		for i in range(20):
			r = self.client.post(path=url_for('session.mfa_auth_finish'), data={'code': inv_code}, follow_redirects=True)
			self.assertEqual(r.status_code, 200)
			self.assertIsNone(request.user)
		r = self.client.post(path=url_for('session.mfa_auth_finish'), data={'code': code}, follow_redirects=True)
		dump('mfa_auth_ratelimit', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(request.user)

	# TODO: webauthn auth tests
