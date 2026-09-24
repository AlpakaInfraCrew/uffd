"""Remailer v2

Revision ID: 2b68f688bec1
Revises: e13b733ec856
Create Date: 2022-10-20 03:40:11.522343

"""
from alembic import op
import sqlalchemy as sa

revision = '2b68f688bec1'
down_revision = 'e13b733ec856'
branch_labels = None
depends_on = None

def upgrade():
	with op.batch_alter_table('service', schema=None) as batch_op:
		batch_op.add_column(sa.Column('remailer_mode', sa.Enum('DISABLED', 'ENABLED_V1', 'ENABLED_V2', create_constraint=True, name='remailermode'), nullable=False, server_default='DISABLED'))
	service = sa.table('service',
		sa.column('id', sa.Integer),
		sa.column('use_remailer', sa.Boolean(create_constraint=True)),
		sa.column('remailer_mode', sa.Enum('DISABLED', 'ENABLED_V1', 'ENABLED_V2', create_constraint=True, name='remailermode')),
	)
	op.execute(service.update().values(remailer_mode='ENABLED_V1').where(service.c.use_remailer))
	meta = sa.MetaData()
	service = sa.Table('service', meta,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('limit_access', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('access_group_id', sa.Integer(), nullable=True),
    sa.Column('use_remailer', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('enable_email_preferences', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('remailer_mode', sa.Enum('DISABLED', 'ENABLED_V1', 'ENABLED_V2', create_constraint=True, name='remailermode'), nullable=False, server_default='DISABLED'),
    sa.ForeignKeyConstraint(['access_group_id'], ['group.id'], name=op.f('fk_service_access_group_id_group'), onupdate='CASCADE', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_service')),
    sa.UniqueConstraint('name', name=op.f('uq_service_name'))
	)
	with op.batch_alter_table('service', copy_from=service) as batch_op:
		batch_op.alter_column('remailer_mode', server_default=None)
		batch_op.drop_column('use_remailer')

def downgrade():
	with op.batch_alter_table('service', schema=None) as batch_op:
		batch_op.add_column(sa.Column('use_remailer', sa.BOOLEAN(), nullable=False, server_default=sa.false()))
	service = sa.table('service',
		sa.column('id', sa.Integer),
		sa.column('use_remailer', sa.Boolean(create_constraint=True)),
		sa.column('remailer_mode', sa.Enum('DISABLED', 'ENABLED_V1', 'ENABLED_V2', create_constraint=True, name='remailermode')),
	)
	op.execute(service.update().values(use_remailer=sa.true()).where(service.c.remailer_mode != 'DISABLED'))
	meta = sa.MetaData()
	service = sa.Table('service', meta,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('limit_access', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('access_group_id', sa.Integer(), nullable=True),
    sa.Column('use_remailer', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()),
    sa.Column('enable_email_preferences', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('remailer_mode', sa.Enum('DISABLED', 'ENABLED_V1', 'ENABLED_V2', create_constraint=True, name='remailermode'), nullable=False),
    sa.ForeignKeyConstraint(['access_group_id'], ['group.id'], name=op.f('fk_service_access_group_id_group'), onupdate='CASCADE', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_service')),
    sa.UniqueConstraint('name', name=op.f('uq_service_name'))
	)
	with op.batch_alter_table('service', copy_from=service) as batch_op:
		batch_op.alter_column('use_remailer', server_default=None)
		batch_op.drop_column('remailer_mode')
