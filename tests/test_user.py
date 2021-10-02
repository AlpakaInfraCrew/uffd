import datetime
import unittest

from flask import url_for, session

# These imports are required, because otherwise we get circular imports?!
from uffd import user

from uffd.user.models import User, Group
from uffd.role.models import Role
from uffd import create_app, db

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
			data={'loginname': 'newuser', 'mail': 'newuser@example.com', 'displayname': 'New User',
			f'role-{role1_id}': '1', 'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_submit', r)
		self.assertEqual(r.status_code, 200)
		user_ = User.query.filter_by(loginname='newuser').one_or_none()
		roles = sorted([r.name for r in user_.roles_effective])
		self.assertIsNotNone(user_)
		self.assertFalse(user_.is_service_user)
		self.assertEqual(user_.loginname, 'newuser')
		self.assertEqual(user_.displayname, 'New User')
		self.assertEqual(user_.mail, 'newuser@example.com')
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
			data={'loginname': 'newuser', 'mail': 'newuser@example.com', 'displayname': 'New User',
			f'role-{role1_id}': '1', 'password': 'newpassword', 'serviceaccount': '1'}, follow_redirects=True)
		dump('user_new_submit', r)
		self.assertEqual(r.status_code, 200)
		user = User.query.filter_by(loginname='newuser').one_or_none()
		roles = sorted([r.name for r in user.roles])
		self.assertIsNotNone(user)
		self.assertTrue(user.is_service_user)
		self.assertEqual(user.loginname, 'newuser')
		self.assertEqual(user.displayname, 'New User')
		self.assertEqual(user.mail, 'newuser@example.com')
		self.assertTrue(user.unix_uid)
		role1 = Role(name='role1')
		self.assertEqual(roles, ['role1'])
		# TODO: confirm Mail is send, login not yet possible

	def test_new_invalid_loginname(self):
		r = self.client.post(path=url_for('user.update'),
			data={'loginname': '!newuser', 'mail': 'newuser@example.com', 'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_invalid_loginname', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())

	def test_new_empty_loginname(self):
		r = self.client.post(path=url_for('user.update'),
			data={'loginname': '', 'mail': 'newuser@example.com', 'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_empty_loginname', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())

	def test_new_empty_email(self):
		r = self.client.post(path=url_for('user.update'),
			data={'loginname': 'newuser', 'mail': '', 'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_empty_email', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())

	def test_new_invalid_display_name(self):
		r = self.client.post(path=url_for('user.update'),
			data={'loginname': 'newuser', 'mail': 'newuser@example.com', 'displayname': 'A'*200,
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_new_invalid_display_name', r)
		self.assertEqual(r.status_code, 200)
		self.assertIsNone(User.query.filter_by(loginname='newuser').one_or_none())

	def test_update(self):
		user_unupdated = self.get_user()
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
			data={'loginname': 'testuser', 'mail': 'newuser@example.com', 'displayname': 'New User',
			f'role-{role1_id}': '1', 'password': ''}, follow_redirects=True)
		dump('user_update_submit', r)
		self.assertEqual(r.status_code, 200)
		user_updated = self.get_user()
		roles = sorted([r.name for r in user_updated.roles_effective])
		self.assertEqual(user_updated.displayname, 'New User')
		self.assertEqual(user_updated.mail, 'newuser@example.com')
		self.assertEqual(user_updated.unix_uid, user_unupdated.unix_uid)
		self.assertEqual(user_updated.loginname, user_unupdated.loginname)
		self.assertTrue(user_updated.check_password('userpassword'))
		self.assertEqual(roles, ['base', 'role1'])

	def test_update_password(self):
		user_unupdated = self.get_user()
		r = self.client.get(path=url_for('user.show', id=user_unupdated.id), follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		r = self.client.post(path=url_for('user.update', id=user_unupdated.id),
			data={'loginname': 'testuser', 'mail': 'newuser@example.com', 'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_update_password', r)
		self.assertEqual(r.status_code, 200)
		user_updated = self.get_user()
		self.assertEqual(user_updated.displayname, 'New User')
		self.assertEqual(user_updated.mail, 'newuser@example.com')
		self.assertEqual(user_updated.unix_uid, user_unupdated.unix_uid)
		self.assertEqual(user_updated.loginname, user_unupdated.loginname)
		self.assertTrue(user_updated.check_password('newpassword'))
		self.assertFalse(user_updated.check_password('userpassword'))

	def test_update_invalid_password(self):
		user_unupdated = self.get_user()
		r = self.client.get(path=url_for('user.show', id=user_unupdated.id), follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		r = self.client.post(path=url_for('user.update', id=user_unupdated.id),
			data={'loginname': 'testuser', 'mail': 'newuser@example.com', 'displayname': 'New User',
			'password': 'A'}, follow_redirects=True)
		dump('user_update_invalid_password', r)
		self.assertEqual(r.status_code, 200)
		user_updated = self.get_user()
		self.assertFalse(user_updated.check_password('A'))
		self.assertTrue(user_updated.check_password('userpassword'))
		self.assertEqual(user_updated.displayname, user_unupdated.displayname)
		self.assertEqual(user_updated.mail, user_unupdated.mail)
		self.assertEqual(user_updated.loginname, user_unupdated.loginname)

	# Regression test for #100 (login not possible if password contains character disallowed by SASLprep)
	def test_update_saslprep_invalid_password(self):
		user_unupdated = self.get_user()
		r = self.client.get(path=url_for('user.show', id=user_unupdated.id), follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		r = self.client.post(path=url_for('user.update', id=user_unupdated.id),
			data={'loginname': 'testuser', 'mail': 'newuser@example.com', 'displayname': 'New User',
			'password': 'newpassword\n'}, follow_redirects=True)
		dump('user_update_invalid_password', r)
		self.assertEqual(r.status_code, 200)
		user_updated = self.get_user()
		self.assertFalse(user_updated.check_password('newpassword\n'))
		self.assertTrue(user_updated.check_password('userpassword'))
		self.assertEqual(user_updated.displayname, user_unupdated.displayname)
		self.assertEqual(user_updated.mail, user_unupdated.mail)
		self.assertEqual(user_updated.loginname, user_unupdated.loginname)

	def test_update_empty_email(self):
		user_unupdated = self.get_user()
		r = self.client.get(path=url_for('user.show', id=user_unupdated.id), follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		r = self.client.post(path=url_for('user.update', id=user_unupdated.id),
			data={'loginname': 'testuser', 'mail': '', 'displayname': 'New User',
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_update_empty_mail', r)
		self.assertEqual(r.status_code, 200)
		user_updated = self.get_user()
		self.assertEqual(user_updated.displayname, user_unupdated.displayname)
		self.assertEqual(user_updated.mail, user_unupdated.mail)
		self.assertEqual(user_updated.loginname, user_unupdated.loginname)
		self.assertFalse(user_updated.check_password('newpassword'))
		self.assertTrue(user_updated.check_password('userpassword'))

	def test_update_invalid_display_name(self):
		user_unupdated = self.get_user()
		r = self.client.get(path=url_for('user.show', id=user_unupdated.id), follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		r = self.client.post(path=url_for('user.update', id=user_unupdated.id),
			data={'loginname': 'testuser', 'mail': 'newuser@example.com', 'displayname': 'A'*200,
			'password': 'newpassword'}, follow_redirects=True)
		dump('user_update_invalid_display_name', r)
		self.assertEqual(r.status_code, 200)
		user_updated = self.get_user()
		self.assertEqual(user_updated.displayname, user_unupdated.displayname)
		self.assertEqual(user_updated.mail, user_unupdated.mail)
		self.assertEqual(user_updated.loginname, user_unupdated.loginname)
		self.assertFalse(user_updated.check_password('newpassword'))
		self.assertTrue(user_updated.check_password('userpassword'))

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
		self.assertEqual(user.mail, 'newuser1@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, [])
		user = User.query.filter_by(loginname='newuser2').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser2')
		self.assertEqual(user.displayname, 'newuser2')
		self.assertEqual(user.mail, 'newuser2@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, ['role1'])
		user = User.query.filter_by(loginname='newuser3').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser3')
		self.assertEqual(user.displayname, 'newuser3')
		self.assertEqual(user.mail, 'newuser3@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, ['role1', 'role2'])
		user = User.query.filter_by(loginname='newuser4').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser4')
		self.assertEqual(user.displayname, 'newuser4')
		self.assertEqual(user.mail, 'newuser4@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, [])
		user = User.query.filter_by(loginname='newuser5').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser5')
		self.assertEqual(user.displayname, 'newuser5')
		self.assertEqual(user.mail, 'newuser5@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, [])
		user = User.query.filter_by(loginname='newuser6').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser6')
		self.assertEqual(user.displayname, 'newuser6')
		self.assertEqual(user.mail, 'newuser6@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, ['role1', 'role2'])
		self.assertIsNone(User.query.filter_by(loginname='newuser7').one_or_none())
		self.assertIsNone(User.query.filter_by(loginname='newuser8').one_or_none())
		self.assertIsNone(User.query.filter_by(loginname='newuser9').one_or_none())
		user = User.query.filter_by(loginname='newuser10').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser10')
		self.assertEqual(user.displayname, 'newuser10')
		self.assertEqual(user.mail, 'newuser10@example.com')
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, [])
		user = User.query.filter_by(loginname='newuser11').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser11')
		self.assertEqual(user.displayname, 'newuser11')
		self.assertEqual(user.mail, 'newuser11@example.com')
		# Currently the csv import is not very robust, imho newuser11 should have role1 and role2!
		roles = sorted([r.name for r in user.roles])
		self.assertEqual(roles, ['role2'])
		user = User.query.filter_by(loginname='newuser12').one_or_none()
		self.assertIsNotNone(user)
		self.assertEqual(user.loginname, 'newuser12')
		self.assertEqual(user.displayname, 'newuser12')
		self.assertEqual(user.mail, 'newuser12@example.com')
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
