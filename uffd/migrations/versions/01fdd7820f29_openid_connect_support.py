"""OpenID Connect Support

Revision ID: 01fdd7820f29
Revises: a9b449776953
Create Date: 2023-11-09 16:52:20.860871

"""
from alembic import op
import sqlalchemy as sa

import datetime
import secrets
import math
import logging

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend # Only required for Buster
import jwt

# pyjwt v1.7.x compat (Buster/Bullseye)
if not hasattr(jwt, 'get_algorithm_by_name'):
	jwt.get_algorithm_by_name = lambda name: jwt.algorithms.get_default_algorithms()[name]

# revision identifiers, used by Alembic.
revision = '01fdd7820f29'
down_revision = 'a9b449776953'
branch_labels = None
depends_on = None

logger = logging.getLogger('alembic.runtime.migration.01fdd7820f29')

def token_with_alphabet(alphabet, nbytes=None):
	'''Return random text token that consists of characters from `alphabet`'''
	if nbytes is None:
		nbytes = max(secrets.DEFAULT_ENTROPY, 32)
	nbytes_per_char = math.log(len(alphabet), 256)
	nchars = math.ceil(nbytes / nbytes_per_char)
	return ''.join([secrets.choice(alphabet) for _ in range(nchars)])

def token_urlfriendly(nbytes=None):
	'''Return random text token that is urlsafe and works around common parsing bugs'''
	alphabet = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
	return token_with_alphabet(alphabet, nbytes=nbytes)

def upgrade():
	logger.info('Generating 3072 bit RSA key pair (RS256) for OpenID Connect support ...')
	private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072, backend=default_backend())

	meta = sa.MetaData()
	oauth2_key = op.create_table('oauth2_key',
		sa.Column('id', sa.String(length=64), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('active', sa.Boolean(create_constraint=False), nullable=False),
		sa.Column('algorithm', sa.String(length=32), nullable=False),
		sa.Column('private_key_jwk', sa.Text(), nullable=False),
		sa.Column('public_key_jwk', sa.Text(), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2_key'))
	)
	algorithm = jwt.get_algorithm_by_name('RS256')
	op.bulk_insert(oauth2_key, [{
		'id': token_urlfriendly(),
		'created': datetime.datetime.utcnow(),
		'active': True,
		'algorithm': 'RS256',
		'private_key_jwk': algorithm.to_jwk(private_key),
		'public_key_jwk': algorithm.to_jwk(private_key.public_key()),
	}])

	with op.batch_alter_table('oauth2grant', schema=None) as batch_op:
		batch_op.drop_index(batch_op.f('ix_oauth2grant_code'))
	oauth2grant = sa.Table('oauth2grant', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('code', sa.String(length=255), nullable=False),
		sa.Column('redirect_uri', sa.String(length=255), nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2grant_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_oauth2grant_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2grant'))
	)
	with op.batch_alter_table('oauth2grant', copy_from=oauth2grant) as batch_op:
		batch_op.add_column(sa.Column('nonce', sa.Text(), nullable=True))
		batch_op.add_column(sa.Column('claims', sa.Text(), nullable=True))
		batch_op.alter_column('redirect_uri', existing_type=sa.VARCHAR(length=255), nullable=True)

	oauth2token = sa.Table('oauth2token', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('token_type', sa.String(length=40), nullable=False),
		sa.Column('access_token', sa.String(length=255), nullable=False),
		sa.Column('refresh_token', sa.String(length=255), nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2token_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_oauth2token_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2token')),
		sa.UniqueConstraint('access_token', name=op.f('uq_oauth2token_access_token')),
		sa.UniqueConstraint('refresh_token', name=op.f('uq_oauth2token_refresh_token'))
	)
	with op.batch_alter_table('oauth2token', copy_from=oauth2token) as batch_op:
		batch_op.add_column(sa.Column('claims', sa.Text(), nullable=True))

def downgrade():
	meta = sa.MetaData()

	oauth2token = sa.Table('oauth2token', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('token_type', sa.String(length=40), nullable=False),
		sa.Column('access_token', sa.String(length=255), nullable=False),
		sa.Column('refresh_token', sa.String(length=255), nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.Column('claims', sa.Text(), nullable=True),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2token_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_oauth2token_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2token')),
		sa.UniqueConstraint('access_token', name=op.f('uq_oauth2token_access_token')),
		sa.UniqueConstraint('refresh_token', name=op.f('uq_oauth2token_refresh_token'))
	)
	with op.batch_alter_table('oauth2token', copy_from=oauth2token) as batch_op:
		batch_op.drop_column('claims')

	oauth2grant = sa.Table('oauth2grant', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('code', sa.String(length=255), nullable=False),
		sa.Column('redirect_uri', sa.String(length=255), nullable=True),
		sa.Column('nonce', sa.Text(), nullable=True),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.Column('claims', sa.Text(), nullable=True),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2grant_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_oauth2grant_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2grant'))
	)
	with op.batch_alter_table('oauth2grant', copy_from=oauth2grant) as batch_op:
		batch_op.alter_column('redirect_uri', existing_type=sa.VARCHAR(length=255), nullable=False)
		batch_op.drop_column('claims')
		batch_op.drop_column('nonce')
		batch_op.create_index(batch_op.f('ix_oauth2grant_code'), ['code'], unique=False)

	op.drop_table('oauth2_key')
