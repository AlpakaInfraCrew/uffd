import datetime

import sqlalchemy

from uffd.database import db
from uffd.models import User, UserEmail, Group, FeatureFlag, IDAlreadyAllocatedError, IDRangeExhaustedError

from tests.utils import UffdTestCase, ModelTestCase

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
		self.app.config['USER_SERVICE_MAX_UID'] = 19999
		db.drop_all()
		db.create_all()
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
		db.session.delete(user2)
		db.session.commit()
		user4 = User(loginname='user4', displayname='user4', primary_email_address='user4@example.com')
		db.session.add(user4)
		db.session.commit()
		self.assertEqual(user4.unix_uid, 10004)
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
		db.drop_all()
		db.create_all()
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
		db.drop_all()
		db.create_all()
		user0 = User(loginname='user0', displayname='user0', primary_email_address='user0@example.com')
		user1 = User(loginname='user1', displayname='user1', primary_email_address='user1@example.com')
		db.session.add_all([user0, user1])
		db.session.commit()
		self.assertEqual(user0.unix_uid, 10000)
		self.assertEqual(user1.unix_uid, 10001)
		with self.assertRaises(sqlalchemy.exc.StatementError):
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
	def test_normalize_address(self):
		ref = UserEmail.normalize_address('foo@example.com')
		self.assertEqual(ref, UserEmail.normalize_address('foo@example.com'))
		self.assertEqual(ref, UserEmail.normalize_address('Foo@Example.Com'))
		self.assertEqual(ref, UserEmail.normalize_address(' foo@example.com  '))
		self.assertNotEqual(ref, UserEmail.normalize_address('bar@example.com'))
		self.assertNotEqual(ref, UserEmail.normalize_address('foo @example.com'))
		# "No-Break Space" instead of SPACE (Unicode normalization + stripping)
		self.assertEqual(ref, UserEmail.normalize_address('\u00A0foo@example.com '))
		# Pre-composed "Angstrom Sign" vs. "A" + "Combining Ring Above" (Unicode normalization)
		self.assertEqual(UserEmail.normalize_address('\u212B@example.com'), UserEmail.normalize_address('A\u030A@example.com'))

	def test_address(self):
		email = UserEmail()
		self.assertIsNone(email.address)
		self.assertIsNone(email.address_normalized)
		email.address = 'Foo@example.com'
		self.assertEqual(email.address, 'Foo@example.com')
		self.assertEqual(email.address_normalized, UserEmail.normalize_address('Foo@example.com'))
		with self.assertRaises(ValueError):
			email.address = 'bar@example.com'
		with self.assertRaises(ValueError):
			email.address = None

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

	def test_verified(self):
		email = UserEmail(user=self.get_user(), address='foo@example.com')
		db.session.add(email)
		self.assertEqual(email.verified, False)
		self.assertEqual(UserEmail.query.filter_by(address='foo@example.com', verified=True).count(), 0)
		self.assertEqual(UserEmail.query.filter_by(address='foo@example.com', verified=False).count(), 1)
		email.verified = True
		self.assertEqual(email.verified, True)
		self.assertEqual(UserEmail.query.filter_by(address='foo@example.com', verified=True).count(), 1)
		self.assertEqual(UserEmail.query.filter_by(address='foo@example.com', verified=False).count(), 0)
		with self.assertRaises(ValueError):
			email.verified = False
		self.assertEqual(email.verified, True)
		with self.assertRaises(ValueError):
			email.verified = None
		self.assertEqual(email.verified, True)

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

	def test_enable_strict_constraints(self):
		email = UserEmail(address='foo@example.com', user=self.get_user())
		db.session.add(email)
		db.session.commit()
		self.assertIsNone(email.enable_strict_constraints)
		FeatureFlag.unique_email_addresses.enable()
		self.assertTrue(email.enable_strict_constraints)
		FeatureFlag.unique_email_addresses.disable()
		self.assertIsNone(email.enable_strict_constraints)

	def assert_can_add_address(self, **kwargs):
		user_email = UserEmail(**kwargs)
		db.session.add(user_email)
		db.session.commit()
		db.session.delete(user_email)
		db.session.commit()

	def assert_cannot_add_address(self, **kwargs):
		with self.assertRaises(sqlalchemy.exc.IntegrityError):
			db.session.add(UserEmail(**kwargs))
			db.session.commit()
		db.session.rollback()

	def test_unique_constraints_old(self):
		# The same user cannot add the same exact address multiple times, but
		# different users can have the same address
		user = self.get_user()
		admin = self.get_admin()
		db.session.add(UserEmail(user=user, address='foo@example.com'))
		db.session.add(UserEmail(user=user, address='bar@example.com', verified=True))
		db.session.commit()

		self.assert_can_add_address(user=user, address='foobar@example.com')
		self.assert_can_add_address(user=user, address='foobar@example.com', verified=True)

		self.assert_cannot_add_address(user=user, address='foo@example.com')
		self.assert_can_add_address(user=user, address='FOO@example.com')
		self.assert_cannot_add_address(user=user, address='bar@example.com')
		self.assert_can_add_address(user=user, address='BAR@example.com')

		self.assert_cannot_add_address(user=user, address='foo@example.com', verified=True)
		self.assert_can_add_address(user=user, address='FOO@example.com', verified=True)
		self.assert_cannot_add_address(user=user, address='bar@example.com', verified=True)
		self.assert_can_add_address(user=user, address='BAR@example.com', verified=True)

		self.assert_can_add_address(user=admin, address='foobar@example.com')
		self.assert_can_add_address(user=admin, address='foobar@example.com', verified=True)

		self.assert_can_add_address(user=admin, address='foo@example.com')
		self.assert_can_add_address(user=admin, address='FOO@example.com')
		self.assert_can_add_address(user=admin, address='bar@example.com')
		self.assert_can_add_address(user=admin, address='BAR@example.com')

		self.assert_can_add_address(user=admin, address='foo@example.com', verified=True)
		self.assert_can_add_address(user=admin, address='FOO@example.com', verified=True)
		self.assert_can_add_address(user=admin, address='bar@example.com', verified=True)
		self.assert_can_add_address(user=admin, address='BAR@example.com', verified=True)

	def test_unique_constraints_strict(self):
		FeatureFlag.unique_email_addresses.enable()
		# The same user cannot add the same (normalized) address multiple times,
		# and different users cannot have the same verified (normalized) address
		user = self.get_user()
		admin = self.get_admin()
		db.session.add(UserEmail(user=user, address='foo@example.com'))
		db.session.add(UserEmail(user=user, address='bar@example.com', verified=True))
		db.session.commit()

		self.assert_can_add_address(user=user, address='foobar@example.com')
		self.assert_can_add_address(user=user, address='foobar@example.com', verified=True)

		self.assert_cannot_add_address(user=user, address='foo@example.com')
		self.assert_cannot_add_address(user=user, address='FOO@example.com')
		self.assert_cannot_add_address(user=user, address='bar@example.com')
		self.assert_cannot_add_address(user=user, address='BAR@example.com')

		self.assert_cannot_add_address(user=user, address='foo@example.com', verified=True)
		self.assert_cannot_add_address(user=user, address='FOO@example.com', verified=True)
		self.assert_cannot_add_address(user=user, address='bar@example.com', verified=True)
		self.assert_cannot_add_address(user=user, address='BAR@example.com', verified=True)

		self.assert_can_add_address(user=admin, address='foobar@example.com')
		self.assert_can_add_address(user=admin, address='foobar@example.com', verified=True)

		self.assert_can_add_address(user=admin, address='foo@example.com')
		self.assert_can_add_address(user=admin, address='FOO@example.com')
		self.assert_can_add_address(user=admin, address='bar@example.com')
		self.assert_can_add_address(user=admin, address='BAR@example.com')

		self.assert_can_add_address(user=admin, address='foo@example.com', verified=True)
		self.assert_can_add_address(user=admin, address='FOO@example.com', verified=True)
		self.assert_cannot_add_address(user=admin, address='bar@example.com', verified=True)
		self.assert_cannot_add_address(user=admin, address='BAR@example.com', verified=True)

