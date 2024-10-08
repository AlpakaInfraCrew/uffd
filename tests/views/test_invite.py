import datetime

from flask import url_for, current_app

from uffd.database import db
from uffd.models import Invite, InviteGrant, InviteSignup, Role, RoleGroup

from tests.utils import dump, UffdTestCase, db_flush

class TestInviteAdminViews(UffdTestCase):
	def setUpApp(self):
		self.app.config['SELF_SIGNUP'] = False
		self.app.last_mail = None

	def test_index(self):
		valid_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
		valid_until_expired = datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
		user1 = self.get_user()
		user2 = self.get_admin()
		role1 = Role(name='testrole1')
		db.session.add(role1)
		role2 = Role(name='testrole2')
		db.session.add(role2)
		# All possible states
		db.session.add(Invite(valid_until=valid_until, single_use=False, creator=self.get_admin()))
		db.session.add(Invite(valid_until=valid_until, single_use=True, used=False, creator=self.get_admin()))
		invite = Invite(valid_until=valid_until, single_use=True, used=True, creator=self.get_admin())
		invite.signups = [InviteSignup(user=user1)]
		db.session.add(invite)
		db.session.add(Invite(valid_until=valid_until_expired, creator=self.get_admin()))
		db.session.add(Invite(valid_until=valid_until, disabled=True, creator=self.get_admin()))
		# Different permissions
		db.session.add(Invite(valid_until=valid_until, allow_signup=True, creator=self.get_admin()))
		db.session.add(Invite(valid_until=valid_until, allow_signup=False, creator=self.get_admin()))
		db.session.add(Invite(valid_until=valid_until, allow_signup=True, roles=[role1], grants=[InviteGrant(user=user2)], creator=self.get_admin()))
		db.session.add(Invite(valid_until=valid_until, allow_signup=False, roles=[role1, role2], creator=self.get_admin()))
		db.session.commit()
		self.login_as('admin')
		r = self.client.get(path=url_for('invite.index'), follow_redirects=True)
		dump('invite_index', r)
		self.assertEqual(r.status_code, 200)

	def test_index_empty(self):
		self.login_as('admin')
		r = self.client.get(path=url_for('invite.index'), follow_redirects=True)
		dump('invite_index_empty', r)
		self.assertEqual(r.status_code, 200)

	def test_index_nologin(self):
		r = self.client.get(path=url_for('invite.index'), follow_redirects=True)
		dump('invite_index_nologin', r)
		self.assertEqual(r.status_code, 200)

	def test_index_noaccess(self):
		self.login_as('user')
		r = self.client.get(path=url_for('invite.index'), follow_redirects=True)
		dump('invite_index_noaccess', r)
		self.assertEqual(r.status_code, 403)

	def test_index_signupperm(self):
		current_app.config['ACL_SIGNUP_GROUP'] = 'uffd_access'
		valid_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
		invite1 = Invite(valid_until=valid_until, allow_signup=True, creator=self.get_admin())
		db.session.add(invite1)
		invite2 = Invite(valid_until=valid_until, allow_signup=True, creator=self.get_user())
		db.session.add(invite2)
		invite3 = Invite(valid_until=valid_until, allow_signup=True)
		db.session.add(invite3)
		db.session.commit()
		token1 = invite1.short_token
		token2 = invite2.short_token
		token3 = invite3.short_token
		self.login_as('user')
		r = self.client.get(path=url_for('invite.index'), follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		self.assertNotIn(token1.encode(), r.data)
		self.assertIn(token2.encode(), r.data)
		self.assertNotIn(token3.encode(), r.data)

	def test_index_rolemod(self):
		role1 = Role(name='testrole1')
		db.session.add(role1)
		role2 = Role(name='testrole2', moderator_group=self.get_access_group())
		db.session.add(role2)
		valid_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
		db.session.add(Invite(valid_until=valid_until, roles=[role1]))
		db.session.add(Invite(valid_until=valid_until, roles=[role2]))
		db.session.commit()
		self.login_as('user')
		r = self.client.get(path=url_for('invite.index'), follow_redirects=True)
		self.assertEqual(r.status_code, 200)
		self.assertNotIn('testrole1'.encode(), r.data)
		self.assertIn('testrole2'.encode(), r.data)

	def test_new(self):
		self.login_as('admin')
		role = Role(name='testrole1')
		db.session.add(role)
		db.session.commit()
		role_id = role.id
		r = self.client.get(path=url_for('invite.new'), follow_redirects=True)
		dump('invite_new', r)
		self.assertEqual(r.status_code, 200)
		valid_until_input = (datetime.datetime.now() + datetime.timedelta(seconds=60)).isoformat(timespec='minutes')
		self.assertListEqual(Invite.query.all(), [])
		r = self.client.post(path=url_for('invite.new_submit'),
			data={'single-use': '1', 'valid-until': valid_until_input,
			      'allow-signup': '1', 'role-%d'%role_id: '1'}, follow_redirects=True)
		dump('invite_new_submit', r)
		invite = Invite.query.one()
		role = Role.query.get(role_id)
		self.assertTrue(invite.active)
		self.assertTrue(invite.single_use)
		self.assertTrue(invite.allow_signup)
		self.assertListEqual(invite.roles, [role])

	def test_new_noperm(self):
		current_app.config['ACL_SIGNUP_GROUP'] = 'uffd_access'
		self.login_as('user')
		role = Role(name='testrole1')
		db.session.add(role)
		db.session.commit()
		role_id = role.id
		valid_until_input = (datetime.datetime.now() + datetime.timedelta(seconds=60)).isoformat(timespec='minutes')
		r = self.client.post(path=url_for('invite.new_submit'),
			data={'single-use': '1', 'valid-until': valid_until_input,
			      'allow-signup': '1', 'role-%d'%role_id: '1'}, follow_redirects=True)
		dump('invite_new_noperm', r)
		self.assertIsNone(Invite.query.first())

	def test_new_empty(self):
		current_app.config['ACL_SIGNUP_GROUP'] = 'uffd_access'
		self.login_as('user')
		valid_until_input = (datetime.datetime.now() + datetime.timedelta(seconds=60)).isoformat(timespec='minutes')
		r = self.client.post(path=url_for('invite.new_submit'),
			data={'single-use': '1', 'valid-until': valid_until_input,
			      'allow-signup': '0'}, follow_redirects=True)
		dump('invite_new_empty', r)
		self.assertIsNone(Invite.query.first())

	def test_disable(self):
		self.login_as('admin')
		valid_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
		invite = Invite(valid_until=valid_until, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		id = invite.id
		self.assertTrue(Invite.query.get(id).active)
		r = self.client.post(path=url_for('invite.disable', invite_id=id), follow_redirects=True)
		dump('invite_disable', r)
		self.assertTrue(Invite.query.get(id).disabled)

	def test_disable_own(self):
		current_app.config['ACL_SIGNUP_GROUP'] = 'uffd_access'
		self.login_as('user')
		valid_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
		invite = Invite(valid_until=valid_until, creator=self.get_user())
		db.session.add(invite)
		db.session.commit()
		id = invite.id
		self.assertTrue(Invite.query.get(id).active)
		r = self.client.post(path=url_for('invite.disable', invite_id=id), follow_redirects=True)
		dump('invite_disable', r)
		self.assertTrue(Invite.query.get(id).disabled)

	def test_disable_rolemod(self):
		self.login_as('user')
		valid_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
		role = Role(name='testrole', moderator_group=self.get_access_group())
		db.session.add(role)
		invite = Invite(valid_until=valid_until, creator=self.get_admin(), roles=[role])
		db.session.add(invite)
		db.session.commit()
		id = invite.id
		self.assertTrue(Invite.query.get(id).active)
		r = self.client.post(path=url_for('invite.disable', invite_id=id), follow_redirects=True)
		self.assertTrue(Invite.query.get(id).disabled)

	def test_disable_noperm(self):
		self.login_as('user')
		valid_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
		db.session.add(Role(name='testrole1', moderator_group=self.get_access_group()))
		role = Role(name='testrole2', moderator_group=self.get_admin_group())
		db.session.add(role)
		invite = Invite(valid_until=valid_until, creator=self.get_admin(), roles=[role])
		db.session.add(invite)
		db.session.commit()
		id = invite.id
		r = self.client.post(path=url_for('invite.disable', invite_id=id), follow_redirects=True)
		self.assertFalse(Invite.query.get(id).disabled)
		self.assertTrue(Invite.query.get(id).active)

	def test_reset_disabled(self):
		self.login_as('admin')
		valid_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
		invite = Invite(valid_until=valid_until, disabled=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		id = invite.id
		self.assertFalse(Invite.query.get(id).active)
		r = self.client.post(path=url_for('invite.reset', invite_id=id), follow_redirects=True)
		dump('invite_reset_disabled', r)
		self.assertTrue(Invite.query.get(id).active)

	def test_reset_voided(self):
		self.login_as('admin')
		valid_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
		invite = Invite(valid_until=valid_until, single_use=True, used=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		id = invite.id
		self.assertFalse(Invite.query.get(id).active)
		r = self.client.post(path=url_for('invite.reset', invite_id=id), follow_redirects=True)
		dump('invite_reset_voided', r)
		self.assertTrue(Invite.query.get(id).active)

	def test_reset_own(self):
		current_app.config['ACL_SIGNUP_GROUP'] = 'uffd_access'
		self.login_as('user')
		valid_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
		invite = Invite(valid_until=valid_until, disabled=True, creator=self.get_user())
		db.session.add(invite)
		db.session.commit()
		id = invite.id
		self.assertFalse(Invite.query.get(id).active)
		r = self.client.post(path=url_for('invite.reset', invite_id=id), follow_redirects=True)
		dump('invite_reset_own', r)
		self.assertTrue(Invite.query.get(id).active)

	def test_reset_foreign(self):
		self.login_as('user')
		valid_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
		role = Role(name='testrole', moderator_group=self.get_access_group())
		db.session.add(role)
		invite = Invite(valid_until=valid_until, disabled=True, creator=self.get_admin(), roles=[role])
		db.session.add(invite)
		db.session.commit()
		id = invite.id
		self.assertFalse(Invite.query.get(id).active)
		r = self.client.post(path=url_for('invite.reset', invite_id=id), follow_redirects=True)
		self.assertFalse(Invite.query.get(id).active)

class TestInviteUseViews(UffdTestCase):
	def setUpApp(self):
		self.app.config['SELF_SIGNUP'] = False
		self.app.last_mail = None

	def test_use(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=True, roles=[Role(name='testrole1'), Role(name='testrole2')])
		db.session.add(invite)
		db.session.commit()
		token = invite.token
		r = self.client.get(path=url_for('invite.use', invite_id=invite.id, token=token), follow_redirects=True)
		dump('invite_use', r)
		self.assertEqual(r.status_code, 200)

	def test_use_loggedin(self):
		self.login_as('user')
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=True, roles=[Role(name='testrole1'), Role(name='testrole2')])
		db.session.add(invite)
		db.session.commit()
		token = invite.token
		r = self.client.get(path=url_for('invite.use', invite_id=invite.id, token=token), follow_redirects=True)
		dump('invite_use_loggedin', r)
		self.assertEqual(r.status_code, 200)

	def test_use_inactive(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), disabled=True)
		db.session.add(invite)
		db.session.commit()
		token = invite.token
		r = self.client.get(path=url_for('invite.use', invite_id=invite.id, token=token), follow_redirects=True)
		dump('invite_use_inactive', r)
		self.assertEqual(r.status_code, 200)

	# TODO: test cases for {logged in, not logged in} x (signup-only, grant-only, both, none?}

	def test_grant(self):
		user = self.get_user()
		group0 = self.get_access_group()
		role0 = Role(name='baserole', groups={group0: RoleGroup(group=group0)})
		db.session.add(role0)
		user.roles.append(role0)
		user.update_groups()
		group1 = self.get_admin_group()
		role1 = Role(name='testrole1', groups={group1: RoleGroup(group=group1)})
		db.session.add(role1)
		role2 = Role(name='testrole2')
		db.session.add(role2)
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), roles=[role1, role2], creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		invite_id = invite.id
		token = invite.token
		self.assertIn(role0, user.roles)
		self.assertNotIn(role1, user.roles)
		self.assertNotIn(role2, user.roles)
		self.assertIn(group0, user.groups)
		self.assertNotIn(group1, user.groups)
		self.assertFalse(invite.used)
		self.login_as('user')
		r = self.client.post(path=url_for('invite.grant', invite_id=invite_id, token=token), follow_redirects=True)
		dump('invite_grant', r)
		self.assertEqual(r.status_code, 200)
		db_flush()
		invite = Invite.query.filter_by(token=token).first()
		user = self.get_user()
		self.assertTrue(invite.used)
		self.assertIn('baserole', [role.name for role in user.roles])
		self.assertIn('testrole1', [role.name for role in user.roles])
		self.assertIn('testrole2', [role.name for role in user.roles])
		self.assertIn(self.get_access_group(), user.groups)
		self.assertIn(self.get_admin_group(), user.groups)

	def test_grant_invalid_invite(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), disabled=True)
		db.session.add(invite)
		db.session.commit()
		invite_id = invite.id
		token = invite.token
		self.login_as('user')
		r = self.client.post(path=url_for('invite.grant', invite_id=invite_id, token=token), follow_redirects=True)
		dump('invite_grant_invalid_invite', r)
		self.assertEqual(r.status_code, 200)
		self.assertFalse(Invite.query.filter_by(token=token).first().used)

	def test_grant_no_roles(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60))
		db.session.add(invite)
		db.session.commit()
		invite_id = invite.id
		token = invite.token
		self.login_as('user')
		r = self.client.post(path=url_for('invite.grant', invite_id=invite_id, token=token), follow_redirects=True)
		dump('invite_grant_no_roles', r)
		self.assertEqual(r.status_code, 200)
		self.assertFalse(Invite.query.filter_by(token=token).first().used)

	def test_grant_no_new_roles(self):
		user = self.get_user()
		role = Role(name='testrole')
		db.session.add(role)
		user.roles.append(role)
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), roles=[role])
		db.session.add(invite)
		db.session.commit()
		invite_id = invite.id
		token = invite.token
		self.login_as('user')
		r = self.client.post(path=url_for('invite.grant', invite_id=invite_id, token=token), follow_redirects=True)
		dump('invite_grant_no_new_roles', r)
		self.assertEqual(r.status_code, 200)
		self.assertFalse(Invite.query.filter_by(token=token).first().used)

	def test_signup(self):
		baserole = Role(name='base', is_default=True)
		baserole.groups[self.get_access_group()] = RoleGroup()
		baserole.groups[self.get_users_group()] = RoleGroup()
		db.session.add(baserole)
		group = self.get_admin_group()
		role1 = Role(name='testrole1', groups={group: RoleGroup(group=group)})
		db.session.add(role1)
		role2 = Role(name='testrole2')
		db.session.add(role2)
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), roles=[role1, role2], allow_signup=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		invite_id = invite.id
		token = invite.token
		r = self.client.get(path=url_for('invite.signup_start', invite_id=invite_id, token=token), follow_redirects=True)
		dump('invite_signup_start', r)
		self.assertEqual(r.status_code, 200)
		r = self.client.post(path=url_for('invite.signup_submit', token=token),
			data={'loginname': 'newuser', 'displayname': 'New User', 'mail': 'test@example.com',
            'password1': 'notsecret', 'password2': 'notsecret'}, follow_redirects=True)
		dump('invite_signup_submit', r)
		self.assertEqual(r.status_code, 200)
		signup = InviteSignup.query.one()
		self.assertEqual(signup.loginname, 'newuser')
		self.assertEqual(signup.displayname, 'New User')
		self.assertEqual(signup.mail, 'test@example.com')
		self.assertIn(signup.token, str(self.app.last_mail.get_content()))
		self.assertTrue(signup.password.verify('notsecret'))
		self.assertTrue(signup.validate()[0])

	def test_signup_invalid_invite(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=True, disabled=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		r = self.client.get(path=url_for('invite.signup_start', invite_id=invite.id, token=invite.token), follow_redirects=True)
		dump('invite_signup_invalid_invite', r)
		self.assertEqual(r.status_code, 200)

	def test_signup_nosignup(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=False, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		r = self.client.get(path=url_for('invite.signup_start', invite_id=invite.id, token=invite.token), follow_redirects=True)
		dump('invite_signup_nosignup', r)
		self.assertEqual(r.status_code, 200)

	def test_signup_wrongpassword(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		r = self.client.post(path=url_for('invite.signup_submit', invite_id=invite.id, token=invite.token),
			data={'loginname': 'newuser', 'displayname': 'New User', 'mail': 'test@example.com',
			      'password1': 'notsecret', 'password2': 'notthesame'}, follow_redirects=True)
		dump('invite_signup_wrongpassword', r)
		self.assertEqual(r.status_code, 200)

	def test_signup_invalid(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		r = self.client.post(path=url_for('invite.signup_submit', invite_id=invite.id, token=invite.token),
			data={'loginname': '', 'displayname': 'New User', 'mail': 'test@example.com',
			      'password1': 'notsecret', 'password2': 'notsecret'}, follow_redirects=True)
		dump('invite_signup_invalid', r)
		self.assertEqual(r.status_code, 200)

	def test_signup_mailerror(self):
		self.app.config['MAIL_SKIP_SEND'] = 'fail'
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		r = self.client.post(path=url_for('invite.signup_submit', invite_id=invite.id, token=invite.token),
			data={'loginname': 'newuser', 'displayname': 'New User', 'mail': 'test@example.com',
			      'password1': 'notsecret', 'password2': 'notsecret'}, follow_redirects=True)
		dump('invite_signup_mailerror', r)
		self.assertEqual(r.status_code, 200)

	def test_signup_hostlimit(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		invite_id = invite.id
		token = invite.token
		for i in range(20):
			r = self.client.post(path=url_for('invite.signup_submit', invite_id=invite_id, token=token),
				data={'loginname': 'newuser%d'%i, 'displayname': 'New User', 'mail': 'test%d@example.com'%i,
							'password1': 'notsecret', 'password2': 'notsecret'}, follow_redirects=True)
			self.assertEqual(r.status_code, 200)
		self.app.last_mail = None
		r = self.client.post(path=url_for('invite.signup_submit', invite_id=invite_id, token=token),
			data={'loginname': 'newuser', 'displayname': 'New User', 'mail': 'test@example.com',
			      'password1': 'notsecret', 'password2': 'notsecret'}, follow_redirects=True)
		dump('invite_signup_hostlimit', r)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(InviteSignup.query.filter_by(loginname='newuser').all(), [])
		self.assertIsNone(self.app.last_mail)

	def test_signup_mailimit(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		invite_id = invite.id
		token = invite.token
		for i in range(3):
			r = self.client.post(path=url_for('invite.signup_submit', invite_id=invite_id, token=token),
				data={'loginname': 'newuser%d'%i, 'displayname': 'New User', 'mail': 'test@example.com',
							'password1': 'notsecret', 'password2': 'notsecret'}, follow_redirects=True)
			self.assertEqual(r.status_code, 200)
		self.app.last_mail = None
		r = self.client.post(path=url_for('invite.signup_submit', invite_id=invite_id, token=token),
			data={'loginname': 'newuser', 'displayname': 'New User', 'mail': 'test@example.com',
			      'password1': 'notsecret', 'password2': 'notsecret'}, follow_redirects=True)
		dump('invite_signup_maillimit', r)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(InviteSignup.query.filter_by(loginname='newuser').all(), [])
		self.assertIsNone(self.app.last_mail)

	def test_signup_check(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		invite_id = invite.id
		token = invite.token
		r = self.client.post(path=url_for('invite.signup_check', invite_id=invite_id, token=token), follow_redirects=True,
		                     data={'loginname': 'newuser'})
		self.assertEqual(r.status_code, 200)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['status'], 'ok')

	def test_signup_check_invalid(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		invite_id = invite.id
		token = invite.token
		r = self.client.post(path=url_for('invite.signup_check', invite_id=invite_id, token=token), follow_redirects=True,
		                     data={'loginname': ''})
		print(r.data)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['status'], 'invalid')

	def test_signup_check_exists(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		invite_id = invite.id
		token = invite.token
		r = self.client.post(path=url_for('invite.signup_check', invite_id=invite_id, token=token), follow_redirects=True,
		                     data={'loginname': 'testuser'})
		self.assertEqual(r.status_code, 200)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['status'], 'exists')

	def test_signup_check_nosignup(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=False, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		invite_id = invite.id
		token = invite.token
		r = self.client.post(path=url_for('invite.signup_check', invite_id=invite_id, token=token), follow_redirects=True,
		                     data={'loginname': 'testuser'})
		self.assertEqual(r.status_code, 403)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['status'], 'error')

	def test_signup_check_error(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=True, disabled=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		invite_id = invite.id
		token = invite.token
		r = self.client.post(path=url_for('invite.signup_check', invite_id=invite_id, token=token), follow_redirects=True,
		                     data={'loginname': 'testuser'})
		self.assertEqual(r.status_code, 403)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['status'], 'error')

	def test_signup_check_ratelimited(self):
		invite = Invite(valid_until=datetime.datetime.utcnow() + datetime.timedelta(seconds=60), allow_signup=True, creator=self.get_admin())
		db.session.add(invite)
		db.session.commit()
		invite_id = invite.id
		token = invite.token
		for i in range(20):
			r = self.client.post(path=url_for('invite.signup_check', invite_id=invite_id, token=token), follow_redirects=True,
													 data={'loginname': 'testuser'})
			self.assertEqual(r.status_code, 200)
			self.assertEqual(r.content_type, 'application/json')
		r = self.client.post(path=url_for('invite.signup_check', invite_id=invite_id, token=token), follow_redirects=True,
		                     data={'loginname': 'testuser'})
		self.assertEqual(r.status_code, 200)
		self.assertEqual(r.content_type, 'application/json')
		self.assertEqual(r.json['status'], 'ratelimited')
