"""MySQL compat fixes

Revision ID: 11ecc8f1ac3b
Revises: bf71799b7b9e
Create Date: 2021-09-13 04:15:07.479295

"""
from alembic import op
import sqlalchemy as sa

revision = '11ecc8f1ac3b'
down_revision = 'bf71799b7b9e'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData()
	table = sa.Table('device_login_confirmation', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('initiation_id', sa.Integer(), nullable=False),
		sa.Column('user_dn', sa.String(length=128), nullable=False),
		sa.Column('code0', sa.String(length=32), nullable=False),
		sa.Column('code1', sa.String(length=32), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_device_login_confirmation')),
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('invite_signup', meta,
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('invite_id', sa.Integer(), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_invite_signup'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	meta = sa.MetaData()
	# Previously "fk_device_login_confirmation_initiation_id_" was named
	# "fk_device_login_confirmation_initiation_id_device_login_initiation"
	# but this was too long for MySQL.
	table = sa.Table('device_login_confirmation', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('initiation_id', sa.Integer(), nullable=False),
		sa.Column('user_dn', sa.String(length=128), nullable=False),
		sa.Column('code0', sa.String(length=32), nullable=False),
		sa.Column('code1', sa.String(length=32), nullable=False),
		sa.ForeignKeyConstraint(['initiation_id'], ['device_login_initiation.id'], name='fk_device_login_confirmation_initiation_id_'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_device_login_confirmation')),
		sa.UniqueConstraint('initiation_id', 'code0', name='uq_device_login_confirmation_initiation_id_code0'),
		sa.UniqueConstraint('initiation_id', 'code1', name='uq_device_login_confirmation_initiation_id_code1'),
		sa.UniqueConstraint('user_dn', name=op.f('uq_device_login_confirmation_user_dn'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass

	# Previously "fk_invite_signup_id_signup" was named
	# "fk_invite_signup_signup_id_signup" by mistake.
	table = sa.Table('invite_signup', meta,
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('invite_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['id'], ['signup.id'], name=op.f('fk_invite_signup_id_signup')),
		sa.ForeignKeyConstraint(['invite_id'], ['invite.id'], name=op.f('fk_invite_signup_invite_id_invite')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_invite_signup'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass

def downgrade():
	pass
