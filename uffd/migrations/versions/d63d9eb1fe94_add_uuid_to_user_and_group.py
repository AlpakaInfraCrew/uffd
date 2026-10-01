"""Add uuid to user and group

Revision ID: d63d9eb1fe94
Revises: ce3fbc4df4a9
Create Date: 2026-10-07 20:30:43.925961

"""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = 'd63d9eb1fe94'
down_revision = 'ce3fbc4df4a9'
branch_labels = None
depends_on = None

def gen_uuid():
	return '%.32x' % uuid4().int


def iter_rows_paged(table, pk='id', limit=1000):
	conn = op.get_bind()
	pk_column = getattr(table.c, pk)
	last_pk = None
	while True:
		expr = table.select().order_by(pk_column).limit(limit)
		if last_pk is not None:
			expr = expr.where(pk_column > last_pk)
		result = conn.execute(expr)
		pk_index = list(result.keys()).index(pk)
		rows = [cols[pk_index] for cols in result.fetchall()]
		if not rows:
			break
		yield from rows
		last_pk = rows[-1]

def upgrade():
	meta = sa.MetaData()
	user = sa.Table('user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_uid', sa.Integer(), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=False),
		sa.Column('displayname', sa.String(length=128), nullable=False),
		sa.Column('primary_email_id', sa.Integer(), nullable=False),
		sa.Column('recovery_email_id', sa.Integer(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('is_service_user', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('is_deactivated', sa.Boolean(create_constraint=True), nullable=False),
		sa.ForeignKeyConstraint(['primary_email_id'], ['user_email.id'], name=op.f('fk_user_primary_email_id_user_email'), onupdate='CASCADE'),
		sa.ForeignKeyConstraint(['recovery_email_id'], ['user_email.id'], name=op.f('fk_user_recovery_email_id_user_email'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.ForeignKeyConstraint(['unix_uid'], ['uid_allocation.id'], name=op.f('fk_user_unix_uid_uid_allocation')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
		sa.UniqueConstraint('loginname', name=op.f('uq_user_loginname')),
		sa.UniqueConstraint('unix_uid', name=op.f('uq_user_unix_uid')),
	)
	group = sa.Table('group', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_gid', sa.Integer(), nullable=False),
		sa.Column('name', sa.String(length=32), nullable=False),
		sa.Column('description', sa.String(length=128), nullable=False),
		sa.ForeignKeyConstraint(['unix_gid'], ['gid_allocation.id'], name=op.f('fk_group_unix_gid_gid_allocation')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_group')),
		sa.UniqueConstraint('name', name=op.f('uq_group_name')),
		sa.UniqueConstraint('unix_gid', name=op.f('uq_group_unix_gid')),
	)
	oauth2client = sa.Table('oauth2client', meta,
		sa.Column('db_id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('service_id', sa.Integer(), nullable=False),
		sa.Column('client_id', sa.String(length=40), nullable=False),
		sa.Column('client_secret', sa.Text(), nullable=False),
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_oauth2client_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('db_id', name=op.f('pk_oauth2client')),
		sa.UniqueConstraint('client_id', name=op.f('uq_oauth2client_client_id'))
	)
	with op.batch_alter_table('user', copy_from=user) as batch_op:
		batch_op.add_column(sa.Column('uuid', sa.CHAR(length=32), nullable=True))
		batch_op.create_unique_constraint(batch_op.f('uq_user_uuid'), ['uuid'])
	with op.batch_alter_table('group', copy_from=group) as batch_op:
		batch_op.add_column(sa.Column('uuid', sa.CHAR(length=32), nullable=True))
		batch_op.create_unique_constraint(batch_op.f('uq_group_uuid'), ['uuid'])
	with op.batch_alter_table('oauth2client', copy_from=oauth2client) as batch_op:
		batch_op.add_column(sa.Column('use_uuid_as_sub', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()))

	meta = sa.MetaData()
	user = sa.Table('user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_uid', sa.Integer(), nullable=False),
		sa.Column('uuid', sa.CHAR(length=32), nullable=True),
		sa.Column('loginname', sa.String(length=32), nullable=False),
		sa.Column('displayname', sa.String(length=128), nullable=False),
		sa.Column('primary_email_id', sa.Integer(), nullable=False),
		sa.Column('recovery_email_id', sa.Integer(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('is_service_user', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('is_deactivated', sa.Boolean(create_constraint=True), nullable=False),
		sa.ForeignKeyConstraint(['primary_email_id'], ['user_email.id'], name=op.f('fk_user_primary_email_id_user_email'), onupdate='CASCADE'),
		sa.ForeignKeyConstraint(['recovery_email_id'], ['user_email.id'], name=op.f('fk_user_recovery_email_id_user_email'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.ForeignKeyConstraint(['unix_uid'], ['uid_allocation.id'], name=op.f('fk_user_unix_uid_uid_allocation')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
		sa.UniqueConstraint('loginname', name=op.f('uq_user_loginname')),
		sa.UniqueConstraint('unix_uid', name=op.f('uq_user_unix_uid')),
		sa.UniqueConstraint('uuid', name=op.f('uq_user_uuid'))
	)
	group = sa.Table('group', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_gid', sa.Integer(), nullable=False),
		sa.Column('uuid', sa.CHAR(length=32), nullable=True),
		sa.Column('name', sa.String(length=32), nullable=False),
		sa.Column('description', sa.String(length=128), nullable=False),
		sa.ForeignKeyConstraint(['unix_gid'], ['gid_allocation.id'], name=op.f('fk_group_unix_gid_gid_allocation')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_group')),
		sa.UniqueConstraint('name', name=op.f('uq_group_name')),
		sa.UniqueConstraint('unix_gid', name=op.f('uq_group_unix_gid')),
		sa.UniqueConstraint('uuid', name=op.f('uq_group_uuid'))
	)
	oauth2client = sa.Table('oauth2client', meta,
		sa.Column('db_id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('service_id', sa.Integer(), nullable=False),
		sa.Column('client_id', sa.String(length=40), nullable=False),
		sa.Column('client_secret', sa.Text(), nullable=False),
		sa.Column('use_uuid_as_sub', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()),
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_oauth2client_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('db_id', name=op.f('pk_oauth2client')),
		sa.UniqueConstraint('client_id', name=op.f('uq_oauth2client_client_id'))
	)
	for obj_id in iter_rows_paged(user):
		op.execute(user.update().where(user.c.id==obj_id).values(uuid=gen_uuid()))
	with op.batch_alter_table('user', copy_from=user) as batch_op:
		batch_op.alter_column('uuid', nullable=False, existing_type=sa.CHAR(length=32))
	for obj_id in iter_rows_paged(group):
		op.execute(group.update().where(group.c.id==obj_id).values(uuid=gen_uuid()))
	with op.batch_alter_table('group', copy_from=group) as batch_op:
		batch_op.alter_column('uuid', nullable=False, existing_type=sa.CHAR(length=32))
	with op.batch_alter_table('oauth2client', copy_from=oauth2client) as batch_op:
		batch_op.alter_column('use_uuid_as_sub', server_default=None)

def downgrade():
	meta = sa.MetaData()
	user = sa.Table('user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_uid', sa.Integer(), nullable=False),
		sa.Column('uuid', sa.CHAR(length=32), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=False),
		sa.Column('displayname', sa.String(length=128), nullable=False),
		sa.Column('primary_email_id', sa.Integer(), nullable=False),
		sa.Column('recovery_email_id', sa.Integer(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('is_service_user', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('is_deactivated', sa.Boolean(create_constraint=True), nullable=False),
		sa.ForeignKeyConstraint(['primary_email_id'], ['user_email.id'], name=op.f('fk_user_primary_email_id_user_email'), onupdate='CASCADE'),
		sa.ForeignKeyConstraint(['recovery_email_id'], ['user_email.id'], name=op.f('fk_user_recovery_email_id_user_email'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.ForeignKeyConstraint(['unix_uid'], ['uid_allocation.id'], name=op.f('fk_user_unix_uid_uid_allocation')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
		sa.UniqueConstraint('loginname', name=op.f('uq_user_loginname')),
		sa.UniqueConstraint('unix_uid', name=op.f('uq_user_unix_uid')),
		sa.UniqueConstraint('uuid', name=op.f('uq_user_uuid'))
	)
	group = sa.Table('group', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_gid', sa.Integer(), nullable=False),
		sa.Column('uuid', sa.CHAR(length=32), nullable=False),
		sa.Column('name', sa.String(length=32), nullable=False),
		sa.Column('description', sa.String(length=128), nullable=False),
		sa.ForeignKeyConstraint(['unix_gid'], ['gid_allocation.id'], name=op.f('fk_group_unix_gid_gid_allocation')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_group')),
		sa.UniqueConstraint('name', name=op.f('uq_group_name')),
		sa.UniqueConstraint('unix_gid', name=op.f('uq_group_unix_gid')),
		sa.UniqueConstraint('uuid', name=op.f('uq_group_uuid'))
	)
	oauth2client = sa.Table('oauth2client', meta,
		sa.Column('db_id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('service_id', sa.Integer(), nullable=False),
		sa.Column('client_id', sa.String(length=40), nullable=False),
		sa.Column('client_secret', sa.Text(), nullable=False),
		sa.Column('use_uuid_as_sub', sa.Boolean(create_constraint=True), nullable=False),
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_oauth2client_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('db_id', name=op.f('pk_oauth2client')),
		sa.UniqueConstraint('client_id', name=op.f('uq_oauth2client_client_id'))
	)
	with op.batch_alter_table('user', copy_from=user) as batch_op:
		batch_op.drop_constraint(batch_op.f('uq_user_uuid'), type_='unique')
		batch_op.drop_column('uuid')
	with op.batch_alter_table('group', copy_from=group) as batch_op:
		batch_op.drop_constraint(batch_op.f('uq_group_uuid'), type_='unique')
		batch_op.drop_column('uuid')
	with op.batch_alter_table('oauth2client', copy_from=oauth2client) as batch_op:
		batch_op.drop_column('use_uuid_as_sub')
