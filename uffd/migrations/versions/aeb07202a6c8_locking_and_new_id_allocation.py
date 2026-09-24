"""Locking and new ID allocation

Revision ID: aeb07202a6c8
Revises: 468995a9c9ee
Create Date: 2022-10-30 13:24:39.864612

"""
from alembic import op
import sqlalchemy as sa
from flask import current_app

# revision identifiers, used by Alembic.
revision = 'aeb07202a6c8'
down_revision = '468995a9c9ee'
branch_labels = None
depends_on = None

def upgrade():
	conn = op.get_bind()
	meta = sa.MetaData()
	user_table = sa.Table('user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_uid', sa.Integer(), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=False),
		sa.Column('displayname', sa.String(length=128), nullable=False),
		sa.Column('primary_email_id', sa.Integer(), nullable=False),
		sa.Column('recovery_email_id', sa.Integer(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('is_service_user', sa.Boolean(create_constraint=True), nullable=False),
		sa.ForeignKeyConstraint(['primary_email_id'], ['user_email.id'], name=op.f('fk_user_primary_email_id_user_email'), onupdate='CASCADE'),
		sa.ForeignKeyConstraint(['recovery_email_id'], ['user_email.id'], name=op.f('fk_user_recovery_email_id_user_email'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
		sa.UniqueConstraint('loginname', name=op.f('uq_user_loginname')),
		sa.UniqueConstraint('unix_uid', name=op.f('uq_user_unix_uid'))
	)
	group_table = sa.Table('group', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_gid', sa.Integer(), nullable=False),
		sa.Column('name', sa.String(length=32), nullable=False),
		sa.Column('description', sa.String(length=128), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_group')),
		sa.UniqueConstraint('name', name=op.f('uq_group_name')),
		sa.UniqueConstraint('unix_gid', name=op.f('uq_group_unix_gid'))
	)

	lock_table = op.create_table('lock',
		sa.Column('name', sa.String(length=32), nullable=False),
		sa.PrimaryKeyConstraint('name', name=op.f('pk_lock'))
	)
	conn.execute(sa.insert(lock_table).values(name='uid_allocation'))
	conn.execute(sa.insert(lock_table).values(name='gid_allocation'))

	uid_allocation_table = op.create_table('uid_allocation',
		sa.Column('id', sa.Integer(), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_uid_allocation'))
	)
	# Completely block range USER_MAX_UID to max UID currently in use (within
	# the UID range) to account for users deleted in the past.
	max_user_uid = conn.execute(
		sa.select(sa.func.max(user_table.c.unix_uid))
		.where(user_table.c.unix_uid <= current_app.config['USER_MAX_UID'])
	).scalar() or 0
	insert_data = []
	if max_user_uid:
		for uid in range(current_app.config['USER_MIN_UID'], max_user_uid + 1):
			insert_data.append({'id': uid})
	op.bulk_insert(uid_allocation_table, insert_data)
	max_service_uid = conn.execute(
		sa.select(sa.func.max(user_table.c.unix_uid))
		.where(user_table.c.unix_uid <= current_app.config['USER_SERVICE_MAX_UID'])
	).scalar() or 0
	insert_data = []
	if max_service_uid:
		for uid in range(current_app.config['USER_SERVICE_MIN_UID'], max_service_uid + 1):
			if uid < current_app.config['USER_MIN_UID'] or uid > max_user_uid:
				insert_data.append({'id': uid})
	op.bulk_insert(uid_allocation_table, insert_data)
	# Also block all UIDs outside of both ranges that are in use
	# (just to be sure, there should not be any)
	conn.execute(sa.insert(uid_allocation_table).from_select(['id'],
		sa.select(user_table.c.unix_uid).where(sa.and_(
			# Out of range for user
			sa.or_(
				user_table.c.unix_uid < current_app.config['USER_MIN_UID'],
				user_table.c.unix_uid > current_app.config['USER_MAX_UID']
			),
			# and out of range for service user
			sa.or_(
				user_table.c.unix_uid < current_app.config['USER_SERVICE_MIN_UID'],
				user_table.c.unix_uid > current_app.config['USER_SERVICE_MAX_UID']
			),
		))
	))
	# Normally we would pass copy_from=user_table, so we don't lose any metadata,
	# but this somehow causes an AttributeError (Neither 'ColumnClause' object
	# nor 'Comparator' object has an attribute 'copy'). Also, we don't seem to
	# lose anything without it.
	with op.batch_alter_table('user', schema=None) as batch_op:
		batch_op.create_foreign_key(batch_op.f('fk_user_unix_uid_uid_allocation'), 'uid_allocation', ['unix_uid'], ['id'])

	gid_allocation_table = op.create_table('gid_allocation',
		sa.Column('id', sa.Integer(), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_gid_allocation'))
	)
	group_table = sa.table('group', sa.column('unix_gid'))
	# Completely block range GROUP_MAX_GID to max GID currently in use (within
	# the GID range) to account for groups deleted in the past.
	max_group_gid = conn.execute(
		sa.select(sa.func.max(group_table.c.unix_gid))
		.where(group_table.c.unix_gid <= current_app.config['GROUP_MAX_GID'])
	).scalar() or 0
	insert_data = []
	if max_group_gid:
		for gid in range(current_app.config['GROUP_MIN_GID'], max_group_gid + 1):
			insert_data.append({'id': gid})
	op.bulk_insert(gid_allocation_table, insert_data)
	# Also block out-of-range GIDs
	conn.execute(sa.insert(gid_allocation_table).from_select(['id'],
		sa.select(group_table.c.unix_gid).where(
			sa.or_(
				group_table.c.unix_gid < current_app.config['GROUP_MIN_GID'],
				group_table.c.unix_gid > current_app.config['GROUP_MAX_GID']
			)
		)
	))
	# See comment on batch_alter_table above
	with op.batch_alter_table('group', schema=None) as batch_op:
		batch_op.create_foreign_key(batch_op.f('fk_group_unix_gid_gid_allocation'), 'gid_allocation', ['unix_gid'], ['id'])

def downgrade():
	meta = sa.MetaData()
	user_table = sa.Table('user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_uid', sa.Integer(), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=False),
		sa.Column('displayname', sa.String(length=128), nullable=False),
		sa.Column('primary_email_id', sa.Integer(), nullable=False),
		sa.Column('recovery_email_id', sa.Integer(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('is_service_user', sa.Boolean(create_constraint=True), nullable=False),
		sa.ForeignKeyConstraint(['primary_email_id'], ['user_email.id'], name=op.f('fk_user_primary_email_id_user_email'), onupdate='CASCADE'),
		sa.ForeignKeyConstraint(['recovery_email_id'], ['user_email.id'], name=op.f('fk_user_recovery_email_id_user_email'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.ForeignKeyConstraint(['unix_uid'], ['uid_allocation.id'], name=op.f('fk_user_unix_uid_uid_allocation')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
		sa.UniqueConstraint('loginname', name=op.f('uq_user_loginname')),
		sa.UniqueConstraint('unix_uid', name=op.f('uq_user_unix_uid'))
	)
	group_table = sa.Table('group', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_gid', sa.Integer(), nullable=False),
		sa.Column('name', sa.String(length=32), nullable=False),
		sa.Column('description', sa.String(length=128), nullable=False),
		sa.ForeignKeyConstraint(['unix_gid'], ['gid_allocation.id'], name=op.f('fk_group_unix_gid_gid_allocation')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_group')),
		sa.UniqueConstraint('name', name=op.f('uq_group_name')),
		sa.UniqueConstraint('unix_gid', name=op.f('uq_group_unix_gid'))
	)
	with op.batch_alter_table('group', copy_from=group_table) as batch_op:
		batch_op.drop_constraint(batch_op.f('fk_group_unix_gid_gid_allocation'), type_='foreignkey')
	with op.batch_alter_table('user', copy_from=user_table) as batch_op:
		batch_op.drop_constraint(batch_op.f('fk_user_unix_uid_uid_allocation'), type_='foreignkey')
	op.drop_table('gid_allocation')
	op.drop_table('uid_allocation')
	op.drop_table('lock')
