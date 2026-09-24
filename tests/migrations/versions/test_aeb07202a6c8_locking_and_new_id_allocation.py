from uffd.database import db
from uffd.models.misc import lock_table, Lock

from tests.utils import MigrationTestCase

user_table = db.table('user',
	db.column('id'),
	db.column('unix_uid'),
	db.column('loginname'),
	db.column('displayname'),
	db.column('primary_email_id'),
	db.column('is_service_user'),
)

user_email_table = db.table('user_email',
	db.column('id'),
	db.column('address'),
	db.column('address_normalized'),
	db.column('verified'),
)

group_table = db.table('group',
	db.column('id'),
	db.column('unix_gid'),
	db.column('name'),
	db.column('description')
)

uid_allocation_table = db.table('uid_allocation', db.column('id'))
gid_allocation_table = db.table('gid_allocation', db.column('id'))

class TestMigration(MigrationTestCase):
	REVISION = 'aeb07202a6c8'

	def setUpApp(self):
		self.app.config['USER_MIN_UID'] = 10000
		self.app.config['USER_MAX_UID'] = 10005
		self.app.config['USER_SERVICE_MIN_UID'] = 10006
		self.app.config['USER_SERVICE_MAX_UID'] = 10010
		self.app.config['GROUP_MIN_GID'] = 20000
		self.app.config['GROUP_MAX_GID'] = 20005

	def create_user(self, uid):
		db.session.execute(db.insert(user_email_table).values(
			address=f'email{uid}@example.com',
			address_normalized=f'email{uid}@example.com',
			verified=True
		))
		email_id = db.session.execute(
			db.select(user_email_table.c.id)
			.where(user_email_table.c.address == f'email{uid}@example.com')
		).scalar()
		db.session.execute(db.insert(user_table).values(
			unix_uid=uid,
			loginname=f'user{uid}',
			displayname='user',
			primary_email_id=email_id,
			is_service_user=False
		))

	def create_group(self, gid):
		db.session.execute(db.insert(group_table).values(unix_gid=gid, name=f'group{gid}', description=''))

	def fetch_uid_allocations(self):
		return [row[0] for row in db.session.execute(
			db.select(uid_allocation_table)
			.order_by(uid_allocation_table.c.id)
		).fetchall()]

	def fetch_gid_allocations(self):
		return [row[0] for row in db.session.execute(
			db.select(gid_allocation_table)
			.order_by(gid_allocation_table.c.id)
		).fetchall()]

	def test_empty(self):
		# No users/groups
		self.upgrade()
		self.assertEqual(self.fetch_uid_allocations(), [])
		self.assertEqual(self.fetch_gid_allocations(), [])

	def test_gid_first_minus_one(self):
		self.create_group(19999)
		self.upgrade()
		self.assertEqual(self.fetch_gid_allocations(), [19999])

	def test_gid_first(self):
		self.create_group(20000)
		self.upgrade()
		self.assertEqual(self.fetch_gid_allocations(), [20000])

	def test_gid_first_plus_one(self):
		self.create_group(20001)
		self.upgrade()
		self.assertEqual(self.fetch_gid_allocations(), [20000, 20001])

	def test_gid_last_minus_one(self):
		self.create_group(20004)
		self.upgrade()
		self.assertEqual(self.fetch_gid_allocations(), [20000, 20001, 20002, 20003, 20004])

	def test_gid_last(self):
		self.create_group(20005)
		self.upgrade()
		self.assertEqual(self.fetch_gid_allocations(), [20000, 20001, 20002, 20003, 20004, 20005])

	def test_gid_last_plus_one(self):
		self.create_group(20006)
		self.upgrade()
		self.assertEqual(self.fetch_gid_allocations(), [20006])

	def test_gid_complex(self):
		self.create_group(10)
		self.create_group(20001)
		self.create_group(20003)
		self.create_group(20010)
		self.upgrade()
		self.assertEqual(self.fetch_gid_allocations(), [10, 20000, 20001, 20002, 20003, 20010])

	# The code for UIDs is mostly the same as for GIDs, so we don't test all
	# the edge cases again.
	def test_uid_different_ranges(self):
		self.create_user(10)
		self.create_user(10000)
		self.create_user(10002)
		self.create_user(10007)
		self.create_user(10009)
		self.create_user(90000)
		self.upgrade()
		self.assertEqual(self.fetch_uid_allocations(), [10, 10000, 10001, 10002, 10006, 10007, 10008, 10009, 90000])

	def test_uid_same_ranges(self):
		self.app.config['USER_MIN_UID'] = 10000
		self.app.config['USER_MAX_UID'] = 10010
		self.app.config['USER_SERVICE_MIN_UID'] = 10000
		self.app.config['USER_SERVICE_MAX_UID'] = 10010
		self.create_user(10)
		self.create_user(10000)
		self.create_user(10002)
		self.create_user(10007)
		self.create_user(10009)
		self.create_user(90000)
		self.upgrade()
		self.assertEqual(self.fetch_uid_allocations(), [10, 10000, 10001, 10002, 10003, 10004, 10005, 10006, 10007, 10008, 10009, 90000])
