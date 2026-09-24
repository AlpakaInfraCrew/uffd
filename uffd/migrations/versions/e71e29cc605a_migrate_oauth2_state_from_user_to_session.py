"""Migrate oauth2 state from user to session

Revision ID: e71e29cc605a
Revises: 99df71f0f4a0
Create Date: 2024-05-18 21:59:20.435912

"""
from alembic import op
import sqlalchemy as sa

revision = 'e71e29cc605a'
down_revision = '99df71f0f4a0'
branch_labels = None
depends_on = None

def upgrade():
	op.drop_table('oauth2grant')
	op.drop_table('oauth2token')
	op.create_table('oauth2grant',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('session_id', sa.Integer(), nullable=False),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('code', sa.String(length=255), nullable=False),
		sa.Column('redirect_uri', sa.String(length=255), nullable=True),
		sa.Column('nonce', sa.Text(), nullable=True),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.Column('claims', sa.Text(), nullable=True),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2grant_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['session_id'], ['session.id'], name=op.f('fk_oauth2grant_session_id_session'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2grant'))
	)
	op.create_table('oauth2token',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('session_id', sa.Integer(), nullable=False),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('token_type', sa.String(length=40), nullable=False),
		sa.Column('access_token', sa.String(length=255), nullable=False),
		sa.Column('refresh_token', sa.String(length=255), nullable=False),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.Column('claims', sa.Text(), nullable=True),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2token_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['session_id'], ['session.id'], name=op.f('fk_oauth2token_session_id_session'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2token')),
		sa.UniqueConstraint('access_token', name=op.f('uq_oauth2token_access_token')),
		sa.UniqueConstraint('refresh_token', name=op.f('uq_oauth2token_refresh_token'))
	)

def downgrade():
	# We don't drop and recreate the table here to improve fuzzy migration test coverage
	meta = sa.MetaData()
	session = sa.table('session',
		sa.column('id', sa.Integer),
		sa.column('user_id', sa.Integer()),
	)

	with op.batch_alter_table('oauth2token', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_id', sa.INTEGER(), nullable=True))
	oauth2token = sa.Table('oauth2token', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('session_id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('token_type', sa.String(length=40), nullable=False),
		sa.Column('access_token', sa.String(length=255), nullable=False),
		sa.Column('refresh_token', sa.String(length=255), nullable=False),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.Column('claims', sa.Text(), nullable=True),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2token_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['session_id'], ['session.id'], name=op.f('fk_oauth2token_session_id_session'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2token')),
		sa.UniqueConstraint('access_token', name=op.f('uq_oauth2token_access_token')),
		sa.UniqueConstraint('refresh_token', name=op.f('uq_oauth2token_refresh_token'))
	)
	op.execute(oauth2token.update().values(user_id=sa.select(session.c.user_id).where(oauth2token.c.session_id==session.c.id).as_scalar()))
	op.execute(oauth2token.delete().where(oauth2token.c.user_id==None))
	with op.batch_alter_table('oauth2token', copy_from=oauth2token) as batch_op:
		batch_op.alter_column('user_id', nullable=False, existing_type=sa.Integer())
		batch_op.create_foreign_key('fk_oauth2token_user_id_user', 'user', ['user_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.drop_constraint(batch_op.f('fk_oauth2token_session_id_session'), type_='foreignkey')
		batch_op.drop_column('session_id')

	with op.batch_alter_table('oauth2grant', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_id', sa.INTEGER(), nullable=True))
	oauth2grant = sa.Table('oauth2grant', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('session_id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('code', sa.String(length=255), nullable=False),
		sa.Column('redirect_uri', sa.String(length=255), nullable=True),
		sa.Column('nonce', sa.Text(), nullable=True),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.Column('claims', sa.Text(), nullable=True),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2grant_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['session_id'], ['session.id'], name=op.f('fk_oauth2grant_session_id_session'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2grant'))
	)
	op.execute(oauth2grant.update().values(user_id=sa.select(session.c.user_id).where(oauth2grant.c.session_id==session.c.id).as_scalar()))
	op.execute(oauth2grant.delete().where(oauth2grant.c.user_id==None))
	with op.batch_alter_table('oauth2grant', copy_from=oauth2grant) as batch_op:
		batch_op.alter_column('user_id', nullable=False, existing_type=sa.Integer())
		batch_op.create_foreign_key('fk_oauth2grant_user_id_user', 'user', ['user_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.drop_constraint(batch_op.f('fk_oauth2grant_session_id_session'), type_='foreignkey')
		batch_op.drop_column('session_id')