class TestIDAllocator(ModelTestCase):
	def allocate_gids(self, *gids):
		for gid in gids:
			Group.unix_gid_allocator.allocate(gid)

	def fetch_gid_allocations(self):
		return [row[0] for row in db.session.execute(
			db.select(Group.unix_gid_allocator.allocation_table)
			.order_by(Group.unix_gid_allocator.allocation_table.c.id)
		).fetchall()]

	def test_empty(self):
		self.assertEqual(Group.unix_gid_allocator.auto(20000, 20005), 20000)
		self.assertEqual(self.fetch_gid_allocations(), [20000])

	def test_first(self):
		self.allocate_gids(20000)
		self.assertEqual(Group.unix_gid_allocator.auto(20000, 20005), 20001)
		self.assertEqual(self.fetch_gid_allocations(), [20000, 20001])

	def test_out_of_range_before(self):
		self.allocate_gids(19998)
		self.assertEqual(Group.unix_gid_allocator.auto(20000, 20005), 20000)
		self.assertEqual(self.fetch_gid_allocations(), [19998, 20000])

	def test_out_of_range_right_before(self):
		self.allocate_gids(19999)
		self.assertEqual(Group.unix_gid_allocator.auto(20000, 20005), 20000)
		self.assertEqual(self.fetch_gid_allocations(), [19999, 20000])

	def test_out_of_range_after(self):
		self.allocate_gids(20006)
		self.assertEqual(Group.unix_gid_allocator.auto(20000, 20005), 20000)
		self.assertEqual(self.fetch_gid_allocations(), [20000, 20006])

	def test_gap_at_beginning(self):
		self.allocate_gids(20001)
		self.assertEqual(Group.unix_gid_allocator.auto(20000, 20005), 20000)
		self.assertEqual(self.fetch_gid_allocations(), [20000, 20001])

	def test_multiple_gaps(self):
		self.allocate_gids(20000, 20001, 20003, 20005)
		self.assertEqual(Group.unix_gid_allocator.auto(20000, 20005), 20002)
		self.assertEqual(self.fetch_gid_allocations(), [20000, 20001, 20002, 20003, 20005])
		self.assertEqual(Group.unix_gid_allocator.auto(20000, 20005), 20004)
		self.assertEqual(self.fetch_gid_allocations(), [20000, 20001, 20002, 20003, 20004, 20005])

	def test_last(self):
		self.allocate_gids(20000, 20001, 20002, 20003, 20004)
		self.assertEqual(Group.unix_gid_allocator.auto(20000, 20005), 20005)
		self.assertEqual(self.fetch_gid_allocations(), [20000, 20001, 20002, 20003, 20004, 20005])

	def test_overflow(self):
		self.allocate_gids(20000, 20001, 20002, 20003, 20004, 20005)
		with self.assertRaises(IDRangeExhaustedError):
			Group.unix_gid_allocator.auto(20000, 20005)
		self.assertEqual(self.fetch_gid_allocations(), [20000, 20001, 20002, 20003, 20004, 20005])

	def test_conflict(self):
		self.allocate_gids(20000)
		with self.assertRaises(IDAlreadyAllocatedError):
			self.allocate_gids(20000)
		self.assertEqual(self.fetch_gid_allocations(), [20000])

