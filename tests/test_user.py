import datetime
import unittest

from flask import url_for, session
import sqlalchemy

from uffd import create_app, db
from uffd.remailer import remailer
from uffd.models import User, UserEmail, Group, Role, RoleGroup, Service, ServiceUser

from utils import dump, UffdTestCase

class TestUserModel(UffdTestCase):
	def test_has_permission(self):
		user_ = self.get_user() # has 'users' and 'uffd_access' group
		admin = self.get_admin() # has 'users', 'uffd_access' and 'uffd_admin' group
		self.assertTrue(user_.has_permission(None))
		self.assertTrue(admin.has_permission(None))
		self.assertTrue(user_.has_permission('users'))
		self.assertTrue(admin.has_permission('users'))
		self.assertFalse(user_.has_permission('notagroup'))
		self.assertFalse(admin.has_permission('notagroup'))
		self.assertFalse(user_.has_permission('uffd_admin'))
		self.assertTrue(admin.has_permission('uffd_admin'))
		self.assertFalse(user_.has_permission(['uffd_admin']))
		self.assertTrue(admin.has_permission(['uffd_admin']))
		self.assertFalse(user_.has_permission(['uffd_admin', 'notagroup']))
		self.assertTrue(admin.has_permission(['uffd_admin', 'notagroup']))
		self.assertFalse(user_.has_permission(['notagroup', 'uffd_admin']))
		self.assertTrue(admin.has_permission(['notagroup', 'uffd_admin']))
		self.assertTrue(user_.has_permission(['uffd_admin', 'users']))
		self.assertTrue(admin.has_permission(['uffd_admin', 'users']))
		self.assertTrue(user_.has_permission([['uffd_admin', 'users'], ['users', 'uffd_access']]))
		self.assertTrue(admin.has_permission([['uffd_admin', 'users'], ['users', 'uffd_access']]))
		self.assertFalse(user_.has_permission(['uffd_admin', ['users', 'notagroup']]))
		self.assertTrue(admin.has_permission(['uffd_admin', ['users', 'notagroup']]))

	def test_unix_uid_generation(self):
		self.app.config['USER_MIN_UID'] = 10000
		self.app.config['USER_MAX_UID'] = 18999
		self.app.config['USER_SERVICE_MIN_UID'] = 19000
		self.app.config['USER_SERVICE_MAX_UID'] =19999
		User.query.delete()
		db.session.commit()
		user0 = User(loginname='user0', displayname='user0', primary_email_address='user0@example.com')
		user1 = User(loginname='user1', displayname='user1', primary_email_address='user1@example.com')
		user2 = User(loginname='user2', displayname='user2', primary_email_address='user2@example.com')
		db.session.add_all([user0, user1, user2])
		db.session.commit()
		self.assertEqual(user0.unix_uid, 10000)
		self.assertEqual(user1.unix_uid, 10001)
		self.assertEqual(user2.unix_uid, 10002)
		db.session.delete(user1)
		db.session.commit()
		user3 = User(loginname='user3', displayname='user3', primary_email_address='user3@example.com')
		db.session.add(user3)
		db.session.commit()
		self.assertEqual(user3.unix_uid, 10003)
		service0 = User(loginname='service0', displayname='service0', primary_email_address='service0@example.com', is_service_user=True)
		service1 = User(loginname='service1', displayname='service1', primary_email_address='service1@example.com', is_service_user=True)
		db.session.add_all([service0, service1])
		db.session.commit()
		self.assertEqual(service0.unix_uid, 19000)
		self.assertEqual(service1.unix_uid, 19001)

	def test_unix_uid_generation_overlapping(self):
		self.app.config['USER_MIN_UID'] = 10000
		self.app.config['USER_MAX_UID'] = 19999
		self.app.config['USER_SERVICE_MIN_UID'] = 10000
		self.app.config['USER_SERVICE_MAX_UID'] = 19999
		User.query.delete()
		db.session.commit()
		user0 = User(loginname='user0', displayname='user0', primary_email_address='user0@example.com')
		service0 = User(loginname='service0', displayname='service0', primary_email_address='service0@example.com', is_service_user=True)
		user1 = User(loginname='user1', displayname='user1', primary_email_address='user1@example.com')
		db.session.add_all([user0, service0, user1])
		db.session.commit()
		self.assertEqual(user0.unix_uid, 10000)
		self.assertEqual(service0.unix_uid, 10001)
		self.assertEqual(user1.unix_uid, 10002)

	def test_unix_uid_generation_overflow(self):
		self.app.config['USER_MIN_UID'] = 10000
		self.app.config['USER_MAX_UID'] = 10001
		User.query.delete()
		db.session.commit()
		user0 = User(loginname='user0', displayname='user0', primary_email_address='user0@example.com')
		user1 = User(loginname='user1', displayname='user1', primary_email_address='user1@example.com')
		db.session.add_all([user0, user1])
		db.session.commit()
		self.assertEqual(user0.unix_uid, 10000)
		self.assertEqual(user1.unix_uid, 10001)
		with self.assertRaises(sqlalchemy.exc.IntegrityError):
			user2 = User(loginname='user2', displayname='user2', primary_email_address='user2@example.com')
			db.session.add(user2)
			db.session.commit()

	def test_init_primary_email_address(self):
		user = User(primary_email_address='foobar@example.com')
		self.assertEqual(user.primary_email.address, 'foobar@example.com')
		self.assertEqual(user.primary_email.verified, True)
		self.assertEqual(user.primary_email.user, user)
		user = User(primary_email_address='invalid')
		self.assertEqual(user.primary_email.address, 'invalid')
		self.assertEqual(user.primary_email.verified, True)
		self.assertEqual(user.primary_email.user, user)

	def test_set_primary_email_address(self):
		user = User()
		self.assertFalse(user.set_primary_email_address('invalid'))
		self.assertIsNone(user.primary_email)
		self.assertEqual(len(user.all_emails), 0)
		self.assertTrue(user.set_primary_email_address('foobar@example.com'))
		self.assertEqual(user.primary_email.address, 'foobar@example.com')
		self.assertEqual(len(user.all_emails), 1)
		self.assertFalse(user.set_primary_email_address('invalid'))
		self.assertEqual(user.primary_email.address, 'foobar@example.com')
		self.assertEqual(len(user.all_emails), 1)
		self.assertTrue(user.set_primary_email_address('other@example.com'))
		self.assertEqual(user.primary_email.address, 'other@example.com')
		self.assertEqual(len(user.all_emails), 2)
		self.assertEqual({user.all_emails[0].address, user.all_emails[1].address}, {'foobar@example.com', 'other@example.com'})

