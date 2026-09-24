"""Deactivate users

Revision ID: 23293f32b503
Revises: e249233e2a31
Create Date: 2022-11-10 02:06:27.766520

"""
from alembic import op
import sqlalchemy as sa

revision = '23293f32b503'
down_revision = 'e249233e2a31'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData()
	with op.batch_alter_table('service', schema=None) as batch_op:
		batch_op.add_column(sa.Column('hide_deactivated_users', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()))
	service = sa.Table('service', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('name', sa.String(length=255), nullable=False),
		sa.Column('limit_access', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('access_group_id', sa.Integer(), nullable=True),
		sa.Column('remailer_mode', sa.Enum('DISABLED', 'ENABLED_V1', 'ENABLED_V2', create_constraint=True, name='remailermode'), nullable=False),
		sa.Column('enable_email_preferences', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('hide_deactivated_users', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()),
		sa.ForeignKeyConstraint(['access_group_id'], ['group.id'], name=op.f('fk_service_access_group_id_group'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_service')),
		sa.UniqueConstraint('name', name=op.f('uq_service_name'))
	)
	with op.batch_alter_table('service', copy_from=service) as batch_op:
		batch_op.alter_column('hide_deactivated_users', server_default=None)
	with op.batch_alter_table('user', schema=None) as batch_op:
		batch_op.add_column(sa.Column('is_deactivated', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()))
	user = sa.Table('user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_uid', sa.Integer(), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=False),
		sa.Column('displayname', sa.String(length=128), nullable=False),
		sa.Column('primary_email_id', sa.Integer(), nullable=False),
		sa.Column('recovery_email_id', sa.Integer(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('is_service_user', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('is_deactivated', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()),
		sa.ForeignKeyConstraint(['primary_email_id'], ['user_email.id'], name=op.f('fk_user_primary_email_id_user_email'), onupdate='CASCADE'),
		sa.ForeignKeyConstraint(['recovery_email_id'], ['user_email.id'], name=op.f('fk_user_recovery_email_id_user_email'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.ForeignKeyConstraint(['unix_uid'], ['uid_allocation.id'], name=op.f('fk_user_unix_uid_uid_allocation')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
		sa.UniqueConstraint('loginname', name=op.f('uq_user_loginname')),
		sa.UniqueConstraint('unix_uid', name=op.f('uq_user_unix_uid'))
	)
	with op.batch_alter_table('user', copy_from=user) as batch_op:
		batch_op.alter_column('is_deactivated', server_default=None)

def downgrade():
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
		sa.UniqueConstraint('unix_uid', name=op.f('uq_user_unix_uid'))
	)
	with op.batch_alter_table('user', schema=None) as batch_op:
		batch_op.drop_column('is_deactivated')
	service = sa.Table('service', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('name', sa.String(length=255), nullable=False),
		sa.Column('limit_access', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('access_group_id', sa.Integer(), nullable=True),
		sa.Column('remailer_mode', sa.Enum('DISABLED', 'ENABLED_V1', 'ENABLED_V2', create_constraint=True, name='remailermode'), nullable=False),
		sa.Column('enable_email_preferences', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('hide_deactivated_users', sa.Boolean(create_constraint=True), nullable=False),
		sa.ForeignKeyConstraint(['access_group_id'], ['group.id'], name=op.f('fk_service_access_group_id_group'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_service')),
		sa.UniqueConstraint('name', name=op.f('uq_service_name'))
	)
	with op.batch_alter_table('service', copy_from=service) as batch_op:
		batch_op.drop_column('hide_deactivated_users')
