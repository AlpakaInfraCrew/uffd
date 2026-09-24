"""Migrate device login from user to session

Revision ID: 99df71f0f4a0
Revises: 87cb93a329bf
Create Date: 2024-05-18 16:41:33.923207

"""
from alembic import op
import sqlalchemy as sa

revision = '99df71f0f4a0'
down_revision = '87cb93a329bf'
branch_labels = None
depends_on = None

def upgrade():
	op.drop_table('device_login_confirmation')
	op.create_table('device_login_confirmation',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('initiation_id', sa.Integer(), nullable=False),
		sa.Column('session_id', sa.Integer(), nullable=False),
		sa.Column('code0', sa.String(length=32), nullable=False),
		sa.Column('code1', sa.String(length=32), nullable=False),
		sa.ForeignKeyConstraint(['initiation_id'], ['device_login_initiation.id'], name='fk_device_login_confirmation_initiation_id_', onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['session_id'], ['session.id'], name=op.f('fk_device_login_confirmation_session_id_session'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_device_login_confirmation')),
		sa.UniqueConstraint('initiation_id', 'code0', name='uq_device_login_confirmation_initiation_id_code0'),
		sa.UniqueConstraint('initiation_id', 'code1', name='uq_device_login_confirmation_initiation_id_code1'),
		sa.UniqueConstraint('session_id', name=op.f('uq_device_login_confirmation_session_id'))
	)

def downgrade():
	# We don't drop and recreate the table here to improve fuzzy migration test coverage
	with op.batch_alter_table('device_login_confirmation', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
	meta = sa.MetaData()
	device_login_confirmation = sa.Table('device_login_confirmation', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('initiation_id', sa.Integer(), nullable=False),
		sa.Column('session_id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('code0', sa.String(length=32), nullable=False),
		sa.Column('code1', sa.String(length=32), nullable=False),
		sa.ForeignKeyConstraint(['initiation_id'], ['device_login_initiation.id'], name='fk_device_login_confirmation_initiation_id_', onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['session_id'], ['session.id'], name=op.f('fk_device_login_confirmation_session_id_session'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_device_login_confirmation')),
		sa.UniqueConstraint('initiation_id', 'code0', name='uq_device_login_confirmation_initiation_id_code0'),
		sa.UniqueConstraint('initiation_id', 'code1', name='uq_device_login_confirmation_initiation_id_code1'),
		sa.UniqueConstraint('session_id', name=op.f('uq_device_login_confirmation_session_id'))
	)
	session = sa.table('session',
		sa.column('id', sa.Integer),
		sa.column('user_id', sa.Integer()),
	)
	op.execute(device_login_confirmation.update().values(user_id=sa.select(session.c.user_id).where(device_login_confirmation.c.session_id==session.c.id).as_scalar()))
	op.execute(device_login_confirmation.delete().where(device_login_confirmation.c.user_id==None))
	with op.batch_alter_table('device_login_confirmation', copy_from=device_login_confirmation) as batch_op:
		batch_op.alter_column('user_id', nullable=False, existing_type=sa.Integer())
		batch_op.create_foreign_key('fk_device_login_confirmation_user_id_user', 'user', ['user_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.create_unique_constraint('uq_device_login_confirmation_user_id', ['user_id'])
		batch_op.drop_constraint(batch_op.f('fk_device_login_confirmation_session_id_session'), type_='foreignkey')
		batch_op.drop_constraint(batch_op.f('uq_device_login_confirmation_session_id'), type_='unique')
		batch_op.drop_column('session_id')
