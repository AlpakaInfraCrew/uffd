"""Add id to signup table

Revision ID: bf71799b7b9e
Revises: e9a67175e179
Create Date: 2021-09-06 23:30:07.486102

"""
from alembic import op
import sqlalchemy as sa

revision = 'bf71799b7b9e'
down_revision = 'e9a67175e179'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData()
	invite_signup = sa.Table('invite_signup', meta,
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('invite_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['invite_id'], ['invite.id'], name=op.f('fk_invite_signup_invite_id_invite')),
		sa.ForeignKeyConstraint(['token'], ['signup.token'], name=op.f('fk_invite_signup_token_signup')),
		sa.PrimaryKeyConstraint('token', name=op.f('pk_invite_signup'))
	)
	with op.batch_alter_table(invite_signup.name, copy_from=invite_signup) as batch_op:
		batch_op.add_column(sa.Column('id', sa.Integer(), nullable=True))
		batch_op.drop_constraint('fk_invite_signup_token_signup', 'foreignkey')

	meta = sa.MetaData()
	signup = sa.Table('signup', meta,
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
	with op.batch_alter_table(signup.name, copy_from=signup, recreate='always') as batch_op:
		batch_op.drop_constraint('pk_signup', 'primary')
		batch_op.add_column(sa.Column('id', sa.Integer(), nullable=True))
		batch_op.create_primary_key('pk_signup', ['id'])
		batch_op.alter_column('id', autoincrement=True, nullable=False, existing_type=sa.Integer())

	meta = sa.MetaData()
	signup = sa.Table('signup', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('loginname', sa.Text(), nullable=True),
		sa.Column('displayname', sa.Text(), nullable=True),
		sa.Column('mail', sa.Text(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('user_dn', sa.String(length=128), nullable=True),
		sa.Column('type', sa.String(length=50), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_signup'))
	)
	invite_signup = sa.Table('invite_signup', meta,
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('invite_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['invite_id'], ['invite.id'], name=op.f('fk_invite_signup_invite_id_invite')),
		sa.PrimaryKeyConstraint('token', name=op.f('pk_invite_signup'))
	)
	op.execute(invite_signup.update().values(id=sa.select(signup.c.id).where(signup.c.token==invite_signup.c.token).limit(1).as_scalar()))
	with op.batch_alter_table(invite_signup.name, copy_from=invite_signup) as batch_op:
		batch_op.alter_column('id', nullable=False, existing_type=sa.Integer())
		batch_op.create_foreign_key(batch_op.f('fk_invite_signup_id_signup'), 'signup', ['id'], ['id'])
		batch_op.drop_constraint('pk_invite_signup', 'primary')
		batch_op.drop_column('token')
		batch_op.create_primary_key('pk_invite_signup', ['id'])

def downgrade():
	meta = sa.MetaData()
	invite_signup = sa.Table('invite_signup', meta,
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('invite_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['invite_id'], ['invite.id'], name=op.f('fk_invite_signup_invite_id_invite')),
		sa.ForeignKeyConstraint(['id'], ['signup.id'], name=op.f('fk_invite_signup_id_signup')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_invite_signup'))
	)
	with op.batch_alter_table(invite_signup.name, copy_from=invite_signup) as batch_op:
		batch_op.add_column(sa.Column('token', sa.VARCHAR(length=128), nullable=True))
		batch_op.drop_constraint('fk_invite_signup_id_signup', type_='foreignkey')

	meta = sa.MetaData()
	signup = sa.Table('signup', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('loginname', sa.Text(), nullable=True),
		sa.Column('displayname', sa.Text(), nullable=True),
		sa.Column('mail', sa.Text(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('user_dn', sa.String(length=128), nullable=True),
		sa.Column('type', sa.String(length=50), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_signup'))
	)
	with op.batch_alter_table(signup.name, copy_from=signup) as batch_op:
		batch_op.alter_column('id', autoincrement=False, existing_type=sa.Integer())
		batch_op.drop_constraint('pk_signup', 'primary')
		batch_op.create_primary_key('pk_signup', ['token'])

	meta = sa.MetaData()
	signup = sa.Table('signup', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('loginname', sa.Text(), nullable=True),
		sa.Column('displayname', sa.Text(), nullable=True),
		sa.Column('mail', sa.Text(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('user_dn', sa.String(length=128), nullable=True),
		sa.Column('type', sa.String(length=50), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_signup'))
	)
	invite_signup = sa.Table('invite_signup', meta,
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('invite_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['invite_id'], ['invite.id'], name=op.f('fk_invite_signup_invite_id_invite')),
		sa.ForeignKeyConstraint(['id'], ['signup.id'], name=op.f('fk_invite_signup_id_signup')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_invite_signup'))
	)
	op.execute(invite_signup.update().values(token=sa.select(signup.c.token).where(signup.c.id==invite_signup.c.id).limit(1).as_scalar()))
	with op.batch_alter_table(invite_signup.name, copy_from=invite_signup) as batch_op:
		batch_op.create_foreign_key(batch_op.f('fk_invite_signup_token_signup'), 'signup', ['token'], ['token'])
		batch_op.drop_constraint('pk_invite_signup', 'primary')
		batch_op.drop_column('id')
		batch_op.create_primary_key('pk_invite_signup', ['token'])

	meta = sa.MetaData()
	signup = sa.Table('signup', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('loginname', sa.Text(), nullable=True),
		sa.Column('displayname', sa.Text(), nullable=True),
		sa.Column('mail', sa.Text(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('user_dn', sa.String(length=128), nullable=True),
		sa.Column('type', sa.String(length=50), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_signup'))
	)
	with op.batch_alter_table(signup.name, copy_from=signup) as batch_op:
		batch_op.drop_column('id')
