"""Per-service email preferences

Revision ID: e13b733ec856
Revises: b273d7fdaa25
Create Date: 2022-10-17 02:13:11.598210

"""
from alembic import op
import sqlalchemy as sa

revision = 'e13b733ec856'
down_revision = 'b273d7fdaa25'
branch_labels = None
depends_on = None

def upgrade():
	with op.batch_alter_table('service', schema=None) as batch_op:
		batch_op.add_column(sa.Column('enable_email_preferences', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()))
	with op.batch_alter_table('service_user', schema=None) as batch_op:
		batch_op.add_column(sa.Column('service_email_id', sa.Integer(), nullable=True))
		batch_op.create_foreign_key(batch_op.f('fk_service_user_service_email_id_user_email'), 'user_email', ['service_email_id'], ['id'], onupdate='CASCADE', ondelete='SET NULL')
	meta = sa.MetaData()
	service = sa.Table('service', meta,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('limit_access', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('access_group_id', sa.Integer(), nullable=True),
    sa.Column('use_remailer', sa.Boolean(create_constraint=True), nullable=False),
    sa.Column('enable_email_preferences', sa.Boolean(create_constraint=True), nullable=False, server_default=sa.false()),
    sa.ForeignKeyConstraint(['access_group_id'], ['group.id'], name=op.f('fk_service_access_group_id_group'), onupdate='CASCADE', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_service')),
    sa.UniqueConstraint('name', name=op.f('uq_service_name'))
	)
	with op.batch_alter_table('service', copy_from=service) as batch_op:
		batch_op.alter_column('enable_email_preferences', server_default=None)

def downgrade():
	with op.batch_alter_table('service_user', schema=None) as batch_op:
		batch_op.drop_constraint(batch_op.f('fk_service_user_service_email_id_user_email'), type_='foreignkey')
		batch_op.drop_column('service_email_id')
	with op.batch_alter_table('service', schema=None) as batch_op:
		batch_op.drop_column('enable_email_preferences')
