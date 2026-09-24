"""invite pk change

Revision ID: 54b2413586fd
Revises: 2a6b1fb82ce6
Create Date: 2021-04-13 23:33:40.118507

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '54b2413586fd'
down_revision = '2a6b1fb82ce6'
branch_labels = None
depends_on = None

invite = sa.sql.table('invite',
	sa.sql.column('id', sa.Integer()),
	sa.sql.column('token', sa.String(length=128))
)
invite_grant = sa.sql.table('invite_grant',
	sa.sql.column('invite_id', sa.Integer()),
	sa.sql.column('invite_token', sa.String(length=128))
)
invite_roles = sa.sql.table('invite_roles',
	sa.sql.column('invite_id', sa.Integer()),
	sa.sql.column('invite_token', sa.String(length=128))
)
invite_signup = sa.sql.table('invite_signup',
	sa.sql.column('invite_id', sa.Integer()),
	sa.sql.column('invite_token', sa.String(length=128))
)

def upgrade():
	# CHECK constraints get lost when reflecting from the actual table
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
	with op.batch_alter_table('invite_grant', schema=None) as batch_op:
		batch_op.drop_constraint('fk_invite_grant_invite_token_invite', type_='foreignkey')
	with op.batch_alter_table('invite_roles', schema=None) as batch_op:
		batch_op.drop_constraint('fk_invite_roles_invite_token_invite', type_='foreignkey')
	with op.batch_alter_table('invite_signup', schema=None) as batch_op:
		batch_op.drop_constraint('fk_invite_signup_invite_token_invite', type_='foreignkey')
	with op.batch_alter_table('invite', copy_from=table, recreate='always') as batch_op:
		batch_op.drop_constraint(batch_op.f('pk_invite'), type_='primary')
		batch_op.add_column(sa.Column('id', sa.Integer(), nullable=True))
		batch_op.create_primary_key(batch_op.f('pk_invite'), ['id'])
		batch_op.alter_column('id', autoincrement=True, nullable=False, existing_type=sa.Integer())
		batch_op.create_unique_constraint(batch_op.f('uq_invite_token'), ['token'])
	with op.batch_alter_table('invite_grant', schema=None) as batch_op:
		batch_op.add_column(sa.Column('invite_id', sa.Integer(), nullable=True))
	with op.batch_alter_table('invite_roles', schema=None) as batch_op:
		batch_op.add_column(sa.Column('invite_id', sa.Integer(), nullable=True))
	with op.batch_alter_table('invite_signup', schema=None) as batch_op:
		batch_op.add_column(sa.Column('invite_id', sa.Integer(), nullable=True))

	op.execute(invite_grant.update().values(invite_id=sa.select(invite.c.id).where(invite.c.token==invite_grant.c.invite_token).as_scalar()))
	op.execute(invite_roles.update().values(invite_id=sa.select(invite.c.id).where(invite.c.token==invite_roles.c.invite_token).as_scalar()))
	op.execute(invite_signup.update().values(invite_id=sa.select(invite.c.id).where(invite.c.token==invite_signup.c.invite_token).as_scalar()))

	with op.batch_alter_table('invite_grant', schema=None) as batch_op:
		batch_op.alter_column('invite_id', existing_type=sa.INTEGER(), nullable=False)
		batch_op.create_foreign_key(batch_op.f('fk_invite_grant_invite_id_invite'), 'invite', ['invite_id'], ['id'])
		batch_op.drop_column('invite_token')
	with op.batch_alter_table('invite_roles', schema=None) as batch_op:
		batch_op.drop_constraint(batch_op.f('pk_invite_roles'), type_='primary')
		batch_op.create_primary_key(batch_op.f('pk_invite_roles'), ['invite_id', 'role_id'])
		batch_op.create_foreign_key(batch_op.f('fk_invite_roles_invite_id_invite'), 'invite', ['invite_id'], ['id'])
		batch_op.drop_column('invite_token')
	with op.batch_alter_table('invite_signup', schema=None) as batch_op:
		batch_op.alter_column('invite_id', existing_type=sa.INTEGER(), nullable=False)
		batch_op.create_foreign_key(batch_op.f('fk_invite_signup_invite_id_invite'), 'invite', ['invite_id'], ['id'])
		batch_op.drop_column('invite_token')

def downgrade():
	with op.batch_alter_table('invite_signup', schema=None) as batch_op:
		batch_op.drop_constraint(batch_op.f('fk_invite_signup_invite_id_invite'), type_='foreignkey')
		batch_op.add_column(sa.Column('invite_token', sa.VARCHAR(length=128), nullable=True))
	with op.batch_alter_table('invite_roles', schema=None) as batch_op:
		batch_op.drop_constraint(batch_op.f('fk_invite_roles_invite_id_invite'), type_='foreignkey')
		batch_op.add_column(sa.Column('invite_token', sa.VARCHAR(length=128), nullable=True))
	with op.batch_alter_table('invite_grant', schema=None) as batch_op:
		batch_op.drop_constraint(batch_op.f('fk_invite_grant_invite_id_invite'), type_='foreignkey')
		batch_op.add_column(sa.Column('invite_token', sa.VARCHAR(length=128), nullable=True))

	op.execute(invite_grant.update().values(invite_token=sa.select(invite.c.token).where(invite.c.id==invite_grant.c.invite_id).as_scalar()))
	op.execute(invite_roles.update().values(invite_token=sa.select(invite.c.token).where(invite.c.id==invite_roles.c.invite_id).as_scalar()))
	op.execute(invite_signup.update().values(invite_token=sa.select(invite.c.token).where(invite.c.id==invite_signup.c.invite_id).as_scalar()))

	with op.batch_alter_table('invite_signup', schema=None) as batch_op:
		batch_op.alter_column('invite_token', existing_type=sa.VARCHAR(length=128), nullable=False)
		batch_op.drop_column('invite_id')
	with op.batch_alter_table('invite_roles', schema=None) as batch_op:
		batch_op.alter_column('invite_token', existing_type=sa.VARCHAR(length=128), nullable=False)
		batch_op.drop_constraint(batch_op.f('pk_invite_roles'), type_='primary')
		batch_op.create_primary_key(batch_op.f('pk_invite_roles'), ['invite_token', 'role_id'])
		batch_op.drop_column('invite_id')
	with op.batch_alter_table('invite_grant', schema=None) as batch_op:
		batch_op.alter_column('invite_token', existing_type=sa.VARCHAR(length=128), nullable=False)
		batch_op.drop_column('invite_id')

	# CHECK constraints get lost when reflecting from the actual table
	meta = sa.MetaData()
	table = sa.Table('invite', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('valid_until', sa.DateTime(), nullable=False),
		sa.Column('single_use', sa.Boolean(create_constraint=True, name=op.f('ck_invite_single_use')), nullable=False),
		sa.Column('allow_signup', sa.Boolean(create_constraint=True, name=op.f('ck_invite_allow_signup')), nullable=False),
		sa.Column('used', sa.Boolean(create_constraint=True, name=op.f('ck_invite_used')), nullable=False),
		sa.Column('disabled', sa.Boolean(create_constraint=True, name=op.f('ck_invite_disabled')), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_invite')),
		sa.UniqueConstraint('token', name=op.f('uq_invite_token'))
	)
	with op.batch_alter_table('invite', copy_from=table, recreate='always') as batch_op:
		batch_op.drop_constraint(batch_op.f('uq_invite_token'), type_='unique')
		batch_op.alter_column('id', autoincrement=False, existing_type=sa.Integer())
		batch_op.drop_constraint(batch_op.f('pk_invite'), type_='primary')
		batch_op.drop_column('id')
		batch_op.create_primary_key(batch_op.f('pk_invite'), ['token'])
	with op.batch_alter_table('invite_signup', schema=None) as batch_op:
		batch_op.create_foreign_key('fk_invite_signup_invite_token_invite', 'invite', ['invite_token'], ['token'])
	with op.batch_alter_table('invite_roles', schema=None) as batch_op:
		batch_op.create_foreign_key('fk_invite_roles_invite_token_invite', 'invite', ['invite_token'], ['token'])
	with op.batch_alter_table('invite_grant', schema=None) as batch_op:
		batch_op.create_foreign_key('fk_invite_grant_invite_token_invite', 'invite', ['invite_token'], ['token'])