class TestUserEmailModel(UffdTestCase):
	def test_set_address(self):
		email = UserEmail()
		self.assertFalse(email.set_address('invalid'))
		self.assertIsNone(email.address)
		self.assertFalse(email.set_address(''))
		self.assertFalse(email.set_address('@'))
		self.app.config['REMAILER_DOMAIN'] = 'remailer.example.com'
		self.assertFalse(email.set_address('foobar@remailer.example.com'))
		self.assertFalse(email.set_address('v1-1-testuser@remailer.example.com'))
		self.assertFalse(email.set_address('v1-1-testuser @ remailer.example.com'))
		self.assertFalse(email.set_address('v1-1-testuser@REMAILER.example.com'))
		self.assertFalse(email.set_address('v1-1-testuser@foobar@remailer.example.com'))
		self.assertTrue(email.set_address('foobar@example.com'))
		self.assertEqual(email.address, 'foobar@example.com')

	def test_verification(self):
		email = UserEmail(address='foo@example.com')
		self.assertFalse(email.finish_verification('test'))
		secret = email.start_verification()
		self.assertTrue(email.verification_secret)
		self.assertTrue(email.verification_secret.verify(secret))
		self.assertFalse(email.verification_expired)
		self.assertFalse(email.finish_verification('test'))
		orig_expires = email.verification_expires
		email.verification_expires = datetime.datetime.utcnow() - datetime.timedelta(days=1)
		self.assertFalse(email.finish_verification(secret))
		email.verification_expires = orig_expires
		self.assertTrue(email.finish_verification(secret))
		self.assertFalse(email.verification_secret)
		self.assertTrue(email.verification_expired)

