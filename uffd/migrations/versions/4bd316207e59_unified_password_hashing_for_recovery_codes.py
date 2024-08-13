"""Unified password hashing for recovery codes

Revision ID: 4bd316207e59
Revises: e71e29cc605a
Create Date: 2024-05-22 03:13:55.917641

"""
from alembic import op
import sqlalchemy as sa

revision = '4bd316207e59'
down_revision = 'e71e29cc605a'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData(bind=op.get_bind())
	mfa_method = sa.Table('mfa_method', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('type', sa.Enum('RECOVERY_CODE', 'TOTP', 'WEBAUTHN', name='mfatype', create_constraint=True), nullable=False),
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
	# This field was already unused before the change to unified password hashing. So this is unrelated cleanup.
	with op.batch_alter_table('mfa_method', copy_from=mfa_method) as batch_op:
		batch_op.drop_column('recovery_salt')
	op.execute(mfa_method.update().values(recovery_hash=('{crypt}' + mfa_method.c.recovery_hash)).where(mfa_method.c.type == 'RECOVERY_CODE'))

def downgrade():
	meta = sa.MetaData(bind=op.get_bind())
	mfa_method = sa.Table('mfa_method', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('type', sa.Enum('RECOVERY_CODE', 'TOTP', 'WEBAUTHN', name='mfatype', create_constraint=True), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('name', sa.String(length=128), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('recovery_hash', sa.String(length=256), nullable=True),
		sa.Column('totp_key', sa.String(length=64), nullable=True),
		sa.Column('totp_last_counter', sa.Integer(), nullable=True),
		sa.Column('webauthn_cred', sa.Text(), nullable=True),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_mfa_method_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mfa_method'))
	)
	with op.batch_alter_table('mfa_method', copy_from=mfa_method) as batch_op:
		batch_op.add_column(sa.Column('recovery_salt', sa.VARCHAR(length=64), nullable=True))
	op.execute(
		mfa_method.delete().where(sa.and_(
			mfa_method.c.type == 'RECOVERY_CODE',
			sa.not_(mfa_method.c.recovery_hash.ilike('{crypt}%'))
		))
	)
	op.execute(
		mfa_method.update().values(
			recovery_hash=sa.func.substr(mfa_method.c.recovery_hash, len('{crypt}') + 1)
		).where(sa.and_(
			mfa_method.c.type == 'RECOVERY_CODE',
			mfa_method.c.recovery_hash.ilike('{crypt}%')
		))
	)
