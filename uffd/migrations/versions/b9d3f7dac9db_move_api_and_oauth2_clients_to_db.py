"""Move API and OAuth2 clients to DB

Revision ID: b9d3f7dac9db
Revises: 09d2edcaf0cc
Create Date: 2022-02-17 21:14:00.440057

"""

import secrets
import hashlib
import base64

from alembic import op
import sqlalchemy as sa
from flask import current_app

revision = 'b9d3f7dac9db'
down_revision = '09d2edcaf0cc'
branch_labels = None
depends_on = None

def hash_sha512(password):
	ctx = hashlib.new('sha512', password.encode())
	return '{sha512}' + base64.b64encode(ctx.digest()).decode()

def upgrade():
	used_service_names = set()
	services = {} # name -> limit_access, access_group_name
	oauth2_clients = [] # service_name, client_id, client_secret, redirect_uris, logout_uris
	api_clients = [] # service_name, auth_username, auth_password, perm_users, perm_checkpassword, perm_mail_aliases
	for opts in current_app.config.get('OAUTH2_CLIENTS', {}).values():
		if 'service_name' in opts:
			used_service_names.add(opts['service_name'])
	for opts in current_app.config.get('API_CLIENTS_2', {}).values():
		if 'service_name' in opts:
			used_service_names.add(opts['service_name'])
	for client_id, opts in current_app.config.get('OAUTH2_CLIENTS', {}).items():
		if 'client_secret' not in opts:
			continue
		if 'service_name' in opts:
			service_name = opts['service_name']
		else:
			service_name = client_id
			if service_name in used_service_names:
				service_name = 'oauth2_' + service_name
			if service_name in used_service_names:
				num = 1
				while (service_name + '_%d'%num) in used_service_names:
					num += 1
				service_name = service_name + '_%d'%num
		if opts.get('required_group') is None:
			limit_access = False
			access_group_name = None
		elif isinstance(opts.get('required_group'), str):
			limit_access = True
			access_group_name = opts['required_group']
		else:
			limit_access = True
			access_group_name = None
		client_secret = opts['client_secret']
		redirect_uris = opts.get('redirect_uris') or []
		logout_uris = []
		for item in opts.get('logout_urls') or []:
			if isinstance(item, str):
				logout_uris.append(('GET', item))
			else:
				logout_uris.append(item)
		used_service_names.add(service_name)
		if service_name not in services or services[service_name] == (False, None):
			services[service_name] = (limit_access, access_group_name)
		elif services[service_name] == (limit_access, access_group_name):
			pass
		else:
			services[service_name] = (True, None)
		oauth2_clients.append((service_name, client_id, client_secret, redirect_uris, logout_uris))
	for client_id, opts in current_app.config.get('API_CLIENTS_2', {}).items():
		if 'client_secret' not in opts:
			continue
		if 'service_name' in opts:
			service_name = opts['service_name']
		else:
			service_name = 'api_' + client_id
			if service_name in used_service_names:
				num = 1
				while (service_name + '_%d'%num) in used_service_names:
					num += 1
				service_name = service_name + '_%d'%num
		auth_username = client_id
		auth_password = opts['client_secret']
		perm_users = 'getusers' in opts.get('scopes', [])
		perm_checkpassword = 'checkpassword' in opts.get('scopes', [])
		perm_mail_aliases = 'getmails' in opts.get('scopes', [])
		if service_name not in services:
			services[service_name] = (False, None)
		api_clients.append((service_name, auth_username, auth_password, perm_users, perm_checkpassword, perm_mail_aliases))

	meta = sa.MetaData()

	service_table = op.create_table('service',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('name', sa.String(length=255), nullable=False),
		sa.Column('limit_access', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('access_group_id', sa.Integer(), nullable=True),
		sa.ForeignKeyConstraint(['access_group_id'], ['group.id'], name=op.f('fk_service_access_group_id_group'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_service')),
		sa.UniqueConstraint('name', name=op.f('uq_service_name'))
	)
	group_table = sa.table('group',
		sa.column('id'),
		sa.column('name'),
	)
	for service_name, args in services.items():
		limit_access, access_group_name = args
		op.execute(service_table.insert().values(name=service_name, limit_access=limit_access, access_group_id=sa.select(group_table.c.id).where(group_table.c.name==access_group_name).as_scalar()))

	api_client_table = op.create_table('api_client',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('service_id', sa.Integer(), nullable=False),
		sa.Column('auth_username', sa.String(length=40), nullable=False),
		sa.Column('auth_password', sa.Text(), nullable=False),
		sa.Column('perm_users', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('perm_checkpassword', sa.Boolean(create_constraint=True), nullable=False),
		sa.Column('perm_mail_aliases', sa.Boolean(create_constraint=True), nullable=False),
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_api_client_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_api_client')),
		sa.UniqueConstraint('auth_username', name=op.f('uq_api_client_auth_username'))
	)
	for service_name, auth_username, auth_password, perm_users, perm_checkpassword, perm_mail_aliases in api_clients:
		op.execute(api_client_table.insert().values(service_id=sa.select(service_table.c.id).where(service_table.c.name==service_name).as_scalar(), auth_username=auth_username, auth_password=hash_sha512(auth_password), perm_users=perm_users, perm_checkpassword=perm_checkpassword, perm_mail_aliases=perm_mail_aliases))

	oauth2client_table = op.create_table('oauth2client',
		sa.Column('db_id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('service_id', sa.Integer(), nullable=False),
		sa.Column('client_id', sa.String(length=40), nullable=False),
		sa.Column('client_secret', sa.Text(), nullable=False),
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_oauth2client_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('db_id', name=op.f('pk_oauth2client')),
		sa.UniqueConstraint('client_id', name=op.f('uq_oauth2client_client_id'))
	)
	oauth2logout_uri_table = op.create_table('oauth2logout_uri',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('method', sa.String(length=40), nullable=False),
		sa.Column('uri', sa.String(length=255), nullable=False),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2logout_uri_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2logout_uri'))
	)
	oauth2redirect_uri_table = op.create_table('oauth2redirect_uri',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('uri', sa.String(length=255), nullable=False),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2redirect_uri_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2redirect_uri'))
	)
	for service_name, client_id, client_secret, redirect_uris, logout_uris in oauth2_clients:
		op.execute(oauth2client_table.insert().values(service_id=sa.select(service_table.c.id).where(service_table.c.name==service_name).as_scalar(), client_id=client_id, client_secret=hash_sha512(client_secret)))
		for method, uri, in logout_uris:
			op.execute(oauth2logout_uri_table.insert().values(client_db_id=sa.select(oauth2client_table.c.db_id).where(oauth2client_table.c.client_id==client_id).as_scalar(), method=method, uri=uri))
		for uri in redirect_uris:
			op.execute(oauth2redirect_uri_table.insert().values(client_db_id=sa.select(oauth2client_table.c.db_id).where(oauth2client_table.c.client_id==client_id).as_scalar(), uri=uri))

	with op.batch_alter_table('device_login_initiation', schema=None) as batch_op:
		batch_op.add_column(sa.Column('oauth2_client_db_id', sa.Integer(), nullable=True))
		batch_op.create_foreign_key(batch_op.f('fk_device_login_initiation_oauth2_client_db_id_oauth2client'), 'oauth2client', ['oauth2_client_db_id'], ['db_id'], onupdate='CASCADE', ondelete='CASCADE')
	device_login_initiation_table = sa.Table('device_login_initiation', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('type', sa.Enum('OAUTH2', create_constraint=True, name='devicelogintype'), nullable=False),
		sa.Column('code0', sa.String(length=32), nullable=False),
		sa.Column('code1', sa.String(length=32), nullable=False),
		sa.Column('secret', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('oauth2_client_id', sa.String(length=40), nullable=True),
		sa.Column('oauth2_client_db_id', sa.Integer(), nullable=True),
		sa.ForeignKeyConstraint(['oauth2_client_db_id'], ['oauth2client.db_id'], name=op.f('fk_device_login_initiation_oauth2_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_device_login_initiation')),
		sa.UniqueConstraint('code0', name=op.f('uq_device_login_initiation_code0')),
		sa.UniqueConstraint('code1', name=op.f('uq_device_login_initiation_code1'))
	)
	op.execute(device_login_initiation_table.update().values(oauth2_client_db_id=sa.select(oauth2client_table.c.db_id).where(device_login_initiation_table.c.oauth2_client_id==oauth2client_table.c.client_id).as_scalar()))
	op.execute(device_login_initiation_table.delete().where(device_login_initiation_table.c.oauth2_client_db_id==None))
	with op.batch_alter_table('device_login_initiation', copy_from=device_login_initiation_table) as batch_op:
		batch_op.drop_column('oauth2_client_id')

	with op.batch_alter_table('oauth2grant', schema=None) as batch_op:
		batch_op.add_column(sa.Column('client_db_id', sa.Integer(), nullable=True))
		batch_op.create_foreign_key(batch_op.f('fk_oauth2grant_client_db_id_oauth2client'), 'oauth2client', ['client_db_id'], ['db_id'], onupdate='CASCADE', ondelete='CASCADE')
	oauth2grant_table = sa.Table('oauth2grant', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('client_id', sa.String(length=40), nullable=False),
		sa.Column('client_db_id', sa.Integer(), nullable=True),
		sa.Column('code', sa.String(length=255), nullable=False),
		sa.Column('redirect_uri', sa.String(length=255), nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_oauth2grant_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2grant_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2grant')),
		sa.Index('ix_oauth2grant_code', 'code')
	)
	op.execute(oauth2grant_table.update().values(client_db_id=sa.select(oauth2client_table.c.db_id).where(oauth2grant_table.c.client_id==oauth2client_table.c.client_id).as_scalar()))
	op.execute(oauth2grant_table.delete().where(oauth2grant_table.c.client_db_id==None))
	with op.batch_alter_table('oauth2grant', copy_from=oauth2grant_table) as batch_op:
		batch_op.alter_column('client_db_id', existing_type=sa.Integer(), nullable=False)
		batch_op.drop_column('client_id')

	with op.batch_alter_table('oauth2token', schema=None) as batch_op:
		batch_op.add_column(sa.Column('client_db_id', sa.Integer(), nullable=True))
		batch_op.create_foreign_key(batch_op.f('fk_oauth2token_client_db_id_oauth2client'), 'oauth2client', ['client_db_id'], ['db_id'], onupdate='CASCADE', ondelete='CASCADE')
	oauth2token_table = sa.Table('oauth2token', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('client_id', sa.String(length=40), nullable=False),
		sa.Column('client_db_id', sa.Integer(), nullable=True),
		sa.Column('token_type', sa.String(length=40), nullable=False),
		sa.Column('access_token', sa.String(length=255), nullable=False),
		sa.Column('refresh_token', sa.String(length=255), nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_oauth2token_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2token_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2token')),
		sa.UniqueConstraint('access_token', name=op.f('uq_oauth2token_access_token')),
		sa.UniqueConstraint('refresh_token', name=op.f('uq_oauth2token_refresh_token'))
	)
	op.execute(oauth2token_table.update().values(client_db_id=sa.select(oauth2client_table.c.db_id).where(oauth2token_table.c.client_id==oauth2client_table.c.client_id).as_scalar()))
	op.execute(oauth2token_table.delete().where(oauth2token_table.c.client_db_id==None))
	with op.batch_alter_table('oauth2token', copy_from=oauth2token_table) as batch_op:
		batch_op.alter_column('client_db_id', existing_type=sa.Integer(), nullable=False)
		batch_op.drop_column('client_id')

def downgrade():
	meta = sa.MetaData()
	oauth2client_table = sa.Table('oauth2client', meta,
		sa.Column('db_id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('service_id', sa.Integer(), nullable=False),
		sa.Column('client_id', sa.String(length=40), nullable=False),
		sa.Column('client_secret', sa.Text(), nullable=False),
		sa.ForeignKeyConstraint(['service_id'], ['service.id'], name=op.f('fk_oauth2client_service_id_service'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('db_id', name=op.f('pk_oauth2client')),
		sa.UniqueConstraint('client_id', name=op.f('uq_oauth2client_client_id'))
	)

	with op.batch_alter_table('oauth2token', schema=None) as batch_op:
		batch_op.add_column(sa.Column('client_id', sa.VARCHAR(length=40), nullable=True))
	oauth2token_table = sa.Table('oauth2token', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('client_id', sa.String(length=40), nullable=True),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('token_type', sa.String(length=40), nullable=False),
		sa.Column('access_token', sa.String(length=255), nullable=False),
		sa.Column('refresh_token', sa.String(length=255), nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_oauth2token_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2token_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2token')),
		sa.UniqueConstraint('access_token', name=op.f('uq_oauth2token_access_token')),
		sa.UniqueConstraint('refresh_token', name=op.f('uq_oauth2token_refresh_token'))
	)
	op.execute(oauth2token_table.update().values(client_id=sa.select(oauth2client_table.c.client_id).where(oauth2token_table.c.client_db_id==oauth2client_table.c.db_id).as_scalar()))
	op.execute(oauth2token_table.delete().where(oauth2token_table.c.client_id==None))
	with op.batch_alter_table('oauth2token', copy_from=oauth2token_table) as batch_op:
		batch_op.alter_column('client_id', existing_type=sa.VARCHAR(length=40), nullable=False)
		batch_op.drop_constraint(batch_op.f('fk_oauth2token_client_db_id_oauth2client'), type_='foreignkey')
		batch_op.drop_column('client_db_id')

	with op.batch_alter_table('oauth2grant', schema=None) as batch_op:
		batch_op.add_column(sa.Column('client_id', sa.VARCHAR(length=40), nullable=True))
	oauth2grant_table = sa.Table('oauth2grant', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('client_id', sa.String(length=40), nullable=True),
		sa.Column('client_db_id', sa.Integer(), nullable=False),
		sa.Column('code', sa.String(length=255), nullable=False),
		sa.Column('redirect_uri', sa.String(length=255), nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_oauth2grant_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['client_db_id'], ['oauth2client.db_id'], name=op.f('fk_oauth2grant_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2grant')),
		sa.Index('ix_oauth2grant_code', 'code')
	)
	op.execute(oauth2grant_table.update().values(client_id=sa.select(oauth2client_table.c.client_id).where(oauth2grant_table.c.client_db_id==oauth2client_table.c.db_id).as_scalar()))
	op.execute(oauth2grant_table.delete().where(oauth2grant_table.c.client_id==None))
	with op.batch_alter_table('oauth2grant', copy_from=oauth2grant_table) as batch_op:
		batch_op.alter_column('client_id', existing_type=sa.VARCHAR(length=40), nullable=False)
		batch_op.drop_constraint(batch_op.f('fk_oauth2grant_client_db_id_oauth2client'), type_='foreignkey')
		batch_op.drop_column('client_db_id')

	with op.batch_alter_table('device_login_initiation', schema=None) as batch_op:
		batch_op.add_column(sa.Column('oauth2_client_id', sa.VARCHAR(length=40), nullable=True))
	device_login_initiation_table = sa.Table('device_login_initiation', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('type', sa.Enum('OAUTH2', create_constraint=True, name='devicelogintype'), nullable=False),
		sa.Column('code0', sa.String(length=32), nullable=False),
		sa.Column('code1', sa.String(length=32), nullable=False),
		sa.Column('secret', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('oauth2_client_id', sa.String(length=40), nullable=True),
		sa.Column('oauth2_client_db_id', sa.Integer(), nullable=True),
		sa.ForeignKeyConstraint(['oauth2_client_db_id'], ['oauth2client.db_id'], name=op.f('fk_device_login_initiation_oauth2_client_db_id_oauth2client'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_device_login_initiation')),
		sa.UniqueConstraint('code0', name=op.f('uq_device_login_initiation_code0')),
		sa.UniqueConstraint('code1', name=op.f('uq_device_login_initiation_code1'))
	)
	op.execute(device_login_initiation_table.update().values(oauth2_client_id=sa.select(oauth2client_table.c.client_id).where(device_login_initiation_table.c.oauth2_client_db_id==oauth2client_table.c.db_id).as_scalar()))
	op.execute(device_login_initiation_table.delete().where(device_login_initiation_table.c.oauth2_client_id==None))
	with op.batch_alter_table('device_login_initiation', copy_from=device_login_initiation_table) as batch_op:
		batch_op.drop_constraint(batch_op.f('fk_device_login_initiation_oauth2_client_db_id_oauth2client'), type_='foreignkey')
		batch_op.drop_column('oauth2_client_db_id')

	op.drop_table('oauth2redirect_uri')
	op.drop_table('oauth2logout_uri')
	op.drop_table('oauth2client')
	op.drop_table('api_client')
	op.drop_table('service')
