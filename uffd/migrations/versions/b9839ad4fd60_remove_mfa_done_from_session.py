"""Remove mfa_done from session

Revision ID: b9839ad4fd60
Revises: 4bd316207e59
Create Date: 2025-11-26 03:15:59.986773

"""
from alembic import op
import sqlalchemy as sa

revision = 'b9839ad4fd60'
down_revision = '4bd316207e59'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData()
	session = sa.Table('session', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('secret', sa.Text(), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('last_used', sa.DateTime(), nullable=False),
		sa.Column('user_agent', sa.Text(), nullable=False),
		sa.Column('ip_address', sa.Text(), nullable=True),
		sa.Column('mfa_done', sa.Boolean(create_constraint=True), nullable=False),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_session_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_session'))
	)
	op.execute(session.delete().where(session.c.mfa_done != True))
	with op.batch_alter_table('session', copy_from=session) as batch_op:
		batch_op.drop_column('mfa_done')

def downgrade():
	meta = sa.MetaData()
	with op.batch_alter_table('session') as batch_op:
		batch_op.add_column(sa.Column('mfa_done', sa.Boolean(create_constraint=True, name=op.f('ck_session_mfa_done')), nullable=False, server_default=sa.true()))
	session = sa.Table('session', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('secret', sa.Text(), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('last_used', sa.DateTime(), nullable=False),
		sa.Column('user_agent', sa.Text(), nullable=False),
		sa.Column('ip_address', sa.Text(), nullable=True),
		sa.Column('mfa_done', sa.Boolean(create_constraint=True, name=op.f('ck_session_mfa_done')), nullable=False, server_default=sa.true()),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_session_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_session'))
	)
	with op.batch_alter_table('session', copy_from=session) as batch_op:
		batch_op.alter_column('mfa_done', server_default=None)
