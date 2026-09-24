"""remailer setting and api permission

Revision ID: 704d1245331c
Revises: b9d3f7dac9db
Create Date: 2022-04-19 17:32:52.304313

"""
from alembic import op
import sqlalchemy as sa

revision = '704d1245331c'
down_revision = 'b9d3f7dac9db'
branch_labels = None
depends_on = None

def upgrade():
	# Retrospective fix of this migration: Originally server_default was not set,
	# which caused "Cannot add a NOT NULL column with default value NULL" errors.
	# This only happens with recent Alembic versions that render
	# batch_op.add_column as an "ALTER TABLE" statement instead of recreating the
	# table. To keep the resulting database consistent, we remove the
	# server_default afterwards.
	with op.batch_alter_table('api_client') as batch_op:
		batch_op.add_column(sa.Column('perm_remailer', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()))
	with op.batch_alter_table('service') as batch_op:
		batch_op.add_column(sa.Column('use_remailer', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()))
	meta = sa.MetaData()
	api_client = sa.Table('api_client', meta,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('service_id', sa.Integer(), nullable=False),
    sa.Column('auth_username', sa.String(length=40), nullable=False),
    sa.Column('auth_password', sa.Text(), nullable=False),
    sa.Column('perm_users', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('perm_checkpassword', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('perm_mail_aliases', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('perm_remailer', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()),
    sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_api_client_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_api_client')),
    sa.UniqueConstraint('auth_username', name=op.f('uq_api_client_auth_username'))
	)
	service = sa.Table('service', meta,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('limit_access', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('access_group_id', sa.Integer(), nullable=True),
    sa.Column('use_remailer', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()),
    sa.ForeignKeyConstraint(['access_group_id'], ['group.id'], name=op.f('fk_service_access_group_id_group'), onupdate='CASCADE', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_service')),
    sa.UniqueConstraint('name', name=op.f('uq_service_name'))
	)
	with op.batch_alter_table('api_client', copy_from=api_client) as batch_op:
		batch_op.alter_column('perm_remailer', server_default=None)
	with op.batch_alter_table('service', copy_from=service) as batch_op:
		batch_op.alter_column('use_remailer', server_default=None)

def downgrade():
	meta = sa.MetaData()
	api_client = sa.Table('api_client', meta,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('service_id', sa.Integer(), nullable=False),
    sa.Column('auth_username', sa.String(length=40), nullable=False),
    sa.Column('auth_password', sa.Text(), nullable=False),
    sa.Column('perm_users', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('perm_checkpassword', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('perm_mail_aliases', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('perm_remailer', sa.Boolean(create_constraint=True), nullable=False),
    sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_api_client_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_api_client')),
    sa.UniqueConstraint('auth_username', name=op.f('uq_api_client_auth_username'))
	)
	service = sa.Table('service', meta,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('limit_access', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('access_group_id', sa.Integer(), nullable=True),
    sa.Column('use_remailer', sa.Boolean(create_constraint=True), nullable=False),
    sa.ForeignKeyConstraint(['access_group_id'], ['group.id'], name=op.f('fk_service_access_group_id_group'), onupdate='CASCADE', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_service')),
    sa.UniqueConstraint('name', name=op.f('uq_service_name'))
	)
	with op.batch_alter_table('service', copy_from=service) as batch_op:
		batch_op.drop_column('use_remailer')
	with op.batch_alter_table('api_client', copy_from=api_client) as batch_op:
		batch_op.drop_column('perm_remailer')
