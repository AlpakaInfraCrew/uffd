"""Add ServiceUser

Revision ID: f2eb2c52a61f
Revises: 9f824f61d8ac
Create Date: 2022-08-21 00:42:37.896970

"""
from alembic import op
import sqlalchemy as sa

revision = 'f2eb2c52a61f'
down_revision = '9f824f61d8ac'
branch_labels = None
depends_on = None

def upgrade():
	service_user = op.create_table('service_user',
		sa.Column('service_id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_service_user_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_service_user_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('service_id', 'user_id', name=op.f('pk_service_user'))
	)
	service = sa.table('service', sa.column('id'))
	user = sa.table('user', sa.column('id'))
	op.execute(service_user.insert().from_select(
		['service_id', 'user_id'],
		sa.select(service.c.id, user.c.id).select_from(sa.join(service, user, sa.true()))
	))

def downgrade():
	op.drop_table('service_user')
