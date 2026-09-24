from flask import url_for, request

from uffd.database import db
from uffd.models import User, UserEmail, Group, Role, Service, ServiceUser, FeatureFlag, MFAMethod, RecoveryCodeMethod, TOTPMethod

from tests.utils import dump, UffdTestCase

class TestUserViews(UffdTestCase):
	def setUp(self):
		super().setUp()
		self.app.last_mail = None
		self.login_as('admin')

	def test_index(self):
		r = self.client.get(path=url_for('user.index'), follow_redirects=True)
		dump('user_index', r)
		self.assertEqual(r.status_code, 200)

	def test_new(self):
		db.session.add(Role(name='base', is_default=True))
		role1 = Role(name='role1')
		db.session.add(role1)
		role2 = Role(name='role2')
		db.session.add(role2)
		db.session.commit()
		role1_id = role1.id
		r = self.client.get(path=url_for('user.show'), follow_redirects=True)
		dump('user_new', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())
		r = self.client.post(path=url_for('user.create'),
			data={'loginname': 'newuser', 'email': 'newuser@example.com', 'displayname': 'New User',
			f'role-{role1_id}': '1', 'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_submit', r)
		self.assertEqual(r.status_code, 200)
		user_ = User.query.filter_by(loginname='newuser').one_or_none()
		roles = sorted([r.name for r in user_.roles_effective])
		self.assertIsNotNone(user_)
		self.assertFalse(user_.is_service_user)
		self.assertEqual(user_.loginname, 'newuser')
		self.assertEqual(user_.displayname, 'New User')
		self.assertEqual(user_.primary_email.address, 'newuser@example.com')
		self.assertFalse(user_.password)
		self.assertGreaterEqual(user_.unix_uid, self.app.config['USER_MIN_UID'])
		self.assertLessEqual(user_.unix_uid, self.app.config['USER_MAX_UID'])
		role1 = Role(name='role1')
		self.assertEqual(roles, ['base', 'role1'])
		self.assertIsNotNone(self.app.last_mail)

	def test_new_service(self):
		db.session.add(Role(name='base', is_default=True))
		role1 = Role(name='role1')
		db.session.add(role1)
		role2 = Role(name='role2')
		db.session.add(role2)
		db.session.commit()
		role1_id = role1.id
		r = self.client.get(path=url_for('user.show'), follow_redirects=True)
		dump('user_new_service', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())
		r = self.client.post(path=url_for('user.create'),
			data={'loginname': 'newuser', 'email': 'newuser@example.com', 'displayname': 'New User',
			f'role-{role1_id}': '1', 'password': 'newpassword', 'serviceaccount': '1'}, follow_redirects=True)
		dump('user_new_submit', r)
		self.assertEqual(r.status_code, 200)
		user = User.query.filter_by(loginname='newuser').one_or_none()
		roles = sorted([r.name for r in user.roles])
		self.assertIsNotNone(user)
		self.assertTrue(user.is_service_user)
		self.assertEqual(user.loginname, 'newuser')
		self.assertEqual(user.displayname, 'New User')
		self.assertEqual(user.primary_email.address, 'newuser@example.com')
		self.assertTrue(user.unix_uid)
		self.assertFalse(user.password)
		role1 = Role(name='role1')
		self.assertEqual(roles, ['role1'])
		self.assertIsNone(self.app.last_mail)

	def test_new_invalid_loginname(self):
		r = self.client.post(path=url_for('user.create'),
			data={'loginname': '!newuser', 'email': 'newuser@example.com', 'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_invalid_loginname', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())

	def test_new_empty_loginname(self):
		r = self.client.post(path=url_for('user.create'),
			data={'loginname': '', 'email': 'newuser@example.com', 'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_empty_loginname', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())

	def test_new_conflicting_loginname(self):
		self.assertEqual(User.query.filter_by(loginname='testuser').count(), 1)
		r = self.client.post(path=url_for('user.create'),
			data={'loginname': 'testuser', 'email': 'newuser@example.com', 'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_conflicting_loginname', r)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(User.query.filter_by(loginname='testuser').count(), 1)

	def test_new_empty_email(self):
		r = self.client.post(path=url_for('user.create'),
			data={'loginname': 'newuser', 'email': '', 'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_empty_email', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())

	def test_new_conflicting_email(self):
		FeatureFlag.unique_email_addresses.enable()
		db.session.commit()
		r = self.client.post(path=url_for('user.create'),
			data={'loginname': 'newuser', 'email': 'test@example.com', 'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_conflicting_email', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())

	def test_new_invalid_display_name(self):
		r = self.client.post(path=url_for('user.create'),
			data={'loginname': 'newuser', 'email': 'newuser@example.com', 'displayname': 'A'*200,
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_invalid_display_name', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())

	def test_update(self):
		user_unupdated = self.get_user()
		email_id = str(user_unupdated.primary_email.id)
		db.session.add(Role(name='base', is_default=True))
		role1 = Role(name='role1')
		db.session.add(role1)
		role2 = Role(name='role2')
		db.session.add(role2)
		role2.members.append(user_unupdated)
		db.session.commit()
		role1_id = role1.id
		r = self.client.get(path=url_for('user.show', id=user_unupdated.id), follow_redirects=True)
		dump('user_update', r)
		self.assertEqual(r.status_code, 200)
		r = self.client.post(path=url_for('user.update', id=user_unupdated.id),
			data={'loginname': 'testuser',
			f'email-{email_id}-present': '1', 'primary_email': email_id, 'recovery_email': 'primary',
			'displayname': 'New User', f'role-{role1_id}': '1', 'password': ''},
			follow_redirects=True)
		dump('user_update_submit', r)
		self.assertEqual(r.status_code, 200)
		user_updated = self.get_user()
		roles = sorted([r.name for r in user_updated.roles_effective])
		self.assertEqual(user_updated.displayname, 'New User')
		self.assertEqual(user_updated.primary_email.address, 'test@example.com')
		self.assertEqual(user_updated.unix_uid, user_unupdated.unix_uid)
		self.assertEqual(user_updated.loginname, user_unupdated.loginname)
		self.assertTrue(user_updated.password.verify('userpassword'))
		self.assertEqual(roles, ['base', 'role1'])

	def test_update_password(self):
		user_unupdated = self.get_user()
		email_id = str(user_unupdated.primary_email.id)
		r = self.client.get(path=url_for('user.show', id=user_unupdated.id), follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		r = self.client.post(path=url_for('user.update', id=user_unupdated.id),
			data={'loginname': 'testuser',
			f'email-{email_id}-present': '1', 'primary_email': email_id, 'recovery_email': 'primary',
			'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_update_password', r)
		self.assertEqual(r.status_code, 200)
		user_updated = self.get_user()
		self.assertEqual(user_updated.displayname, 'New User')
		self.assertEqual(user_updated.primary_email.address, 'test@example.com')
		self.assertEqual(user_updated.unix_uid, user_unupdated.unix_uid)
		self.assertEqual(user_updated.loginname, user_unupdated.loginname)
		self.assertTrue(user_updated.password.verify('newpassword'))
		self.assertFalse(user_updated.password.verify('userpassword'))

	def test_update_invalid_password(self):
		user_unupdated = self.get_user()
		email_id = str(user_unupdated.primary_email.id)
		r = self.client.get(path=url_for('user.show', id=user_unupdated.id), follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		r = self.client.post(path=url_for('user.update', id=user_unupdated.id),
			data={'loginname': 'testuser',
			f'email-{email_id}-present': '1', 'primary_email': email_id, 'recovery_email': 'primary',
			'displayname': 'New User',
			'password': 'A'}, follow_redirects=True)
		dump('user_update_invalid_password', r)
		self.assertEqual(r.status_code, 200)
		user_updated = self.get_user()
		self.assertFalse(user_updated.password.verify('A'))
		self.assertTrue(user_updated.password.verify('userpassword'))
		self.assertEqual(user_updated.displayname, user_unupdated.displayname)
		self.assertEqual(user_updated.primary_email.address, user_unupdated.primary_email.address)
		self.assertEqual(user_updated.loginname, user_unupdated.loginname)

	# Regression test for #100 (login not possible if password contains character disallowed by SASLprep)
	def test_update_saslprep_invalid_password(self):
		user_unupdated = self.get_user()
		email_id = str(user_unupdated.primary_email.id)
		r = self.client.get(path=url_for('user.show', id=user_unupdated.id), follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		r = self.client.post(path=url_for('user.update', id=user_unupdated.id),
			data={'loginname': 'testuser',
			f'email-{email_id}-present': '1', 'primary_email': email_id, 'recovery_email': 'primary',
			'displayname': 'New User',
			'password': 'newpassword\n'}, follow_redirects=True)
		dump('user_update_invalid_password', r)
		self.assertEqual(r.status_code, 200)
		user_updated = self.get_user()
		self.assertFalse(user_updated.password.verify('newpassword\n'))
		self.assertTrue(user_updated.password.verify('userpassword'))
		self.assertEqual(user_updated.displayname, user_unupdated.displayname)
		self.assertEqual(user_updated.primary_email.address, user_unupdated.primary_email.address)
		self.assertEqual(user_updated.loginname, user_unupdated.loginname)

	def test_update_email(self):
		user = self.get_user()
		email = UserEmail(user=user, address='foo@example.com')
		service1 = Service(name='service1', enable_email_preferences=True, limit_access=False)
		service2 = Service(name='service2', enable_email_preferences=True, limit_access=False)
		db.session.add_all([email, service1, service2])
		db.session.commit()
		email1_id = user.primary_email.id
		email2_id = email.id
		service1_id = service1.id
		service2_id = service2.id
		r = self.client.post(path=url_for('user.update', id=user.id),
			data={'loginname': 'testuser',
			f'email-{email1_id}-present': '1',
			f'email-{email2_id}-present': '1',
			f'email-{email2_id}-verified': '1',
			f'newemail-1-address': 'new1@example.com',
			f'newemail-2-address': 'new2@example.com', f'newemail-2-verified': '1',
			'primary_email': email2_id, 'recovery_email': email1_id,
			f'service_{service1_id}_email': 'primary',
			f'service_{service2_id}_email': email2_id,
			'displayname': 'Test User', 'password': ''},
			follow_redirects=True)
		dump('user_update_email', r)
		self.assertEqual(r.status_code, 200)
		user = self.get_user()
		self.assertEqual(user.primary_email.id, email2_id)
		self.assertEqual(user.recovery_email.id, email1_id)
		self.assertEqual(ServiceUser.query.get((service1.id, user.id)).service_email, None)
		self.assertEqual(ServiceUser.query.get((service2.id, user.id)).service_email.id, email2_id)
		self.assertEqual(
			{email.address: email.verified for email in user.all_emails},
			{
				'test@example.com': True,
				'foo@example.com': True,
				'new1@example.com': False,
				'new2@example.com': True,
			}
		)

	def test_update_email_conflict(self):
		user = self.get_user()
		user_id = user.id
		email_id = user.primary_email.id
		email_address = user.primary_email.address
		r = self.client.post(path=url_for('user.update', id=user.id),
			data={'loginname': 'testuser',
			f'email-{email_id}-present': '1',
			f'newemail-1-address': user.primary_email.address},
			follow_redirects=True)
		dump('user_update_email_conflict', r)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(UserEmail.query.filter_by(user_id=user_id).count(), 1)

	def test_update_email_strict_uniqueness(self):
		FeatureFlag.unique_email_addresses.enable()
		db.session.commit()
		user = self.get_user()
		email = UserEmail(user=user, address='foo@example.com')
		service1 = Service(name='service1', enable_email_preferences=True, limit_access=False)
		service2 = Service(name='service2', enable_email_preferences=True, limit_access=False)
		db.session.add_all([email, service1, service2])
		db.session.commit()
		email1_id = user.primary_email.id
		email2_id = email.id
		service1_id = service1.id
		service2_id = service2.id
		r = self.client.post(path=url_for('user.update', id=user.id),
			data={'loginname': 'testuser',
			f'email-{email1_id}-present': '1',
			f'email-{email2_id}-present': '1',
			f'email-{email2_id}-verified': '1',
			f'newemail-1-address': 'new1@example.com',
			f'newemail-2-address': 'new2@example.com', f'newemail-2-verified': '1',
			'primary_email': email2_id, 'recovery_email': email1_id,
			f'service_{service1_id}_email': 'primary',
			f'service_{service2_id}_email': email2_id,
			'displayname': 'Test User', 'password': ''},
			follow_redirects=True)
		dump('user_update_email_strict_uniqueness', r)
		self.assertEqual(r.status_code, 200)
		user = self.get_user()
		self.assertEqual(user.primary_email.id, email2_id)
		self.assertEqual(user.recovery_email.id, email1_id)
		self.assertEqual(ServiceUser.query.get((service1.id, user.id)).service_email, None)
		self.assertEqual(ServiceUser.query.get((service2.id, user.id)).service_email.id, email2_id)
		self.assertEqual(
			{email.address: email.verified for email in user.all_emails},
			{
				'test@example.com': True,
				'foo@example.com': True,
				'new1@example.com': False,
				'new2@example.com': True,
			}
		)

	def test_update_email_strict_uniqueness_conflict(self):
		FeatureFlag.unique_email_addresses.enable()
		db.session.commit()
		user = self.get_user()
		user_id = user.id
		email_id = user.primary_email.id
		email_address = user.primary_email.address
		r = self.client.post(path=url_for('user.update', id=user.id),
			data={'loginname': 'testuser',
			f'email-{email_id}-present': '1',
			f'newemail-1-address': user.primary_email.address},
			follow_redirects=True)
		dump('user_update_email_strict_uniqueness_conflict', r)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(UserEmail.query.filter_by(user_id=user_id).count(), 1)

	def test_update_invalid_display_name(self):
		user_unupdated = self.get_user()
		email_id = str(user_unupdated.primary_email.id)
		r = self.client.get(path=url_for('user.show', id=user_unupdated.id), follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		r = self.client.post(path=url_for('user.update', id=user_unupdated.id),
			data={'loginname': 'testuser',
			f'email-{email_id}-present': '1', 'primary_email': email_id, 'recovery_email': 'primary',
			'displayname': 'A'*200,
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_update_invalid_display_name', r)
		self.assertEqual(r.status_code, 200)
		user_updated = self.get_user()
		self.assertEqual(user_updated.displayname, user_unupdated.displayname)
		self.assertEqual(user_updated.primary_email.address, user_unupdated.primary_email.address)
		self.assertEqual(user_updated.loginname, user_unupdated.loginname)
		self.assertFalse(user_updated.password.verify('newpassword'))
		self.assertTrue(user_updated.password.verify('userpassword'))

	def test_show(self):
		r = self.client.get(path=url_for('user.show', id=self.get_user().id), follow_redirects=True)
		dump('user_show', r)
		self.assertEqual(r.status_code, 200)

	def test_show_self(self):
		r = self.client.get(path=url_for('user.show', id=self.get_admin().id), follow_redirects=True)
		dump('user_show_self', r)
		self.assertEqual(r.status_code, 200)

	def test_delete(self):
		r = self.client.get(path=url_for('user.delete', id=self.get_user().id), follow_redirects=True)
		dump('user_delete', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(self.get_user())

	def test_deactivate(self):
		r = self.client.get(path=url_for('user.deactivate', id=self.get_user().id), follow_redirects=True)
		dump('user_deactivate', r)
		self.assertEqual(r.status_code, 200)
		self.assertTrue(self.get_user().is_deactivated)

	def test_activate(self):
		self.get_user().is_deactivated = True
		db.session.commit()
		r = self.client.get(path=url_for('user.activate', id=self.get_user().id), follow_redirects=True)
		dump('user_activate', r)
		self.assertEqual(r.status_code, 200)
		self.assertFalse(self.get_user().is_deactivated)

	def test_disable_mfa(self):
		db.session.add(RecoveryCodeMethod(user=self.get_admin()))
		user = self.get_user()
		for _ in range(10):
			db.session.add(RecoveryCodeMethod(user=user))
		db.session.add(TOTPMethod(user=self.get_user(), name='My phone'))
		db.session.commit()
		self.login_as('admin')
		admin_methods = len(MFAMethod.query.filter_by(user=self.get_admin()).all())
		r = self.client.get(path=url_for('user.disable_mfa', id=self.get_user().id), follow_redirects=True)
		dump('user_disable_mfa', r)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(len(MFAMethod.query.filter_by(user=self.get_user()).all()), 0)
		self.assertEqual(len(MFAMethod.query.filter_by(user=self.get_admin()).all()), admin_methods)

	def test_csvimport(self):
		role1 = Role(name='role1')
		db.session.add(role1)
		role2 = Role(name='role2')
		db.session.add(role2)
		db.session.commit()
		data = f'''\
newuser1,newuser1@example.com,
newuser2,newuser2@example.com,{role1.id}
newuser3,newuser3@example.com,{role1.id};{role2.id}
newuser4,newuser4@example.com,9999
newuser5,newuser5@example.com,notanumber
newuser6,newuser6@example.com,{role1.id};{role2.id};
newuser7,invalidmail,
newuser8,,
,newuser9@example.com,
,,

,,,
newuser10,newuser10@example.com,
newuser11,newuser11@example.com, {role1.id};{role2.id}
newuser12,newuser12@example.com,{role1.id};{role1.id}
<invalid tag-like thingy>'''
		r = self.client.post(path=url_for('user.csvimport'), data={'csv': data}, follow_redirects=True)
		dump('user_csvimport', r)
		self.assertEqual(r.status_code, 200)
		user = User.query.filter_by(loginname='newuser1').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser1')
		self.assertEqual(user.displayname, 'newuser1')
		self.assertEqual(user.primary_email.address, 'newuser1@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, [])
		user = User.query.filter_by(loginname='newuser2').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser2')
		self.assertEqual(user.displayname, 'newuser2')
		self.assertEqual(user.primary_email.address, 'newuser2@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, ['role1'])
		user = User.query.filter_by(loginname='newuser3').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser3')
		self.assertEqual(user.displayname, 'newuser3')
		self.assertEqual(user.primary_email.address, 'newuser3@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, ['role1', 'role2'])
		user = User.query.filter_by(loginname='newuser4').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser4')
		self.assertEqual(user.displayname, 'newuser4')
		self.assertEqual(user.primary_email.address, 'newuser4@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, [])
		user = User.query.filter_by(loginname='newuser5').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser5')
		self.assertEqual(user.displayname, 'newuser5')
		self.assertEqual(user.primary_email.address, 'newuser5@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, [])
		user = User.query.filter_by(loginname='newuser6').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser6')
		self.assertEqual(user.displayname, 'newuser6')
		self.assertEqual(user.primary_email.address, 'newuser6@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, ['role1', 'role2'])
		self.assertIsNone(User.query.filter_by(loginname='newuser7').one_or_none())
		self.assertIsNone(User.query.filter_by(loginname='newuser8').one_or_none())
		self.assertIsNone(User.query.filter_by(loginname='newuser9').one_or_none())
		user = User.query.filter_by(loginname='newuser10').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser10')
		self.assertEqual(user.displayname, 'newuser10')
		self.assertEqual(user.primary_email.address, 'newuser10@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, [])
		user = User.query.filter_by(loginname='newuser11').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser11')
		self.assertEqual(user.displayname, 'newuser11')
		self.assertEqual(user.primary_email.address, 'newuser11@example.com')
		# Currently the csv import is not very robust, imho newuser11 should have role1 and role2!
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, ['role2'])
		user = User.query.filter_by(loginname='newuser12').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser12')
		self.assertEqual(user.displayname, 'newuser12')
		self.assertEqual(user.primary_email.address, 'newuser12@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, ['role1'])

class TestGroupViews(UffdTestCase):
	def setUp(self):
		super().setUp()
		self.login_as('admin')

	def test_index(self):
		r = self.client.get(path=url_for('group.index'), follow_redirects=True)
		dump('group_index', r)
		self.assertEqual(r.status_code, 200)

	def test_show(self):
		r = self.client.get(path=url_for('group.show', gid=20001), follow_redirects=True)
		dump('group_show', r)
		self.assertEqual(r.status_code, 200)

	def test_new(self):
		r = self.client.get(path=url_for('group.show'), follow_redirects=True)
		dump('group_new', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(Group.query.filter_by(name='newgroup').one_or_none())
		r = self.client.post(path=url_for('group.update'),
			data={'unix_gid': '', 'name': 'newgroup', 'description': 'Test description'},
			follow_redirects=True)
		dump('group_new_submit', r)
		self.assertEqual(r.status_code, 200)
		group = Group.query.filter_by(name='newgroup').one_or_none()
		self.assertIsNotNone(group)
		self.assertEqual(group.name, 'newgroup')
		self.assertEqual(group.description, 'Test description')
		self.assertGreaterEqual(group.unix_gid, self.app.config['GROUP_MIN_GID'])
		self.assertLessEqual(group.unix_gid, self.app.config['GROUP_MAX_GID'])

	def test_new_fixed_gid(self):
		gid = self.app.config['GROUP_MAX_GID'] - 1
		r = self.client.post(path=url_for('group.update'),
			data={'unix_gid': str(gid), 'name': 'newgroup', 'description': 'Test description'},
			follow_redirects=True)
		dump('group_new_fixed_gid', r)
		self.assertEqual(r.status_code, 200)
		group = Group.query.filter_by(name='newgroup').one_or_none()
		self.assertIsNotNone(group)
		self.assertEqual(group.name, 'newgroup')
		self.assertEqual(group.description, 'Test description')
		self.assertEqual(group.unix_gid, gid)

	def test_new_existing_name(self):
		gid = self.app.config['GROUP_MAX_GID'] - 1
		db.session.add(Group(name='newgroup', description='Original description', unix_gid=gid))
		db.session.commit()
		r = self.client.post(path=url_for('group.update'),
			data={'unix_gid': '', 'name': 'newgroup', 'description': 'New description'},
			follow_redirects=True)
		dump('group_new_existing_name', r)
		self.assertEqual(r.status_code, 400)
		group = Group.query.filter_by(name='newgroup').one_or_none()
		self.assertIsNotNone(group)
		self.assertEqual(group.name, 'newgroup')
		self.assertEqual(group.description, 'Original description')
		self.assertEqual(group.unix_gid, gid)

	def test_new_name_too_long(self):
		r = self.client.post(path=url_for('group.update'),
			data={'unix_gid': '', 'name': 'a'*33, 'description': 'New description'},
			follow_redirects=True)
		dump('group_new_name_too_long', r)
		self.assertEqual(r.status_code, 400)
		group = Group.query.filter_by(name='a'*33).one_or_none()
		self.assertIsNone(group)

	def test_new_name_too_short(self):
		r = self.client.post(path=url_for('group.update'),
			data={'unix_gid': '', 'name': '', 'description': 'New description'},
			follow_redirects=True)
		dump('group_new_name_too_short', r)
		self.assertEqual(r.status_code, 400)
		group = Group.query.filter_by(name='').one_or_none()
		self.assertIsNone(group)

	def test_new_name_invalid(self):
		r = self.client.post(path=url_for('group.update'),
			data={'unix_gid': '', 'name': 'foo bar', 'description': 'New description'},
			follow_redirects=True)
		dump('group_new_name_invalid', r)
		self.assertEqual(r.status_code, 400)
		group = Group.query.filter_by(name='foo bar').one_or_none()
		self.assertIsNone(group)

	def test_new_existing_gid(self):
		gid = self.app.config['GROUP_MAX_GID'] - 1
		db.session.add(Group(name='newgroup', description='Original description', unix_gid=gid))
		db.session.commit()
		r = self.client.post(path=url_for('group.update'),
			data={'unix_gid': str(gid), 'name': 'newgroup2', 'description': 'New description'},
			follow_redirects=True)
		dump('group_new_existing_gid', r)
		self.assertEqual(r.status_code, 400)
		group = Group.query.filter_by(name='newgroup').one_or_none()
		self.assertIsNotNone(group)
		self.assertEqual(group.name, 'newgroup')
		self.assertEqual(group.description, 'Original description')
		self.assertEqual(group.unix_gid, gid)
		self.assertIsNone(Group.query.filter_by(name='newgroup2').one_or_none())

	def test_update(self):
		group = Group(name='newgroup', description='Original description')
		db.session.add(group)
		db.session.commit()
		group_id = group.id
		group_gid = group.unix_gid
		new_gid = self.app.config['GROUP_MAX_GID'] - 1
		r = self.client.post(path=url_for('group.update', id=group_id),
			data={'unix_gid': str(new_gid), 'name': 'newgroup_changed', 'description': 'New description'},
			follow_redirects=True)
		dump('group_update', r)
		self.assertEqual(r.status_code, 200)
		group = Group.query.get(group_id)
		self.assertEqual(group.name, 'newgroup') # Not changed
		self.assertEqual(group.description, 'New description') # Changed
		self.assertEqual(group.unix_gid, group_gid) # Not changed

	def test_delete(self):
		group1 = Group(name='newgroup1', description='Original description1')
		group2 = Group(name='newgroup2', description='Original description2')
		db.session.add(group1)
		db.session.add(group2)
		db.session.commit()
		group1_id = group1.id
		group2_id = group2.id
		r = self.client.get(path=url_for('group.delete', id=group1_id), follow_redirects=True)
		dump('group_delete', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(Group.query.get(group1_id))
		self.assertIsNotNone(Group.query.get(group2_id))
