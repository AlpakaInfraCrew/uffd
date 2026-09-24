"""added RoleGroup.requires_mfa and cleanup

Revision ID: bad6fc529510
Revises: aff5f350dcdf
Create Date: 2021-06-22 15:58:10.515330

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'bad6fc529510'
down_revision = 'aff5f350dcdf'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData()
	table = sa.Table('role-group', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=True),
		sa.Column('role_id', sa.Integer(), nullable=True),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role-group_role_id_role')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_role-group')),
		sa.UniqueConstraint('dn', 'role_id', name=op.f('uq_role-group_dn'))
	)
	with op.batch_alter_table(table.name, copy_from=table) as batch_op:
		batch_op.alter_column('id', autoincrement=False, existing_type=sa.Integer())
		batch_op.drop_constraint(batch_op.f('pk_role-group'), type_='primary')
		batch_op.drop_constraint(batch_op.f('uq_role-group_dn'), type_='unique')
		batch_op.drop_column('id')
		batch_op.alter_column('dn', new_column_name='group_dn', nullable=False, existing_type=sa.String(128))
		batch_op.alter_column('role_id', nullable=False, existing_type=sa.Integer())
		batch_op.add_column(sa.Column('requires_mfa', sa.Boolean(create_constraint=True, name=op.f('ck_role-group_requires_mfa')), nullable=False, default=False))
		batch_op.create_primary_key(batch_op.f('pk_role-group'), ['role_id', 'group_dn'])

def downgrade():
	meta = sa.MetaData()
	table = sa.Table('role-group', meta,
		sa.Column('role_id', sa.Integer(), nullable=False),
		sa.Column('group_dn', sa.String(128), nullable=False),
		sa.Column('requires_mfa', sa.Boolean(create_constraint=True, name=op.f('ck_role-group_requires_mfa')), nullable=False, default=False),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role-group_role_id_role')),
		sa.PrimaryKeyConstraint('role_id', 'group_dn', name=op.f('pk_role-group'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		# For some reason MySQL does not allow us to drop the primary key if the foreignkey on role_id exists
		batch_op.drop_constraint(batch_op.f('fk_role-group_role_id_role'), type_='foreignkey')
		batch_op.drop_constraint(batch_op.f('pk_role-group'), type_='primary')
		batch_op.drop_column('requires_mfa')
		batch_op.alter_column('role_id', nullable=True, existing_type=sa.Integer())
		batch_op.alter_column('group_dn', new_column_name='dn', nullable=True, existing_type=sa.String(128))
		batch_op.add_column(sa.Column('id', sa.Integer(), nullable=True))
		batch_op.create_primary_key(batch_op.f('pk_role-group'), ['id'])
		batch_op.alter_column('id', autoincrement=True, nullable=False, existing_type=sa.Integer())
		# For some reason MySQL ignores this statement
		#batch_op.create_unique_constraint(op.f('uq_role-group_dn'), ['dn', 'role_id'])
	meta = sa.MetaData()
	table = sa.Table('role-group', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=True),
		sa.Column('role_id', sa.Integer(), nullable=True),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role-group_role_id_role')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_role-group')),
		sa.UniqueConstraint('dn', 'role_id', name=op.f('uq_role-group_dn'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