class TestUserViews(UffdTestCase):
	def setUp(self):
		super().setUp()
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
		r = self.client.post(path=url_for('user.update'),
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
		self.assertGreaterEqual(user_.unix_uid, self.app.config['USER_MIN_UID'])
		self.assertLessEqual(user_.unix_uid, self.app.config['USER_MAX_UID'])
		role1 = Role(name='role1')
		self.assertEqual(roles, ['base', 'role1'])
		# TODO: confirm Mail is send, login not yet possible

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
		r = self.client.post(path=url_for('user.update'),
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
		role1 = Role(name='role1')
		self.assertEqual(roles, ['role1'])
		# TODO: confirm Mail is send, login not yet possible

	def test_new_invalid_loginname(self):
		r = self.client.post(path=url_for('user.update'),
			data={'loginname': '!newuser', 'email': 'newuser@example.com', 'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_invalid_loginname', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())

	def test_new_empty_loginname(self):
		r = self.client.post(path=url_for('user.update'),
			data={'loginname': '', 'email': 'newuser@example.com', 'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_empty_loginname', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())

	def test_new_empty_email(self):
		r = self.client.post(path=url_for('user.update'),
			data={'loginname': 'newuser', 'email': '', 'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_empty_email', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())

	def test_new_invalid_display_name(self):
		r = self.client.post(path=url_for('user.update'),
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
		service1 = Service(name='service1', enable_email_preferences=True)
		service2 = Service(name='service2', enable_email_preferences=True)
		db.session.add_all([service1, service2])
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

	def test_delete(self):
		r = self.client.get(path=url_for('user.delete', id=self.get_user().id), follow_redirects=True)
		dump('user_delete', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(self.get_user())

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

class TestUserCLI(UffdTestCase):
	def setUp(self):
		super().setUp()
		role = Role(name='admin')
		role.groups[self.get_admin_group()] = RoleGroup(group=self.get_admin_group())
		db.session.add(role)
		db.session.add(Role(name='test'))
		db.session.commit()
		self.client.__exit__(None, None, None)

	def test_list(self):
		result = self.app.test_cli_runner().invoke(args=['user', 'list'])
		self.assertEqual(result.exit_code, 0)

	def test_show(self):
		result = self.app.test_cli_runner().invoke(args=['user', 'show', 'testuser'])
		self.assertEqual(result.exit_code, 0)
		result = self.app.test_cli_runner().invoke(args=['user', 'show', 'doesnotexist'])
		self.assertEqual(result.exit_code, 1)

	def test_create(self):
		result = self.app.test_cli_runner().invoke(args=['user', 'create', 'new user', '--mail', 'foobar@example.com']) # invalid login name
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['user', 'create', 'newuser', '--mail', '']) # invalid mail
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['user', 'create', 'newuser', '--mail', 'foobar@example.com', '--password', '']) # invalid password
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['user', 'create', 'newuser', '--mail', 'foobar@example.com', '--displayname', '']) # invalid display name
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['user', 'create', 'newuser', '--mail', 'foobar@example.com', '--add-role', 'doesnotexist']) # unknown role
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['user', 'create', 'testuser', '--mail', 'foobar@example.com']) # conflicting name
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['user', 'create', 'newuser', '--mail', 'newmail@example.com',
		                                                 '--displayname', 'New Display Name', '--password', 'newpassword', '--add-role', 'admin'])
		self.assertEqual(result.exit_code, 0)
		with self.app.test_request_context():
			user = User.query.filter_by(loginname='newuser').first()
			self.assertIsNotNone(user)
			self.assertEqual(user.primary_email.address, 'newmail@example.com')
			self.assertEqual(user.displayname, 'New Display Name')
			self.assertTrue(user.password.verify('newpassword'))
			self.assertEqual(user.roles, Role.query.filter_by(name='admin').all())
			self.assertIn(self.get_admin_group(), user.groups)

	def test_update(self):
		result = self.app.test_cli_runner().invoke(args=['user', 'update', 'doesnotexist', '--displayname', 'foo'])
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['user', 'update', 'testuser', '--mail', '']) # invalid mail
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['user', 'update', 'testuser', '--password', '']) # invalid password
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['user', 'update', 'testuser', '--displayname', '']) # invalid display name
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['user', 'update', 'testuser', '--remove-role', 'doesnotexist'])
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['user', 'update', 'testuser', '--mail', 'newmail@example.com',
		                                                 '--displayname', 'New Display Name', '--password', 'newpassword'])
		self.assertEqual(result.exit_code, 0)
		with self.app.test_request_context():
			user = User.query.filter_by(loginname='testuser').first()
			self.assertIsNotNone(user)
			self.assertEqual(user.primary_email.address, 'newmail@example.com')
			self.assertEqual(user.displayname, 'New Display Name')
			self.assertTrue(user.password.verify('newpassword'))
		result = self.app.test_cli_runner().invoke(args=['user', 'update', 'testuser', '--add-role', 'admin', '--add-role', 'test'])
		self.assertEqual(result.exit_code, 0)
		with self.app.test_request_context():
			user = User.query.filter_by(loginname='testuser').first()
			self.assertEqual(set(user.roles), {Role.query.filter_by(name='admin').one(), Role.query.filter_by(name='test').one()})
			self.assertIn(self.get_admin_group(), user.groups)
		result = self.app.test_cli_runner().invoke(args=['user', 'update', 'testuser', '--remove-role', 'admin'])
		self.assertEqual(result.exit_code, 0)
		with self.app.test_request_context():
			user = User.query.filter_by(loginname='testuser').first()
			self.assertEqual(user.roles, Role.query.filter_by(name='test').all())
			self.assertNotIn(self.get_admin_group(), user.groups)
		result = self.app.test_cli_runner().invoke(args=['user', 'update', 'testuser', '--clear-roles', '--add-role', 'admin'])
		self.assertEqual(result.exit_code, 0)
		with self.app.test_request_context():
			user = User.query.filter_by(loginname='testuser').first()
			self.assertEqual(user.roles, Role.query.filter_by(name='admin').all())
			self.assertIn(self.get_admin_group(), user.groups)

	def test_delete(self):
		with self.app.test_request_context():
			self.assertIsNotNone(User.query.filter_by(loginname='testuser').first())
		result = self.app.test_cli_runner().invoke(args=['user', 'delete', 'testuser'])
		self.assertEqual(result.exit_code, 0)
		with self.app.test_request_context():
			self.assertIsNone(User.query.filter_by(loginname='testuser').first())
		result = self.app.test_cli_runner().invoke(args=['user', 'delete', 'doesnotexist'])
		self.assertEqual(result.exit_code, 1)

