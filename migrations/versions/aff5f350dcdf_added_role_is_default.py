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
		batch_op.add_column(sa.Column('is_default', sa.Boolean(name=op.f('ck_role_is_default')), nullable=False, default=False))

def downgrade():
	with op.batch_alter_table('role', schema=None) as batch_op:
		batch_op.drop_column('is_default')
