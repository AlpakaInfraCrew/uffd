from uffd.database import db
from uffd.models.misc import lock_table, Lock

from tests.utils import MigrationTestCase

class TestForMissingLockRows(MigrationTestCase):
	def test_check_missing_lock_rows(self):
		self.upgrade('head')
		existing_locks = {row[0] for row in db.session.execute(db.select(lock_table.c.name)).fetchall()}
		for name in Lock.ALL_LOCKS - existing_locks:
			self.fail(f'Lock "{name}" is missing. Make sure to add a migration that inserts it.')

# Add something like this:
#  conn = op.get_bind()
#  lock_table = sa.table('lock', sa.column('name'))
#  conn.execute(sa.insert(lock_table).values(name='NAME'))
