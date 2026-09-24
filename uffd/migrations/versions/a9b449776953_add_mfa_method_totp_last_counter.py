"""Add mfa_method.totp_last_counter

Revision ID: a9b449776953
Revises: 23293f32b503
Create Date: 2023-11-07 12:09:23.843865

"""
from alembic import op
import sqlalchemy as sa

revision = 'a9b449776953'
down_revision = '23293f32b503'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData()
	mfa_method = sa.Table('mfa_method', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('type', sa.Enum('RECOVERY_CODE', 'TOTP', 'WEBAUTHN', create_constraint=True, name='ck_mfa_method_type'), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('name', sa.String(length=128), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('recovery_salt', sa.String(length=64), nullable=True),
		sa.Column('recovery_hash', sa.String(length=256), nullable=True),
		sa.Column('totp_key', sa.String(length=64), nullable=True),
		sa.Column('webauthn_cred', sa.Text(), nullable=True),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_mfa_method_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mfa_method'))
	)
	with op.batch_alter_table('mfa_method', copy_from=mfa_method) as batch_op:
		batch_op.add_column(sa.Column('totp_last_counter', sa.Integer(), nullable=True))

def downgrade():
	meta = sa.MetaData()
	mfa_method = sa.Table('mfa_method', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('type', sa.Enum('RECOVERY_CODE', 'TOTP', 'WEBAUTHN', create_constraint=True, name='ck_mfa_method_type'), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('name', sa.String(length=128), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('recovery_salt', sa.String(length=64), nullable=True),
		sa.Column('recovery_hash', sa.String(length=256), nullable=True),
		sa.Column('totp_key', sa.String(length=64), nullable=True),
		sa.Column('totp_last_counter', sa.Integer(), nullable=True),
		sa.Column('webauthn_cred', sa.Text(), nullable=True),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_mfa_method_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mfa_method'))
	)
	with op.batch_alter_table('mfa_method', copy_from=mfa_method) as batch_op:
		batch_op.drop_column('totp_last_counter')
