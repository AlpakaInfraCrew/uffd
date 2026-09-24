"""Add id to selfservice tokens

Revision ID: e9a67175e179
Revises: a8c6b6e91c28
Create Date: 2021-09-06 22:04:46.741233

"""
from alembic import op
import sqlalchemy as sa

revision = 'e9a67175e179'
down_revision = 'a8c6b6e91c28'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData()
	table = sa.Table('mailToken', meta,
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=True),
		sa.Column('loginname', sa.String(length=32), nullable=True),
		sa.Column('newmail', sa.String(length=255), nullable=True),
		sa.PrimaryKeyConstraint('token', name=op.f('pk_mailToken'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		batch_op.drop_constraint('pk_mailToken', 'primary')
		batch_op.add_column(sa.Column('id', sa.Integer(), nullable=True))
		batch_op.create_primary_key('pk_mailToken', ['id'])
		batch_op.alter_column('id', autoincrement=True, nullable=False, existing_type=sa.Integer())
	table = sa.Table('passwordToken', meta,
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=True),
		sa.Column('loginname', sa.String(length=32), nullable=True),
		sa.PrimaryKeyConstraint('token', name=op.f('pk_passwordToken'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		batch_op.drop_constraint('pk_passwordToken', 'primary')
		batch_op.add_column(sa.Column('id', sa.Integer(), nullable=True))
		batch_op.create_primary_key('pk_passwordToken', ['id'])
		batch_op.alter_column('id', autoincrement=True, nullable=False, existing_type=sa.Integer())

def downgrade():
	meta = sa.MetaData()
	table = sa.Table('mailToken', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=True),
		sa.Column('loginname', sa.String(length=32), nullable=True),
		sa.Column('newmail', sa.String(length=255), nullable=True),
		sa.PrimaryKeyConstraint('token', name=op.f('pk_mailToken'))
	)
	with op.batch_alter_table(table.name, copy_from=table) as batch_op:
		batch_op.alter_column('id', autoincrement=False, existing_type=sa.Integer())
		batch_op.drop_constraint('pk_mailToken', 'primary')
		batch_op.create_primary_key('pk_mailToken', ['token'])
		batch_op.drop_column('id')
	table = sa.Table('passwordToken', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=True),
		sa.Column('loginname', sa.String(length=32), nullable=True),
		sa.PrimaryKeyConstraint('token', name=op.f('pk_passwordToken'))
	)
	with op.batch_alter_table(table.name, copy_from=table) as batch_op:
		batch_op.alter_column('id', autoincrement=False, existing_type=sa.Integer())
		batch_op.drop_constraint('pk_passwordToken', 'primary')
		batch_op.create_primary_key('pk_passwordToken', ['token'])
		batch_op.drop_column('id')
