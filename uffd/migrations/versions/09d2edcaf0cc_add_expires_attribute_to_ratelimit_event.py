"""add expires attribute to ratelimit_event

Revision ID: 09d2edcaf0cc
Revises: af07cea65391
Create Date: 2022-02-15 14:16:19.318253

"""
from alembic import op
import sqlalchemy as sa

revision = '09d2edcaf0cc'
down_revision = 'af07cea65391'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData()
	ratelimit_event = sa.Table('ratelimit_event', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('timestamp', sa.DateTime(), nullable=True),
		sa.Column('name', sa.String(length=128), nullable=True),
		sa.Column('key', sa.String(length=128), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_ratelimit_event'))
	)
	op.execute(ratelimit_event.delete())
	with op.batch_alter_table('ratelimit_event', copy_from=ratelimit_event) as batch_op:
		batch_op.add_column(sa.Column('expires', sa.DateTime(), nullable=False))
		batch_op.alter_column('name', existing_type=sa.VARCHAR(length=128), nullable=False)
		batch_op.alter_column('timestamp', existing_type=sa.DATETIME(), nullable=False)

def downgrade():
	meta = sa.MetaData()
	ratelimit_event = sa.Table('ratelimit_event', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('timestamp', sa.DateTime(), nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('name', sa.String(length=128), nullable=False),
		sa.Column('key', sa.String(length=128), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_ratelimit_event'))
	)
	op.execute(ratelimit_event.delete())
	with op.batch_alter_table('ratelimit_event', schema=None) as batch_op:
		batch_op.alter_column('timestamp', existing_type=sa.DATETIME(), nullable=True)
		batch_op.alter_column('name', existing_type=sa.VARCHAR(length=128), nullable=True)
		batch_op.drop_column('expires')
