"""constraint name fixes

Revision ID: cbca20cf64d9
Revises: 
Create Date: 2021-04-13 18:10:58.210232

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'cbca20cf64d9'
down_revision = '5a07d4a63b64'
branch_labels = None
depends_on = None

def upgrade():
	# This migration recreates all tables with identical columns and constraints.
	# The only difference is that all contraints are named according to the newly
	# defined naming conventions. This enables changing constraints in future
	# migrations.
	#
	# We call batch_alter_table without any operations to have it recreate all
	# tables with the column/constraint definitions from "table" and populate it
	# with the data from the original table.

	# First recreate tables that have (unnamed) foreign keys without any foreign keys
	meta = sa.MetaData()
	table = sa.Table('invite_grant', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('invite_token', sa.String(length=128), nullable=False),
		sa.Column('user_dn', sa.String(length=128), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_invite_grant'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('invite_roles', meta,
		sa.Column('invite_token', sa.String(length=128), nullable=False),
		sa.Column('role_id', sa.Integer(), nullable=False),
		sa.PrimaryKeyConstraint('invite_token', 'role_id', name=op.f('pk_invite_roles'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('invite_signup', meta,
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('invite_token', sa.String(length=128), nullable=False),
		sa.PrimaryKeyConstraint('token', name=op.f('pk_invite_signup'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('role-group', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=True),
		sa.Column('role_id', sa.Integer(), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_role-group')),
		sa.UniqueConstraint('dn', 'role_id', name=op.f('uq_role-group_dn'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('role-inclusion', meta,
		sa.Column('role_id', sa.Integer(), nullable=False),
		sa.Column('included_role_id', sa.Integer(), nullable=False),
		sa.PrimaryKeyConstraint('role_id', 'included_role_id', name=op.f('pk_role-inclusion'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('role-user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=True),
		sa.Column('role_id', sa.Integer(), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_role-user')),
		sa.UniqueConstraint('dn', 'role_id', name=op.f('uq_role-user_dn'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass

	# Then recreate all tables with properly named constraints and readd foreign key constraints
	meta = sa.MetaData()
	table = sa.Table('invite', meta,
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('valid_until', sa.DateTime(), nullable=False),
		sa.Column('single_use', sa.Boolean(create_constraint=True, name=op.f('ck_invite_single_use')), nullable=False),
		sa.Column('allow_signup', sa.Boolean(create_constraint=True, name=op.f('ck_invite_allow_signup')), nullable=False),
		sa.Column('used', sa.Boolean(create_constraint=True, name=op.f('ck_invite_used')), nullable=False),
		sa.Column('disabled', sa.Boolean(create_constraint=True, name=op.f('ck_invite_disabled')), nullable=False),
		sa.PrimaryKeyConstraint('token', name=op.f('pk_invite'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('mailToken', meta,
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=True),
		sa.Column('loginname', sa.String(length=32), nullable=True),
		sa.Column('newmail', sa.String(length=255), nullable=True),
		sa.PrimaryKeyConstraint('token', name=op.f('pk_mailToken'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('mfa_method', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('type', sa.Enum('RECOVERY_CODE', 'TOTP', 'WEBAUTHN', create_constraint=True, name='mfatype'), nullable=True),
		sa.Column('created', sa.DateTime(), nullable=True),
		sa.Column('name', sa.String(length=128), nullable=True),
		sa.Column('dn', sa.String(length=128), nullable=True),
		sa.Column('recovery_salt', sa.String(length=64), nullable=True),
		sa.Column('recovery_hash', sa.String(length=256), nullable=True),
		sa.Column('totp_key', sa.String(length=64), nullable=True),
		sa.Column('webauthn_cred', sa.Text(), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mfa_method'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('oauth2grant', meta,
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('user_dn', sa.String(length=128), nullable=True),
		sa.Column('client_id', sa.String(length=40), nullable=True),
		sa.Column('code', sa.String(length=255), nullable=False),
		sa.Column('redirect_uri', sa.String(length=255), nullable=True),
		sa.Column('expires', sa.DateTime(), nullable=True),
		sa.Column('_scopes', sa.Text(), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2grant'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('oauth2token', meta,
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('user_dn', sa.String(length=128), nullable=True),
		sa.Column('client_id', sa.String(length=40), nullable=True),
		sa.Column('token_type', sa.String(length=40), nullable=True),
		sa.Column('access_token', sa.String(length=255), nullable=True),
		sa.Column('refresh_token', sa.String(length=255), nullable=True),
		sa.Column('expires', sa.DateTime(), nullable=True),
		sa.Column('_scopes', sa.Text(), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2token')),
		sa.UniqueConstraint('access_token', name=op.f('uq_oauth2token_access_token')),
		sa.UniqueConstraint('refresh_token', name=op.f('uq_oauth2token_refresh_token'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('passwordToken', meta,
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=True),
		sa.Column('loginname', sa.String(length=32), nullable=True),
		sa.PrimaryKeyConstraint('token', name=op.f('pk_passwordToken'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('ratelimit_event', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('timestamp', sa.DateTime(), nullable=True),
		sa.Column('name', sa.String(length=128), nullable=True),
		sa.Column('key', sa.String(length=128), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_ratelimit_event'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('role', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('name', sa.String(length=32), nullable=True),
		sa.Column('description', sa.Text(), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_role')),
		sa.UniqueConstraint('name', name=op.f('uq_role_name'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('signup', meta,
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('loginname', sa.Text(), nullable=True),
		sa.Column('displayname', sa.Text(), nullable=True),
		sa.Column('mail', sa.Text(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('user_dn', sa.String(length=128), nullable=True),
		sa.Column('type', sa.String(length=50), nullable=True),
		sa.PrimaryKeyConstraint('token', name=op.f('pk_signup'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('invite_grant', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('invite_token', sa.String(length=128), nullable=False),
		sa.Column('user_dn', sa.String(length=128), nullable=False),
		sa.ForeignKeyConstraint(['invite_token'], ['invite.token'], name=op.f('fk_invite_grant_invite_token_invite')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_invite_grant'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('invite_roles', meta,
		sa.Column('invite_token', sa.String(length=128), nullable=False),
		sa.Column('role_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['invite_token'], ['invite.token'], name=op.f('fk_invite_roles_invite_token_invite')),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_invite_roles_role_id_role')),
		sa.PrimaryKeyConstraint('invite_token', 'role_id', name=op.f('pk_invite_roles'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('invite_signup', meta,
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('invite_token', sa.String(length=128), nullable=False),
		sa.ForeignKeyConstraint(['invite_token'], ['invite.token'], name=op.f('fk_invite_signup_invite_token_invite')),
		sa.ForeignKeyConstraint(['token'], ['signup.token'], name=op.f('fk_invite_signup_token_signup')),
		sa.PrimaryKeyConstraint('token', name=op.f('pk_invite_signup'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('role-group', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=True),
		sa.Column('role_id', sa.Integer(), nullable=True),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role-group_role_id_role')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_role-group')),
		sa.UniqueConstraint('dn', 'role_id', name=op.f('uq_role-group_dn'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('role-inclusion', meta,
		sa.Column('role_id', sa.Integer(), nullable=False),
		sa.Column('included_role_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['included_role_id'], ['role.id'], name=op.f('fk_role-inclusion_included_role_id_role')),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role-inclusion_role_id_role')),
		sa.PrimaryKeyConstraint('role_id', 'included_role_id', name=op.f('pk_role-inclusion'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass
	table = sa.Table('role-user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=True),
		sa.Column('role_id', sa.Integer(), nullable=True),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role-user_role_id_role')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_role-user')),
		sa.UniqueConstraint('dn', 'role_id', name=op.f('uq_role-user_dn'))
	)
	with op.batch_alter_table(table.name, copy_from=table, recreate='always') as batch_op:
		pass

def downgrade():
	# upgrade only adds names to all constraints, no need to undo much
	with op.batch_alter_table('oauth2grant', schema=None) as batch_op:
		batch_op.create_index(batch_op.f('ix_oauth2grant_code'), ['code'], unique=False)
