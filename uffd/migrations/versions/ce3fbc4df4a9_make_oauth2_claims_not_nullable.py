"""Make OAuth2 claims not nullable

Revision ID: ce3fbc4df4a9
Revises: b9839ad4fd60
Create Date: 2026-03-08 22:54:34.984447

"""
from alembic import op
import sqlalchemy as sa

revision = 'ce3fbc4df4a9'
down_revision = 'b9839ad4fd60'
branch_labels = None
depends_on = None

def upgrade():
	meta = sa.MetaData()

	oauth2grant = sa.Table('oauth2grant', meta,
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
	op.execute(oauth2grant.update().values(claims='{}').where(oauth2grant.c.claims==None))
	with op.batch_alter_table('oauth2grant', schema=None) as batch_op:
		batch_op.alter_column('claims', existing_type=sa.TEXT(), nullable=False)

	oauth2token = sa.Table('oauth2token', meta,
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
	op.execute(oauth2token.update().values(claims='{}').where(oauth2token.c.claims==None))
	with op.batch_alter_table('oauth2token', schema=None) as batch_op:
		batch_op.alter_column('claims', existing_type=sa.TEXT(), nullable=False)

def downgrade():
	meta = sa.MetaData()

	oauth2grant = sa.Table('oauth2grant', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('session_id', sa.Integer(), nullable=False),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('code', sa.String(length=255), nullable=False),
		sa.Column('redirect_uri', sa.String(length=255), nullable=True),
		sa.Column('nonce', sa.Text(), nullable=True),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.Column('claims', sa.Text(), nullable=False),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2grant_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['session_id'], ['session.id'], name=op.f('fk_oauth2grant_session_id_session'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2grant'))
	)
	with op.batch_alter_table('oauth2token', schema=None) as batch_op:
		batch_op.alter_column('claims', existing_type=sa.TEXT(), nullable=True)

	oauth2token = sa.Table('oauth2token', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('session_id', sa.Integer(), nullable=False),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('token_type', sa.String(length=40), nullable=False),
		sa.Column('access_token', sa.String(length=255), nullable=False),
		sa.Column('refresh_token', sa.String(length=255), nullable=False),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.Column('claims', sa.Text(), nullable=False),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2token_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['session_id'], ['session.id'], name=op.f('fk_oauth2token_session_id_session'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2token')),
		sa.UniqueConstraint('access_token', name=op.f('uq_oauth2token_access_token')),
		sa.UniqueConstraint('refresh_token', name=op.f('uq_oauth2token_refresh_token'))
	)
	with op.batch_alter_table('oauth2grant', schema=None) as batch_op:
		batch_op.alter_column('claims', existing_type=sa.TEXT(), nullable=True)
