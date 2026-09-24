"""unified password hashing for User and Signup

Revision ID: af07cea65391
Revises: 042879d5e3ac
Create Date: 2022-02-11 23:55:35.502529

"""
from alembic import op
import sqlalchemy as sa

revision = 'af07cea65391'
down_revision = '042879d5e3ac'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData()
	signup = sa.Table('signup', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('loginname', sa.Text(), nullable=True),
		sa.Column('displayname', sa.Text(), nullable=True),
		sa.Column('mail', sa.Text(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('type', sa.String(length=50), nullable=True),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_signup_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_signup')),
		sa.UniqueConstraint('user_id', name=op.f('uq_signup_user_id'))
	)

	user = sa.Table('user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_uid', sa.Integer(), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=False),
		sa.Column('displayname', sa.String(length=128), nullable=False),
		sa.Column('mail', sa.String(length=128), nullable=False),
		sa.Column('pwhash', sa.String(length=256), nullable=True),
		sa.Column('is_service_user', sa.Boolean(create_constraint=True), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
		sa.UniqueConstraint('loginname', name=op.f('uq_user_loginname')),
		sa.UniqueConstraint('unix_uid', name=op.f('uq_user_unix_uid'))
	)
	with op.batch_alter_table('user', copy_from=user) as batch_op:
		batch_op.alter_column('pwhash', existing_type=sa.String(length=256), type_=sa.Text())

	op.execute(signup.update().values(pwhash=('{crypt}' + signup.c.pwhash)))

def downgrade():
	meta = sa.MetaData()
	signup = sa.Table('signup', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('loginname', sa.Text(), nullable=True),
		sa.Column('displayname', sa.Text(), nullable=True),
		sa.Column('mail', sa.Text(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('type', sa.String(length=50), nullable=True),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_signup_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_signup')),
		sa.UniqueConstraint('user_id', name=op.f('uq_signup_user_id'))
	)

	user = sa.Table('user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('unix_uid', sa.Integer(), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=False),
		sa.Column('displayname', sa.String(length=128), nullable=False),
		sa.Column('mail', sa.String(length=128), nullable=False),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('is_service_user', sa.Boolean(create_constraint=True), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
		sa.UniqueConstraint('loginname', name=op.f('uq_user_loginname')),
		sa.UniqueConstraint('unix_uid', name=op.f('uq_user_unix_uid'))
	)
	with op.batch_alter_table('user', copy_from=user) as batch_op:
		batch_op.alter_column('pwhash', existing_type=sa.Text(), type_=sa.String(length=256))

	op.execute(signup.update().values(pwhash=None).where(sa.not_(signup.c.pwhash.ilike('{crypt}%'))))
	op.execute(signup.update().values(pwhash=sa.func.substr(signup.c.pwhash, len('{crypt}') + 1)).where(signup.c.pwhash.ilike('{crypt}%')))
