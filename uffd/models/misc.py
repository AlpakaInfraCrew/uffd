from uffd.database import db

# pylint completely fails to understand SQLAlchemy's query functions
# pylint: disable=no-member

feature_flag_table = db.Table('feature_flag',
	db.Column('name', db.String(32), primary_key=True),
)

class FeatureFlag:
	def __init__(self, name):
		self.name = name
		self.enable_hooks = []
		self.disable_hooks = []

	@property
	def expr(self):
		return db.exists().where(feature_flag_table.c.name == self.name)

	def __bool__(self):
		return db.session.execute(db.select(self.expr)).scalar()

	def enable_hook(self, func):
		self.enable_hooks.append(func)
		return func

	def enable(self):
		db.session.execute(db.insert(feature_flag_table).values(name=self.name))
		for func in self.enable_hooks:
			func()

	def disable_hook(self, func):
		self.disable_hooks.append(func)
		return func

	def disable(self):
		db.session.execute(db.delete(feature_flag_table).where(feature_flag_table.c.name == self.name))
		for func in self.disable_hooks:
			func()

FeatureFlag.unique_email_addresses = FeatureFlag('unique-email-addresses')

lock_table = db.Table('lock',
	db.Column('name', db.String(32), primary_key=True),
)

class Lock:
	ALL_LOCKS = set()

	def __init__(self, name):
		self.name = name
		assert name not in self.ALL_LOCKS
		self.ALL_LOCKS.add(name)

	def acquire(self):
		'''Acquire the lock until the end of the current transaction

		Calling acquire while the specific lock is already held has no effect.'''
		if db.engine.name == 'sqlite':
			# SQLite does not support with_for_update, but we can lock the whole DB
			# with any write operation. So we do a dummy update.
			db.session.execute(db.update(lock_table).where(False).values(name=None))
		elif db.engine.name in ('mysql', 'mariadb'):
			result = db.session.execute(db.select(lock_table.c.name).where(lock_table.c.name == self.name).with_for_update()).scalar()
			if result is not None:
				return
			# We add all lock rows with migrations so we should never end up here
			raise Exception(f'Lock "{self.name}" is missing')
		else:
			raise NotImplementedError()

# Only executed when lock_table is created with db.create/db.create_all (e.g.
# during testing). Otherwise the rows are inserted with migrations.
@db.event.listens_for(lock_table, 'after_create') # pylint: disable=no-member
def insert_lock_rows(target, connection, **kwargs): # pylint: disable=unused-argument
	for name in Lock.ALL_LOCKS:
		db.session.execute(db.insert(lock_table).values(name=name))
	db.session.commit()