class TestGroupModel(UffdTestCase):
	def test_unix_gid_generation(self):
		self.app.config['GROUP_MIN_GID'] = 20000
		self.app.config['GROUP_MAX_GID'] = 49999
		Group.query.delete()
		db.session.commit()
		group0 = Group(name='group0', description='group0')
		group1 = Group(name='group1', description='group1')
		group2 = Group(name='group2', description='group2')
		db.session.add_all([group0, group1, group2])
		db.session.commit()
		self.assertEqual(group0.unix_gid, 20000)
		self.assertEqual(group1.unix_gid, 20001)
		self.assertEqual(group2.unix_gid, 20002)
		db.session.delete(group1)
		db.session.commit()
		group3 = Group(name='group3', description='group3')
		db.session.add(group3)
		db.session.commit()
		self.assertEqual(group3.unix_gid, 20003)

	def test_unix_gid_generation(self):
		self.app.config['GROUP_MIN_GID'] = 20000
		self.app.config['GROUP_MAX_GID'] = 20001
		Group.query.delete()
		db.session.commit()
		group0 = Group(name='group0', description='group0')
		group1 = Group(name='group1', description='group1')
		db.session.add_all([group0, group1])
		db.session.commit()
		self.assertEqual(group0.unix_gid, 20000)
		self.assertEqual(group1.unix_gid, 20001)
		db.session.commit()
		with self.assertRaises(sqlalchemy.exc.IntegrityError):
			group2 = Group(name='group2', description='group2')
			db.session.add(group2)
			db.session.commit()

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

class TestGroupCLI(UffdTestCase):
	def setUp(self):
		super().setUp()
		self.client.__exit__(None, None, None)

	def test_list(self):
		result = self.app.test_cli_runner().invoke(args=['group', 'list'])
		self.assertEqual(result.exit_code, 0)

	def test_show(self):
		result = self.app.test_cli_runner().invoke(args=['group', 'show', 'users'])
		self.assertEqual(result.exit_code, 0)
		result = self.app.test_cli_runner().invoke(args=['group', 'show', 'doesnotexist'])
		self.assertEqual(result.exit_code, 1)

	def test_create(self):
		result = self.app.test_cli_runner().invoke(args=['group', 'create', 'users']) # Duplicate name
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['group', 'create', 'new group'])
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['group', 'create', 'newgroup', '--description', 'A new group'])
		self.assertEqual(result.exit_code, 0)
		with self.app.test_request_context():
			group = Group.query.filter_by(name='newgroup').first()
			self.assertIsNotNone(group)
			self.assertEqual(group.description, 'A new group')

	def test_update(self):
		result = self.app.test_cli_runner().invoke(args=['group', 'update', 'doesnotexist', '--description', 'foo'])
		self.assertEqual(result.exit_code, 1)
		result = self.app.test_cli_runner().invoke(args=['group', 'update', 'users', '--description', 'New description'])
		self.assertEqual(result.exit_code, 0)
		with self.app.test_request_context():
			group = Group.query.filter_by(name='users').first()
			self.assertEqual(group.description, 'New description')

	def test_update_without_description(self):
		result = self.app.test_cli_runner().invoke(args=['group', 'update', 'users']) # Should not change anything
		self.assertEqual(result.exit_code, 0)
		with self.app.test_request_context():
			group = Group.query.filter_by(name='users').first()
			self.assertEqual(group.description, 'Base group for all users')

	def test_delete(self):
		with self.app.test_request_context():
			self.assertIsNotNone(Group.query.filter_by(name='users').first())
		result = self.app.test_cli_runner().invoke(args=['group', 'delete', 'users'])
		self.assertEqual(result.exit_code, 0)
		with self.app.test_request_context():
			self.assertIsNone(Group.query.filter_by(name='users').first())
		result = self.app.test_cli_runner().invoke(args=['group', 'delete', 'doesnotexist'])
		self.assertEqual(result.exit_code, 1)
