"""Remailer mode overwrite

Revision ID: e249233e2a31
Revises: aeb07202a6c8
Create Date: 2022-11-05 03:42:38.036623

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e249233e2a31'
down_revision = 'aeb07202a6c8'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData()
	service_user = sa.Table('service_user', meta,
		sa.Column('service_id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('service_email_id', sa.Integer(), nullable=True),
		sa.ForeignKeyConstraint(['service_email_id'], ['user_email.id'], name=op.f('fk_service_user_service_email_id_user_email'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_service_user_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_service_user_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('service_id', 'user_id', name=op.f('pk_service_user'))
	)
	with op.batch_alter_table('service_user', copy_from=service_user) as batch_op:
		batch_op.add_column(sa.Column('remailer_overwrite_mode', sa.Enum('DISABLED', 'ENABLED_V1', 'ENABLED_V2', create_constraint=True, name='remailermode'), nullable=True))

def downgrade():
	meta = sa.MetaData()
	service_user = sa.Table('service_user', meta,
		sa.Column('service_id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('remailer_overwrite_mode', sa.Enum('DISABLED', 'ENABLED_V1', 'ENABLED_V2', create_constraint=True, name='remailermode'), nullable=True),
		sa.Column('service_email_id', sa.Integer(), nullable=True),
		sa.ForeignKeyConstraint(['service_email_id'], ['user_email.id'], name=op.f('fk_service_user_service_email_id_user_email'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_service_user_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_service_user_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('service_id', 'user_id', name=op.f('pk_service_user'))
	)
	with op.batch_alter_table('service_user', copy_from=service_user) as batch_op:
		batch_op.drop_column('remailer_overwrite_mode')
