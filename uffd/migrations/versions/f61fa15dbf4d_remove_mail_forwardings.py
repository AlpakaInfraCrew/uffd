"""Remove mail forwardings

Revision ID: f61fa15dbf4d
Revises: d63d9eb1fe94
Create Date: 2026-10-18 16:02:45.674761

"""
from alembic import op
import sqlalchemy as sa
from flask import current_app

revision = 'f61fa15dbf4d'
down_revision = 'd63d9eb1fe94'
branch_labels = None
depends_on = None

def upgrade():
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
		sa.Column('perm_metrics', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()),
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_api_client_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_api_client')),
		sa.UniqueConstraint('auth_username', name=op.f('uq_api_client_auth_username'))
	)
	mail = sa.table('mail',
		sa.column('id', sa.Integer),
	)
	result = op.get_bind().execute(mail.select())
	if result.fetchall() and not current_app.config.get('DELETE_ALL_MAIL_FORWARDINGS'):
		raise Exception('Refusing to run migration: Would delete existing mail forwardings. Set config option DELETE_ALL_MAIL_FORWARDINGS=True to delete all mail forwardings and continue the migration.')
	op.drop_table('mail_destination_address')
	op.drop_table('mail_receive_address')
	op.drop_table('mail')
	with op.batch_alter_table('api_client', copy_from=api_client) as batch_op:
		batch_op.drop_column('perm_mail_aliases')

def downgrade():
	meta = sa.MetaData()
	api_client = sa.Table('api_client', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('service_id', sa.Integer(), nullable=False),
		sa.Column('auth_username', sa.String(length=40), nullable=False),
		sa.Column('auth_password', sa.Text(), nullable=False),
		sa.Column('perm_users', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('perm_checkpassword', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('perm_remailer', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('perm_metrics', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()),
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_api_client_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_api_client')),
		sa.UniqueConstraint('auth_username', name=op.f('uq_api_client_auth_username'))
	)
	with op.batch_alter_table('api_client', copy_from=api_client) as batch_op:
		batch_op.add_column(sa.Column('perm_mail_aliases', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()))
	meta = sa.MetaData()
	api_client = sa.Table('api_client', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('service_id', sa.Integer(), nullable=False),
		sa.Column('auth_username', sa.String(length=40), nullable=False),
		sa.Column('auth_password', sa.Text(), nullable=False),
		sa.Column('perm_users', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('perm_checkpassword', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('perm_remailer', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('perm_metrics', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()),
		sa.Column('perm_mail_aliases', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()),
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_api_client_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_api_client')),
		sa.UniqueConstraint('auth_username', name=op.f('uq_api_client_auth_username'))
	)
	with op.batch_alter_table('api_client', copy_from=api_client) as batch_op:
		batch_op.alter_column('perm_mail_aliases', existing_type=sa.Boolean(create_constraint=True), nullable=False)
	op.create_table('mail',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('uid', sa.String(length=32), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mail')),
		sa.UniqueConstraint('uid', name=op.f('uq_mail_uid'))
	)
	op.create_table('mail_receive_address',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('mail_id', sa.Integer(), nullable=False),
		sa.Column('address', sa.String(length=128), nullable=False),
		sa.ForeignKeyConstraint(['mail_id'], ['mail.id'], name=op.f('fk_mail_receive_address_mail_id_mail'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mail_receive_address'))
	)
	op.create_table('mail_destination_address',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('mail_id', sa.Integer(), nullable=False),
		sa.Column('address', sa.String(length=128), nullable=False),
		sa.ForeignKeyConstraint(['mail_id'], ['mail.id'], name=op.f('fk_mail_destination_address_mail_id_mail'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mail_destination_address'))
	)
