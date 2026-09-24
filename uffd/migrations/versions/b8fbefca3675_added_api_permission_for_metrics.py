"""added api permission for metrics

Revision ID: b8fbefca3675
Revises: f2eb2c52a61f
Create Date: 2022-08-22 21:30:19.265531

"""
from alembic import op
import sqlalchemy as sa

revision = 'b8fbefca3675'
down_revision = 'f2eb2c52a61f'
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
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_api_client_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_api_client')),
		sa.UniqueConstraint('auth_username', name=op.f('uq_api_client_auth_username'))
	)
	with op.batch_alter_table('api_client', copy_from=api_client) as batch_op:
		batch_op.add_column(sa.Column('perm_metrics', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()))

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
		sa.Column('perm_metrics', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()),
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_api_client_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_api_client')),
		sa.UniqueConstraint('auth_username', name=op.f('uq_api_client_auth_username'))
	)
	with op.batch_alter_table('api_client', copy_from=api_client) as batch_op:
		batch_op.drop_column('perm_metrics')
