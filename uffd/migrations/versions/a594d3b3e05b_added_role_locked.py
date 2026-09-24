"""added role.locked

Revision ID: a594d3b3e05b
Revises: 5cab70e95bf8
Create Date: 2021-06-14 00:32:47.792794

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a594d3b3e05b'
down_revision = '5cab70e95bf8'
branch_labels = None
depends_on = None

def upgrade():
	with op.batch_alter_table('role', schema=None) as batch_op:
		batch_op.add_column(sa.Column('locked', sa.Boolean(create_constraint=True, name=op.f('ck_role_locked')), nullable=False, default=False))

def downgrade():
	meta = sa.MetaData()
	table = sa.Table('role', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('name', sa.String(length=32), nullable=True),
		sa.Column('description', sa.Text(), nullable=True),
		sa.Column('moderator_group_dn', sa.String(length=128), nullable=True),
		sa.Column('locked', sa.Boolean(create_constraint=False), nullable=False),
		sa.CheckConstraint('locked IN (0, 1)', name=op.f('ck_role_locked')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_role')),
		sa.UniqueConstraint('name', name=op.f('uq_role_name'))
	)
	with op.batch_alter_table('role', copy_from=table) as batch_op:
		batch_op.drop_constraint(op.f('ck_role_locked'), 'check')
		batch_op.drop_column('locked')
