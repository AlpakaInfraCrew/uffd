"""added role.is_default

Revision ID: aff5f350dcdf
Revises: a594d3b3e05b
Create Date: 2021-06-15 21:24:13.158828

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'aff5f350dcdf'
down_revision = 'a594d3b3e05b'
branch_labels = None
depends_on = None

def upgrade():
	with op.batch_alter_table('role', schema=None) as batch_op:
		batch_op.add_column(sa.Column('is_default', sa.Boolean(create_constraint=True, name=op.f('ck_role_is_default')), nullable=False, default=False))

def downgrade():
	meta = sa.MetaData()
	table = sa.Table('role', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('name', sa.String(length=32), nullable=True),
		sa.Column('description', sa.Text(), nullable=True),
		sa.Column('moderator_group_dn', sa.String(length=128), nullable=True),
		sa.Column('locked', sa.Boolean(create_constraint=False), nullable=False),
		sa.Column('is_default', sa.Boolean(create_constraint=False), nullable=False),
		sa.CheckConstraint('locked IN (0, 1)', name=op.f('ck_role_locked')),
		sa.CheckConstraint('is_default IN (0, 1)', name=op.f('ck_role_is_default')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_role')),
		sa.UniqueConstraint('name', name=op.f('uq_role_name'))
	)
	with op.batch_alter_table('role', copy_from=table) as batch_op:
		batch_op.drop_constraint(op.f('ck_role_is_default'), 'check')
		batch_op.drop_column('is_default')