class TestGroup(ModelTestCase):
	def test_unix_gid_generation(self):
		self.app.config['GROUP_MIN_GID'] = 20000
		self.app.config['GROUP_MAX_GID'] = 49999
		group0 = Group(name='group0', description='group0')
		group1 = Group(name='group1', description='group1')
		group2 = Group(name='group2', description='group2')
		group3 = Group(name='group3', description='group3', unix_gid=20004)
		db.session.add_all([group0, group1, group2, group3])
		db.session.commit()
		self.assertEqual(group0.unix_gid, 20000)
		self.assertEqual(group1.unix_gid, 20001)
		self.assertEqual(group2.unix_gid, 20002)
		self.assertEqual(group3.unix_gid, 20004)
		db.session.delete(group2)
		db.session.commit()
		group4 = Group(name='group4', description='group4')
		group5 = Group(name='group5', description='group5')
		db.session.add_all([group4, group5])
		db.session.commit()
		self.assertEqual(group4.unix_gid, 20003)
		self.assertEqual(group5.unix_gid, 20005)

	def test_unix_gid_generation_conflict(self):
		self.app.config['GROUP_MIN_GID'] = 20000
		self.app.config['GROUP_MAX_GID'] = 49999
		group0 = Group(name='group0', description='group0', unix_gid=20023)
		db.session.add(group0)
		db.session.commit()
		with self.assertRaises(IDAlreadyAllocatedError):
			Group(name='group1', description='group1', unix_gid=20023)

	def test_unix_gid_generation_overflow(self):
		self.app.config['GROUP_MIN_GID'] = 20000
		self.app.config['GROUP_MAX_GID'] = 20001
		group0 = Group(name='group0', description='group0')
		group1 = Group(name='group1', description='group1')
		db.session.add_all([group0, group1])
		db.session.commit()
		self.assertEqual(group0.unix_gid, 20000)
		self.assertEqual(group1.unix_gid, 20001)
		db.session.commit()
		with self.assertRaises(sqlalchemy.exc.StatementError):
			group2 = Group(name='group2', description='group2')
			db.session.add(group2)
			db.session.commit()
