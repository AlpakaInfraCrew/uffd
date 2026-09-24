"""LDAP to DB

Revision ID: 878b25c4fae7
Revises: 11ecc8f1ac3b
Create Date: 2021-08-01 16:31:09.242380

"""
from warnings import warn

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '878b25c4fae7'
down_revision = '11ecc8f1ac3b'
branch_labels = None
depends_on = None

from flask import current_app

def encode_filter(filter_params):
	from ldap3.utils.conv import escape_filter_chars
	return '(&%s)'%(''.join(['(%s=%s)'%(attr, escape_filter_chars(value)) for attr, value in filter_params]))

def get_ldap_conn():
	if 'LDAP_SERVICE_URL' in current_app.config and not current_app.config.get('UPGRADE_V1_TO_V2'):
		raise Exception('Refusing to run v1 to v2 migrations: UPGRADE_V1_TO_V2 not set. Make sure to read upgrade instructions first!')
	critical = True
	if 'LDAP_SERVICE_URL' not in current_app.config:
		critical = False
	try:
		if current_app.config.get('LDAP_SERVICE_USER_BIND'):
			raise Exception('Import with LDAP_SERVICE_USER_BIND=True is not supported')
		if current_app.config.get('LDAP_SERVICE_MOCK'):
			# never reached if current_app.testing is True
			raise Exception('Import with LDAP_SERVICE_MOCK=True is not supported')
		import ldap3
		server = ldap3.Server(current_app.config.get('LDAP_SERVICE_URL', 'ldapi:///'), get_info=ldap3.ALL)
		# Using auto_bind cannot close the connection, so define the connection with extra steps
		conn = ldap3.Connection(server, current_app.config.get('LDAP_SERVICE_BIND_DN', ''),
		                        current_app.config.get('LDAP_SERVICE_BIND_PASSWORD', ''))
		if conn.closed:
			conn.open(read_server_info=False)
		if current_app.config.get('LDAP_SERVICE_USE_STARTTLS', True):
			conn.start_tls(read_server_info=False)
		if not conn.bind(read_server_info=True):
			conn.unbind()
			raise ldap3.core.exceptions.LDAPBindError
		return conn
	except Exception as e:
		if critical:
			raise e
		else:
			warn(f'LDAP not properly configured, disabling import: {e}')
	return None

def get_ldap_users():
	if current_app.config.get('LDAP_SERVICE_MOCK') and current_app.testing:
		return [
			{'dn': 'uid=testuser,ou=users,dc=example,dc=com', 'unix_uid': 10000, 'loginname': 'testuser',
			 'displayname': 'Test User', 'mail': 'testuser@example.com',
		   'pwhash': '{ssha512}llnQc2ruKczLUHJUPA3/MGA1rkChXcmYdIeMRfKC8NfsqnHTtd2UmSZ7RL4uTExzAcMyYKxLwyjmjZfycjLHBjR6NJeK1sz3',
			 'is_service_user': False},
			{'dn': 'uid=testadmin,ou=users,dc=example,dc=com', 'unix_uid': 10001, 'loginname': 'testadmin',
			 'displayname': 'Test Admin', 'mail': 'testadmin@example.com',
			 'pwhash': '{ssha512}8pI4sHQWEgDf9u4qj35QT3J1lskLrnWdvhlzSmYg1g2R1r/038f6we+8Hy5ld/KArApB9Gd9+4uitKbZVbR1CkuPT2iAWoMc',
			 'is_service_user': False},
		]
	conn = get_ldap_conn()
	if not conn:
		return []
	conn.search(current_app.config.get('LDAP_USER_SEARCH_BASE', 'ou=users,dc=example,dc=com'),
	            encode_filter(current_app.config.get('LDAP_USER_SEARCH_FILTER', [('objectClass', 'person')])),
	            attributes='*')
	users = []
	for response in conn.response:
		uid = response['attributes'][current_app.config.get('LDAP_USER_UID_ATTRIBUTE', 'uidNumber')]
		pwhash = response['attributes'].get('userPassword', [None])[0]
		if pwhash is None:
			raise Exception('Cannot read userPassword attribute')
		elif isinstance(pwhash, bytes):
			pwhash = pwhash.decode()
		users.append({
			'dn': response['dn'],
			'unix_uid': uid,
			'loginname': response['attributes'][current_app.config.get('LDAP_USER_LOGINNAME_ATTRIBUTE', 'uid')][0],
			'displayname': response['attributes'].get(current_app.config.get('LDAP_USER_DISPLAYNAME_ATTRIBUTE', 'cn'), [''])[0],
			'mail': response['attributes'][current_app.config.get('LDAP_USER_MAIL_ATTRIBUTE', 'mail')][0],
			'pwhash': pwhash,
			'is_service_user':  uid >= current_app.config.get('LDAP_USER_SERVICE_MIN_UID', 19000) and \
			                    uid <= current_app.config.get('LDAP_USER_SERVICE_MAX_UID', 19999),
		})
	return users

def get_ldap_groups():
	if current_app.config.get('LDAP_SERVICE_MOCK') and current_app.testing:
		return [
			{'dn': 'cn=users,ou=groups,dc=example,dc=com', 'unix_gid': 20001, 'name': 'users',
			 'description': 'Base group for all users', 'member_dns': ['cn=dummy,ou=system,dc=example,dc=com',
			                                                           'uid=testuser,ou=users,dc=example,dc=com',
			                                                           'uid=testadmin,ou=users,dc=example,dc=com']},
			{'dn': 'cn=uffd_access,ou=groups,dc=example,dc=com', 'unix_gid': 20002, 'name': 'uffd_access',
			 'description': 'User access to uffd selfservice', 'member_dns': ['cn=dummy,ou=system,dc=example,dc=com',
			                                                                  'uid=testuser,ou=users,dc=example,dc=com',
			                                                                  'uid=testadmin,ou=users,dc=example,dc=com']},
			{'dn': 'cn=uffd_admin,ou=groups,dc=example,dc=com', 'unix_gid': 20003, 'name': 'uffd_admin',
			 'description': 'User access to uffd selfservice', 'member_dns': ['cn=dummy,ou=system,dc=example,dc=com',
			                                                                  'uid=testadmin,ou=users,dc=example,dc=com']},
		]
	conn = get_ldap_conn()
	if not conn:
		return []
	conn.search(current_app.config.get('LDAP_GROUP_SEARCH_BASE', 'ou=groups,dc=example,dc=com'),
	            encode_filter(current_app.config.get('LDAP_GROUP_SEARCH_FILTER', [('objectClass','groupOfUniqueNames')])),
	            attributes='*')
	groups = []
	for response in conn.response:
		groups.append({
			'dn': response['dn'],
			'unix_gid': response['attributes'][current_app.config.get('LDAP_GROUP_GID_ATTRIBUTE', 'gidNumber')],
			'name': response['attributes'][current_app.config.get('LDAP_GROUP_NAME_ATTRIBUTE', 'cn')][0],
			'description': response['attributes'].get(current_app.config.get('LDAP_GROUP_DESCRIPTION_ATTRIBUTE', 'description'), [''])[0],
			'member_dns': response['attributes'].get(current_app.config.get('LDAP_GROUP_MEMBER_ATTRIBUTE', 'uniqueMember'), []),
		})
	return groups

def get_ldap_mails():
	if current_app.config.get('LDAP_SERVICE_MOCK') and current_app.testing:
		return [
			{'dn': 'uid=test,ou=postfix,dc=example,dc=com', 'uid': 'test',
			 'receivers': ['test1@example.com', 'test2@example.com'],
			 'destinations': ['testuser@mail.example.com']},
		]
	conn = get_ldap_conn()
	if not conn:
		return []
	conn.search(current_app.config.get('LDAP_MAIL_SEARCH_BASE', 'ou=postfix,dc=example,dc=com'),
	            encode_filter(current_app.config.get('LDAP_MAIL_SEARCH_FILTER', [('objectClass','postfixVirtual')])),
	            attributes='*')
	mails = []
	for response in conn.response:
		mails.append({
			'dn': response['dn'],
			'uid': response['attributes'][current_app.config.get('LDAP_MAIL_UID_ATTRIBUTE', 'uid')][0],
			'receivers': response['attributes'].get(current_app.config.get('LDAP_MAIL_RECEIVERS_ATTRIBUTE', 'mailacceptinggeneralid'), []),
			'destinations': response['attributes'].get(current_app.config.get('LDAP_MAIL_DESTINATIONS_ATTRIBUTE', 'maildrop'), []),
		})
	return mails

def upgrade():
	# Load LDAP data first, so we fail as early as possible
	ldap_mails = get_ldap_mails()
	ldap_users = get_ldap_users()
	ldap_groups = get_ldap_groups()
	meta = sa.MetaData()

	mail_table = op.create_table('mail',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('uid', sa.String(length=32), nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=False), # tmp
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mail')),
		sa.UniqueConstraint('uid', name=op.f('uq_mail_uid'))
	)
	mail_receive_address_table = op.create_table('mail_receive_address',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('mail_id', sa.Integer(), nullable=True),
		sa.Column('mail_dn', sa.String(length=128), nullable=False), # tmp
		sa.Column('address', sa.String(length=128), nullable=False),
		sa.ForeignKeyConstraint(['mail_id'], ['mail.id'], name=op.f('fk_mail_receive_address_mail_id_mail'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mail_receive_address'))
	)
	mail_destination_address_table = op.create_table('mail_destination_address',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('mail_id', sa.Integer(), nullable=True),
		sa.Column('mail_dn', sa.String(length=128), nullable=False), # tmp
		sa.Column('address', sa.String(length=128), nullable=False),
		sa.ForeignKeyConstraint(['mail_id'], ['mail.id'], name=op.f('fk_mail_destination_address_mail_id_mail'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mail_destination_address'))
	)
	op.bulk_insert(mail_table, [{'uid': mail['uid'], 'dn': mail['dn']} for mail in ldap_mails])
	rows = []
	for mail in ldap_mails:
		rows += [{'mail_dn': mail['dn'], 'address': address} for address in mail['receivers']]
	op.bulk_insert(mail_receive_address_table, rows)
	op.execute(mail_receive_address_table.update().values(mail_id=sa.select(mail_table.c.id).where(mail_receive_address_table.c.mail_dn==mail_table.c.dn).limit(1).as_scalar()))
	rows = []
	for mail in ldap_mails:
		rows += [{'mail_dn': mail['dn'], 'address': address} for address in mail['destinations']]
	op.bulk_insert(mail_destination_address_table, rows)
	op.execute(mail_destination_address_table.update().values(mail_id=sa.select(mail_table.c.id).where(mail_destination_address_table.c.mail_dn==mail_table.c.dn).limit(1).as_scalar()))
	with op.batch_alter_table('mail', schema=None) as batch_op:
		batch_op.drop_column('dn')
	with op.batch_alter_table('mail_destination_address', copy_from=mail_destination_address_table) as batch_op:
		batch_op.alter_column('mail_id', existing_type=sa.Integer(), nullable=False)
		batch_op.drop_column('mail_dn')
	with op.batch_alter_table('mail_receive_address', copy_from=mail_receive_address_table) as batch_op:
		batch_op.alter_column('mail_id', existing_type=sa.Integer(), nullable=False)
		batch_op.drop_column('mail_dn')

	user_table = op.create_table('user',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=False), # tmp
		sa.Column('unix_uid', sa.Integer(), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=False),
		sa.Column('displayname', sa.String(length=128), nullable=False),
		sa.Column('mail', sa.String(length=128), nullable=False),
		sa.Column('pwhash', sa.String(length=256), nullable=True),
		sa.Column('is_service_user', sa.Boolean(create_constraint=True, name=op.f('ck_user_is_service_user')), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
		sa.UniqueConstraint('loginname', name=op.f('uq_user_loginname')),
		sa.UniqueConstraint('unix_uid', name=op.f('uq_user_unix_uid'))
	)
	op.bulk_insert(user_table, ldap_users)

	group_table = op.create_table('group',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=False), # tmp
		sa.Column('unix_gid', sa.Integer(), nullable=False),
		sa.Column('name', sa.String(length=32), nullable=False),
		sa.Column('description', sa.String(length=128), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_group')),
		sa.UniqueConstraint('name', name=op.f('uq_group_name')),
		sa.UniqueConstraint('unix_gid', name=op.f('uq_group_unix_gid'))
	)
	op.bulk_insert(group_table, [{'dn': group['dn'], 'unix_gid': group['unix_gid'], 'name': group['name'], 'description': group['description']} for group in ldap_groups])
	user_groups_table = op.create_table('user_groups',
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False), # tmp
		sa.Column('user_dn', sa.String(length=128), nullable=False), # tmp
		sa.Column('user_id', sa.Integer(), nullable=True), # tmp nullable
		sa.Column('group_dn', sa.String(length=128), nullable=False), # tmp
		sa.Column('group_id', sa.Integer(), nullable=True), # tmp nullable
		sa.ForeignKeyConstraint(['group_id'], ['group.id'], name=op.f('fk_user_groups_group_id_group'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_user_groups_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user_groups')),
	)
	rows = []
	for group in ldap_groups:
		rows += [{'group_dn': group['dn'], 'user_dn': member_dn} for member_dn in group['member_dns']]
	op.bulk_insert(user_groups_table, rows)
	op.execute(user_groups_table.update().values(user_id=sa.select(user_table.c.id).where(user_groups_table.c.user_dn==user_table.c.dn).as_scalar()))
	op.execute(user_groups_table.update().values(group_id=sa.select(group_table.c.id).where(user_groups_table.c.group_dn==group_table.c.dn).as_scalar()))
	# Delete member objects that are not users (like the "dummy" object)
	op.execute(user_groups_table.delete().where(sa.or_(user_groups_table.c.user_id==None, user_groups_table.c.group_id==None)))
	with op.batch_alter_table('user_groups', copy_from=user_groups_table) as batch_op:
		batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=False)
		batch_op.alter_column('group_id', existing_type=sa.Integer(), nullable=False)
		batch_op.drop_column('group_dn')
		batch_op.alter_column('id', existing_type=sa.Integer(), nullable=True, autoincrement=False)
		batch_op.drop_constraint('pk_user_groups', 'primary')
		batch_op.create_primary_key('pk_user_groups', ['user_id', 'group_id'])
		batch_op.drop_column('id')
		batch_op.drop_column('user_dn')

	with op.batch_alter_table('role-group', schema=None) as batch_op:
		batch_op.add_column(sa.Column('group_id', sa.Integer(), nullable=True))
	role_groups_table = sa.Table('role-group', meta,
		sa.Column('role_id', sa.Integer(), nullable=False),
		sa.Column('group_dn', sa.String(length=128), nullable=False),
		sa.Column('group_id', sa.Integer(), nullable=True),
		sa.Column('requires_mfa', sa.Boolean(create_constraint=False), nullable=False),
		sa.CheckConstraint('requires_mfa in (0,1)', name=op.f('ck_role-group_requires_mfa')),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role-group_role_id_role')),
		sa.PrimaryKeyConstraint('role_id', 'group_dn', name=op.f('pk_role-group'))
	)
	op.execute(role_groups_table.update().values(group_id=sa.select(group_table.c.id).where(role_groups_table.c.group_dn==group_table.c.dn).as_scalar()))
	op.execute(role_groups_table.delete().where(role_groups_table.c.group_id==None))
	with op.batch_alter_table('role-group', copy_from=role_groups_table) as batch_op:
		batch_op.drop_constraint('ck_role-group_requires_mfa', 'check')
		batch_op.create_check_constraint('ck_role_groups_requires_mfa', role_groups_table.c.requires_mfa.in_([0,1]))
		batch_op.drop_constraint('fk_role-group_role_id_role', 'foreignkey')
		batch_op.drop_constraint('pk_role-group', 'primary')
		batch_op.create_primary_key('pk_role_groups', ['role_id', 'group_id'])
		batch_op.create_foreign_key(batch_op.f('fk_role_groups_role_id_role'), 'role', ['role_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.create_foreign_key(batch_op.f('fk_role_groups_group_id_group'), 'group', ['group_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.drop_column('group_dn')
	op.rename_table('role-group', 'role_groups')

	with op.batch_alter_table('role-user', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
	role_members_table = sa.Table('role-user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=False),
		sa.Column('role_id', sa.Integer(), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role-user_role_id_role')),
		sa.UniqueConstraint('dn', 'role_id', name='uq_role-user_dn'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_role-user'))
	)
	op.execute(role_members_table.update().values(user_id=sa.select(user_table.c.id).where(role_members_table.c.dn==user_table.c.dn).as_scalar()))
	op.execute(role_members_table.delete().where(role_members_table.c.user_id==None))
	with op.batch_alter_table('role-user', copy_from=role_members_table) as batch_op:
		batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=False)
		batch_op.alter_column('role_id', existing_type=sa.Integer(), nullable=False)
		batch_op.drop_constraint('fk_role-user_role_id_role', 'foreignkey')
		batch_op.drop_constraint('uq_role-user_dn', 'unique')
		batch_op.create_foreign_key(batch_op.f('fk_role_members_role_id_role'), 'role', ['role_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.create_foreign_key(batch_op.f('fk_role_members_user_id_user'), 'user', ['user_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.drop_column('dn')
		batch_op.alter_column('id', existing_type=sa.Integer(), nullable=True, autoincrement=False)
		batch_op.drop_constraint('pk_role-user', 'primary')
		batch_op.create_primary_key('pk_role_members', ['role_id', 'user_id'])
		batch_op.drop_column('id')
	op.rename_table('role-user', 'role_members')

	with op.batch_alter_table('device_login_confirmation', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
		batch_op.create_unique_constraint(batch_op.f('uq_device_login_confirmation_user_id'), ['user_id'])
	device_login_confirmation = sa.Table('device_login_confirmation', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('initiation_id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('user_dn', sa.String(length=128), nullable=False),
		sa.Column('code0', sa.String(length=32), nullable=False),
		sa.Column('code1', sa.String(length=32), nullable=False),
		sa.ForeignKeyConstraint(['initiation_id'], ['device_login_initiation.id'], name=op.f('fk_device_login_confirmation_initiation_id_')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_device_login_confirmation')),
		sa.UniqueConstraint('initiation_id', 'code0', name='uq_device_login_confirmation_initiation_id_code0'),
		sa.UniqueConstraint('initiation_id', 'code1', name='uq_device_login_confirmation_initiation_id_code1'),
		sa.UniqueConstraint('user_id', name=op.f('uq_device_login_confirmation_user_id'))
	)
	op.execute(device_login_confirmation.update().values(user_id=sa.select(user_table.c.id).where(device_login_confirmation.c.user_dn==user_table.c.dn).as_scalar()))
	op.execute(device_login_confirmation.delete().where(device_login_confirmation.c.user_id==None))
	with op.batch_alter_table('device_login_confirmation', copy_from=device_login_confirmation) as batch_op:
		batch_op.create_foreign_key(batch_op.f('fk_device_login_confirmation_user_id_user'), 'user', ['user_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.drop_constraint('fk_device_login_confirmation_initiation_id_', type_='foreignkey')
		batch_op.create_foreign_key('fk_device_login_confirmation_initiation_id_', 'device_login_initiation', ['initiation_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.alter_column('user_id', nullable=False, existing_type=sa.Integer())
		batch_op.drop_column('user_dn')

	with op.batch_alter_table('invite', schema=None) as batch_op:
		batch_op.add_column(sa.Column('creator_id', sa.Integer(), nullable=True))
		batch_op.create_foreign_key(batch_op.f('fk_invite_creator_id_user'), 'user', ['creator_id'], ['id'], onupdate='CASCADE')
	invite = sa.Table('invite', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('creator_id', sa.Integer(), nullable=True),
		sa.Column('creator_dn', sa.String(length=128), nullable=True),
		sa.Column('valid_until', sa.DateTime(), nullable=False),
		sa.Column('single_use', sa.Boolean(create_constraint=True, name=op.f('ck_invite_single_use')), nullable=False),
		sa.Column('allow_signup', sa.Boolean(create_constraint=True, name=op.f('ck_invite_allow_signup')), nullable=False),
		sa.Column('used', sa.Boolean(create_constraint=True, name=op.f('ck_invite_used')), nullable=False),
		sa.Column('disabled', sa.Boolean(create_constraint=True, name=op.f('ck_invite_disabled')), nullable=False),
		sa.ForeignKeyConstraint(['creator_id'], ['user.id'], name=op.f('fk_invite_creator_id_user'), onupdate='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_invite')),
		sa.UniqueConstraint('token', name=op.f('uq_invite_token'))
	)
	op.execute(invite.update().values(creator_id=sa.select(user_table.c.id).where(invite.c.creator_dn==user_table.c.dn).as_scalar()))
	with op.batch_alter_table('invite', copy_from=invite) as batch_op:
		batch_op.drop_column('creator_dn')

	with op.batch_alter_table('invite_grant', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
	invite_grant = sa.Table('invite_grant', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('invite_id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('user_dn', sa.String(length=128), nullable=False),
		sa.ForeignKeyConstraint(['invite_id'], ['invite.id'], name=op.f('fk_invite_grant_invite_id_invite')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_invite_grant'))
	)
	op.execute(invite_grant.update().values(user_id=sa.select(user_table.c.id).where(invite_grant.c.user_dn==user_table.c.dn).as_scalar()))
	op.execute(invite_grant.delete().where(invite_grant.c.user_id==None))
	with op.batch_alter_table('invite_grant', copy_from=invite_grant) as batch_op:
		batch_op.create_foreign_key(batch_op.f('fk_invite_grant_user_id_user'), 'user', ['user_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.drop_constraint('fk_invite_grant_invite_id_invite', type_='foreignkey')
		batch_op.create_foreign_key(batch_op.f('fk_invite_grant_invite_id_invite'), 'invite', ['invite_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.alter_column('user_id', nullable=False, existing_type=sa.Integer())
		batch_op.drop_column('user_dn')

	with op.batch_alter_table('mfa_method', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
		batch_op.create_foreign_key(batch_op.f('fk_mfa_method_user_id_user'), 'user', ['user_id'], ['id'])
	mfa_method = sa.Table('mfa_method', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('type', sa.Enum('RECOVERY_CODE', 'TOTP', 'WEBAUTHN', create_constraint=True, name='ck_mfa_method_type'), nullable=True),
		sa.Column('created', sa.DateTime(), nullable=True),
		sa.Column('name', sa.String(length=128), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('dn', sa.String(length=128), nullable=False),
		sa.Column('recovery_salt', sa.String(length=64), nullable=True),
		sa.Column('recovery_hash', sa.String(length=256), nullable=True),
		sa.Column('totp_key', sa.String(length=64), nullable=True),
		sa.Column('webauthn_cred', sa.Text(), nullable=True),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_mfa_method_user_id_user')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mfa_method'))
	)
	op.execute(mfa_method.update().values(user_id=sa.select(user_table.c.id).where(mfa_method.c.dn==user_table.c.dn).as_scalar()))
	op.execute(mfa_method.delete().where(mfa_method.c.user_id==None))
	with op.batch_alter_table('mfa_method', copy_from=mfa_method) as batch_op:
		batch_op.alter_column('user_id', nullable=False, existing_type=sa.Integer())
		batch_op.alter_column('created', existing_type=sa.DateTime(), nullable=False)
		batch_op.alter_column('type', existing_type=sa.Enum('RECOVERY_CODE', 'TOTP', 'WEBAUTHN', create_constraint=True, name='ck_mfa_method_type'), nullable=False)
		batch_op.drop_constraint('fk_mfa_method_user_id_user', type_='foreignkey')
		batch_op.create_foreign_key(batch_op.f('fk_mfa_method_user_id_user'), 'user', ['user_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.drop_column('dn')

	with op.batch_alter_table('oauth2grant', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
	oauth2grant = sa.Table('oauth2grant', meta,
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('user_dn', sa.String(length=128), nullable=False),
		sa.Column('client_id', sa.String(length=40), nullable=True),
		sa.Column('code', sa.String(length=255), nullable=False),
		sa.Column('redirect_uri', sa.String(length=255), nullable=True),
		sa.Column('expires', sa.DateTime(), nullable=True),
		sa.Column('_scopes', sa.Text(), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2grant')),
		sa.Index('ix_oauth2grant_code', 'code')
	)
	op.execute(oauth2grant.update().values(user_id=sa.select(user_table.c.id).where(oauth2grant.c.user_dn==user_table.c.dn).as_scalar()))
	op.execute(oauth2grant.delete().where(oauth2grant.c.user_id==None))
	with op.batch_alter_table('oauth2grant', copy_from=oauth2grant) as batch_op:
		batch_op.create_foreign_key(batch_op.f('fk_oauth2grant_user_id_user'), 'user', ['user_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.alter_column('user_id', nullable=False, existing_type=sa.Integer())
		batch_op.alter_column('_scopes', nullable=False, existing_type=sa.Text())
		batch_op.alter_column('client_id', nullable=False, existing_type=sa.String(length=40))
		batch_op.alter_column('expires', nullable=False, existing_type=sa.DateTime())
		batch_op.alter_column('redirect_uri', nullable=False, existing_type=sa.String(length=255))
		batch_op.drop_column('user_dn')

	with op.batch_alter_table('oauth2token', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
	oauth2token = sa.Table('oauth2token', meta,
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('user_dn', sa.String(length=128), nullable=False),
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
	op.execute(oauth2token.update().values(user_id=sa.select(user_table.c.id).where(oauth2token.c.user_dn==user_table.c.dn).as_scalar()))
	op.execute(oauth2token.delete().where(oauth2token.c.user_id==None))
	with op.batch_alter_table('oauth2token', copy_from=oauth2token) as batch_op:
		batch_op.create_foreign_key(batch_op.f('fk_oauth2token_user_id_user'), 'user', ['user_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.alter_column('user_id', nullable=False, existing_type=sa.Integer())
		batch_op.alter_column('_scopes', nullable=False, existing_type=sa.Text())
		batch_op.alter_column('access_token', nullable=False, existing_type=sa.String(length=255))
		batch_op.alter_column('client_id', nullable=False, existing_type=sa.String(length=40))
		batch_op.alter_column('expires', nullable=False, existing_type=sa.DateTime())
		batch_op.alter_column('refresh_token', nullable=False, existing_type=sa.String(length=255))
		batch_op.alter_column('token_type', nullable=False, existing_type=sa.String(length=40))
		batch_op.drop_column('user_dn')

	with op.batch_alter_table('role', schema=None) as batch_op:
		batch_op.add_column(sa.Column('moderator_group_id', sa.Integer(), nullable=True))
	role = sa.Table('role', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('name', sa.String(length=32), nullable=True),
		sa.Column('description', sa.Text(), nullable=True),
		sa.Column('moderator_group_id', sa.Integer(), nullable=True),
		sa.Column('moderator_group_dn', sa.String(length=128), nullable=True),
		sa.Column('locked', sa.Boolean(create_constraint=True, name=op.f('ck_role_locked')), nullable=False),
		sa.Column('is_default', sa.Boolean(create_constraint=True, name=op.f('ck_role_is_default')), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_role')),
		sa.UniqueConstraint('name', name=op.f('uq_role_name'))
	)
	op.execute(role.update().values(moderator_group_id=sa.select(group_table.c.id).where(role.c.moderator_group_dn==group_table.c.dn).as_scalar()))
	with op.batch_alter_table('role', copy_from=role) as batch_op:
		batch_op.create_foreign_key(batch_op.f('fk_role_moderator_group_id_group'), 'group', ['moderator_group_id'], ['id'], onupdate='CASCADE', ondelete='SET NULL')
		batch_op.alter_column('description', existing_type=sa.Text(), nullable=False)
		batch_op.alter_column('name', existing_type=sa.String(length=32), nullable=False)
		batch_op.drop_column('moderator_group_dn')

	with op.batch_alter_table('signup', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
		batch_op.create_unique_constraint(batch_op.f('uq_signup_user_id'), ['user_id'])
	signup = sa.Table('signup', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('loginname', sa.Text(), nullable=True),
		sa.Column('displayname', sa.Text(), nullable=True),
		sa.Column('mail', sa.Text(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('user_dn', sa.String(length=128), nullable=True),
		sa.Column('type', sa.String(length=50), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_signup')),
		sa.UniqueConstraint('user_id', name=op.f('uq_signup_user_id'))
	)
	op.execute(signup.update().values(user_id=sa.select(user_table.c.id).where(signup.c.user_dn==user_table.c.dn).as_scalar()))
	with op.batch_alter_table('signup', copy_from=signup) as batch_op:
		batch_op.create_foreign_key(batch_op.f('fk_signup_user_id_user'), 'user', ['user_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.drop_column('user_dn')

	with op.batch_alter_table('mailToken', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
	mail_token = sa.Table('mailToken', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=True),
		sa.Column('loginname', sa.String(length=32), nullable=True),
		sa.Column('newmail', sa.String(length=255), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mailToken'))
	)
	op.execute(mail_token.update().values(user_id=sa.select(user_table.c.id).where(mail_token.c.loginname==user_table.c.loginname).as_scalar()))
	op.execute(mail_token.delete().where(mail_token.c.user_id==None))
	with op.batch_alter_table('mailToken', copy_from=mail_token) as batch_op:
		batch_op.alter_column('user_id', nullable=False, existing_type=sa.Integer())
		batch_op.create_foreign_key(batch_op.f('fk_mailToken_user_id_user'), 'user', ['user_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.drop_column('loginname')

	with op.batch_alter_table('passwordToken', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
	password_token = sa.Table('passwordToken', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_passwordToken'))
	)
	op.execute(password_token.update().values(user_id=sa.select(user_table.c.id).where(password_token.c.loginname==user_table.c.loginname).as_scalar()))
	op.execute(password_token.delete().where(password_token.c.user_id==None))
	with op.batch_alter_table('passwordToken', copy_from=password_token) as batch_op:
		batch_op.alter_column('user_id', nullable=False, existing_type=sa.Integer())
		batch_op.alter_column('created', existing_type=sa.DateTime(), nullable=False)
		batch_op.create_foreign_key(batch_op.f('fk_passwordToken_user_id_user'), 'user', ['user_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.drop_column('loginname')

	with op.batch_alter_table('group', copy_from=group_table) as batch_op:
		batch_op.drop_column('dn')
	with op.batch_alter_table('user', copy_from=user_table) as batch_op:
		batch_op.drop_column('dn')

	# These changes have nothing todo with the LDAP-to-DB migration, but since we add onupdate/ondelete clauses everywhere else ...
	invite_roles = sa.Table('invite_roles', meta,
		sa.Column('invite_id', sa.Integer(), nullable=False),
		sa.Column('role_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['invite_id'], ['invite.id'], name=op.f('fk_invite_roles_invite_id_invite')),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_invite_roles_role_id_role')),
		sa.PrimaryKeyConstraint('invite_id', 'role_id', name=op.f('pk_invite_roles'))
	)
	with op.batch_alter_table('invite_roles', copy_from=invite_roles) as batch_op:
		batch_op.drop_constraint('fk_invite_roles_role_id_role', type_='foreignkey')
		batch_op.drop_constraint('fk_invite_roles_invite_id_invite', type_='foreignkey')
		batch_op.create_foreign_key(batch_op.f('fk_invite_roles_role_id_role'), 'role', ['role_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.create_foreign_key(batch_op.f('fk_invite_roles_invite_id_invite'), 'invite', ['invite_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
	invite_signup = sa.Table('invite_signup', meta,
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('invite_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['id'], ['signup.id'], name=op.f('fk_invite_signup_id_signup'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['invite_id'], ['invite.id'], name=op.f('fk_invite_signup_invite_id_invite'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_invite_signup'))
	)
	with op.batch_alter_table('invite_signup', copy_from=invite_signup) as batch_op:
		batch_op.drop_constraint('fk_invite_signup_id_signup', type_='foreignkey')
		batch_op.drop_constraint('fk_invite_signup_invite_id_invite', type_='foreignkey')
		batch_op.create_foreign_key(batch_op.f('fk_invite_signup_id_signup'), 'signup', ['id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.create_foreign_key(batch_op.f('fk_invite_signup_invite_id_invite'), 'invite', ['invite_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
	role_inclusion = sa.Table('role-inclusion', meta,
		sa.Column('role_id', sa.Integer(), nullable=False),
		sa.Column('included_role_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['included_role_id'], ['role.id'], name=op.f('fk_role-inclusion_included_role_id_role'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role-inclusion_role_id_role'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('role_id', 'included_role_id', name=op.f('pk_role-inclusion'))
	)
	with op.batch_alter_table('role-inclusion', copy_from=role_inclusion) as batch_op:
		batch_op.drop_constraint('fk_role-inclusion_role_id_role', type_='foreignkey')
		batch_op.drop_constraint('fk_role-inclusion_included_role_id_role', type_='foreignkey')
		batch_op.create_foreign_key(batch_op.f('fk_role-inclusion_role_id_role'), 'role', ['role_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
		batch_op.create_foreign_key(batch_op.f('fk_role-inclusion_included_role_id_role'), 'role', ['included_role_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')

def downgrade():
	# The downgrade is incomplete as it does not sync changes back to LDAP. The
	# code is only here to keep check_migrations.py working.
	if not current_app.testing:
		raise Exception('Downgrade is not supported')

	# Load LDAP data first, so we fail as early as possible
	ldap_users = get_ldap_users()
	ldap_groups = get_ldap_groups()

	meta = sa.MetaData()

	# These changes have nothing todo with the LDAP to DB migration
	role_inclusion = sa.Table('role-inclusion', meta,
		sa.Column('role_id', sa.Integer(), nullable=False),
		sa.Column('included_role_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['included_role_id'], ['role.id'], name=op.f('fk_role-inclusion_included_role_id_role'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role-inclusion_role_id_role'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('role_id', 'included_role_id', name=op.f('pk_role-inclusion'))
	)
	with op.batch_alter_table('role-inclusion', copy_from=role_inclusion) as batch_op:
		batch_op.drop_constraint(batch_op.f('fk_role-inclusion_included_role_id_role'), type_='foreignkey')
		batch_op.drop_constraint(batch_op.f('fk_role-inclusion_role_id_role'), type_='foreignkey')
		batch_op.create_foreign_key('fk_role-inclusion_included_role_id_role', 'role', ['included_role_id'], ['id'])
		batch_op.create_foreign_key('fk_role-inclusion_role_id_role', 'role', ['role_id'], ['id'])
	invite_signup = sa.Table('invite_signup', meta,
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('invite_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['id'], ['signup.id'], name=op.f('fk_invite_signup_id_signup'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['invite_id'], ['invite.id'], name=op.f('fk_invite_signup_invite_id_invite'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_invite_signup'))
	)
	with op.batch_alter_table('invite_signup', copy_from=invite_signup) as batch_op:
		batch_op.drop_constraint(batch_op.f('fk_invite_signup_invite_id_invite'), type_='foreignkey')
		batch_op.drop_constraint(batch_op.f('fk_invite_signup_id_signup'), type_='foreignkey')
		batch_op.create_foreign_key('fk_invite_signup_invite_id_invite', 'invite', ['invite_id'], ['id'])
		batch_op.create_foreign_key('fk_invite_signup_id_signup', 'signup', ['id'], ['id'])
	invite_roles = sa.Table('invite_roles', meta,
		sa.Column('invite_id', sa.Integer(), nullable=False),
		sa.Column('role_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['invite_id'], ['invite.id'], name=op.f('fk_invite_roles_invite_id_invite'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_invite_roles_role_id_role'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('invite_id', 'role_id', name=op.f('pk_invite_roles'))
	)
	with op.batch_alter_table('invite_roles', copy_from=invite_roles) as batch_op:
		batch_op.drop_constraint(batch_op.f('fk_invite_roles_invite_id_invite'), type_='foreignkey')
		batch_op.drop_constraint(batch_op.f('fk_invite_roles_role_id_role'), type_='foreignkey')
		batch_op.create_foreign_key('fk_invite_roles_invite_id_invite', 'invite', ['invite_id'], ['id'])
		batch_op.create_foreign_key('fk_invite_roles_role_id_role', 'role', ['role_id'], ['id'])

	with op.batch_alter_table('user', schema=None) as batch_op:
		batch_op.add_column(sa.Column('dn', sa.String(length=128), nullable=True)) # temporarily nullable
	user_table = sa.Table('user', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=False),
		sa.Column('unix_uid', sa.Integer(), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=False),
		sa.Column('displayname', sa.String(length=128), nullable=False),
		sa.Column('mail', sa.String(length=128), nullable=False),
		sa.Column('pwhash', sa.String(length=256), nullable=True),
		sa.Column('is_service_user', sa.Boolean(create_constraint=True, name=op.f('ck_user_is_service_user')), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
		sa.UniqueConstraint('loginname', name=op.f('uq_user_loginname')),
		sa.UniqueConstraint('unix_uid', name=op.f('uq_user_unix_uid'))
	)
	user_dn_map_table = op.create_table('user_dn_map', # deleted later
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_user_dn_map')),
		sa.UniqueConstraint('dn', name=op.f('uq_user_dn_map_dn')),
		sa.UniqueConstraint('loginname', name=op.f('uq_user_dn_map_loginname'))
	)
	rows = [{'dn': user['dn'], 'loginname': user['loginname']} for user in ldap_users]
	op.bulk_insert(user_dn_map_table, rows)
	op.execute(user_table.update().values(dn=sa.select(user_dn_map_table.c.dn).where(user_table.c.loginname==user_dn_map_table.c.loginname).as_scalar()))
	with op.batch_alter_table('user', copy_from=user_table) as batch_op:
		pass # Recreate table with dn not nullable
	op.drop_table('user_dn_map')

	with op.batch_alter_table('group', schema=None) as batch_op:
		batch_op.add_column(sa.Column('dn', sa.String(length=128), nullable=True)) # temporarily nullable
	group_table = sa.Table('group', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=False),
		sa.Column('unix_gid', sa.Integer(), nullable=False),
		sa.Column('name', sa.String(length=32), nullable=False),
		sa.Column('description', sa.String(length=128), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_group')),
		sa.UniqueConstraint('name', name=op.f('uq_group_name')),
		sa.UniqueConstraint('unix_gid', name=op.f('uq_group_unix_gid'))
	)
	group_dn_map_table = op.create_table('group_dn_map', # deleted later
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=False),
		sa.Column('name', sa.String(length=32), nullable=False),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_group_dn_map')),
		sa.UniqueConstraint('dn', name=op.f('uq_group_dn_map_dn')),
		sa.UniqueConstraint('name', name=op.f('uq_group_dn_map_name'))
	)
	rows = [{'dn': group['dn'], 'name': group['name']} for group in ldap_groups]
	op.bulk_insert(group_dn_map_table, rows)
	op.execute(group_table.update().values(dn=sa.select(group_dn_map_table.c.dn).where(group_table.c.name==group_dn_map_table.c.name).as_scalar()))
	with op.batch_alter_table('group', copy_from=group_table) as batch_op:
		pass # Recreate table with dn not nullable
	op.drop_table('group_dn_map')

	with op.batch_alter_table('passwordToken', schema=None) as batch_op:
		batch_op.add_column(sa.Column('loginname', sa.String(length=32), nullable=True))
	password_token = sa.Table('passwordToken', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('loginname', sa.String(length=32), nullable=True),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_passwordToken_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_passwordToken'))
	)
	op.execute(password_token.update().values(loginname=sa.select(user_table.c.loginname).where(password_token.c.user_id==user_table.c.id).as_scalar()))
	with op.batch_alter_table('passwordToken', copy_from=password_token) as batch_op:
		batch_op.drop_constraint(batch_op.f('fk_passwordToken_user_id_user'), type_='foreignkey')
		batch_op.alter_column('created', existing_type=sa.DateTime(), nullable=True)
		batch_op.drop_column('user_id')

	with op.batch_alter_table('mailToken', schema=None) as batch_op:
		batch_op.add_column(sa.Column('loginname', sa.String(length=32), nullable=True))
	mail_token = sa.Table('mailToken', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('newmail', sa.String(length=255), nullable=True),
		sa.Column('loginname', sa.String(length=32), nullable=True),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_mailToken_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mailToken'))
	)
	op.execute(mail_token.update().values(loginname=sa.select(user_table.c.loginname).where(mail_token.c.user_id==user_table.c.id).as_scalar()))
	with op.batch_alter_table('mailToken', copy_from=mail_token) as batch_op:
		batch_op.drop_constraint(batch_op.f('fk_mailToken_user_id_user'), type_='foreignkey')
		batch_op.drop_column('user_id')

	with op.batch_alter_table('signup', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_dn', sa.String(length=128), nullable=True))
	signup = sa.Table('signup', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('loginname', sa.Text(), nullable=True),
		sa.Column('displayname', sa.Text(), nullable=True),
		sa.Column('mail', sa.Text(), nullable=True),
		sa.Column('pwhash', sa.Text(), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=True),
		sa.Column('user_dn', sa.String(length=128), nullable=True),
		sa.Column('type', sa.String(length=50), nullable=True),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_signup_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_signup')),
		sa.UniqueConstraint('user_id', name=op.f('uq_signup_user_id'))
	)
	op.execute(signup.update().values(user_dn=sa.select(user_table.c.dn).where(signup.c.user_id==user_table.c.id).as_scalar()))
	with op.batch_alter_table('signup', copy_from=signup) as batch_op:
		batch_op.drop_constraint('fk_signup_user_id_user', 'foreignkey')
		batch_op.drop_constraint('uq_signup_user_id', 'unique')
		batch_op.drop_column('user_id')

	with op.batch_alter_table('role', schema=None) as batch_op:
		batch_op.add_column(sa.Column('moderator_group_dn', sa.String(length=128), nullable=True))
	role = sa.Table('role', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('name', sa.String(length=32), nullable=True),
		sa.Column('description', sa.Text(), nullable=True),
		sa.Column('moderator_group_id', sa.Integer(), nullable=True),
		sa.Column('moderator_group_dn', sa.String(length=128), nullable=True),
		sa.Column('locked', sa.Boolean(create_constraint=True, name=op.f('ck_role_locked')), nullable=False),
		sa.Column('is_default', sa.Boolean(create_constraint=True, name=op.f('ck_role_is_default')), nullable=False),
		sa.ForeignKeyConstraint(['moderator_group_id'], ['group.id'], name=op.f('fk_role_moderator_group_id_group'), onupdate='CASCADE', ondelete='SET NULL'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_role')),
		sa.UniqueConstraint('name', name=op.f('uq_role_name'))
	)
	op.execute(role.update().values(moderator_group_dn=sa.select(group_table.c.dn).where(role.c.moderator_group_id==group_table.c.id).as_scalar()))
	with op.batch_alter_table('role', copy_from=role) as batch_op:
		batch_op.alter_column('description', existing_type=sa.Text(), nullable=True)
		batch_op.alter_column('name', existing_type=sa.String(length=32), nullable=True)
		batch_op.drop_constraint('fk_role_moderator_group_id_group', 'foreignkey')
		batch_op.drop_column('moderator_group_id')

	with op.batch_alter_table('oauth2token', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_dn', sa.String(length=128), nullable=True))
	oauth2token = sa.Table('oauth2token', meta,
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('user_dn', sa.String(length=128), nullable=True),
		sa.Column('client_id', sa.String(length=40), nullable=False),
		sa.Column('token_type', sa.String(length=40), nullable=False),
		sa.Column('access_token', sa.String(length=255), nullable=False),
		sa.Column('refresh_token', sa.String(length=255), nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_oauth2token_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2token')),
		sa.UniqueConstraint('access_token', name=op.f('uq_oauth2token_access_token')),
		sa.UniqueConstraint('refresh_token', name=op.f('uq_oauth2token_refresh_token'))
	)
	op.execute(oauth2token.update().values(user_dn=sa.select(user_table.c.dn).where(oauth2token.c.user_id==user_table.c.id).as_scalar()))
	op.execute(oauth2token.delete().where(oauth2token.c.user_dn==None))
	with op.batch_alter_table('oauth2token', copy_from=oauth2token) as batch_op:
		batch_op.alter_column('_scopes', nullable=True, existing_type=sa.Text())
		batch_op.alter_column('access_token', nullable=True, existing_type=sa.String(length=255))
		batch_op.alter_column('client_id', nullable=True, existing_type=sa.String(length=40))
		batch_op.alter_column('expires', nullable=True, existing_type=sa.DateTime())
		batch_op.alter_column('refresh_token', nullable=True, existing_type=sa.String(length=255))
		batch_op.alter_column('token_type', nullable=True, existing_type=sa.String(length=40))
		batch_op.drop_constraint('fk_oauth2token_user_id_user', 'foreignkey')
		batch_op.drop_column('user_id')

	with op.batch_alter_table('oauth2grant', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_dn', sa.String(length=128), nullable=True))
	oauth2grant = sa.Table('oauth2grant', meta,
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('user_dn', sa.String(length=128), nullable=True),
		sa.Column('client_id', sa.String(length=40), nullable=False),
		sa.Column('code', sa.String(length=255), nullable=False),
		sa.Column('redirect_uri', sa.String(length=255), nullable=False),
		sa.Column('expires', sa.DateTime(), nullable=False),
		sa.Column('_scopes', sa.Text(), nullable=False),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_oauth2grant_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth2grant')),
		sa.Index('ix_oauth2grant_code', 'code')
	)
	op.execute(oauth2grant.update().values(user_dn=sa.select(user_table.c.dn).where(oauth2grant.c.user_id==user_table.c.id).as_scalar()))
	op.execute(oauth2grant.delete().where(oauth2grant.c.user_dn==None))
	with op.batch_alter_table('oauth2grant', copy_from=oauth2grant) as batch_op:
		batch_op.alter_column('_scopes', nullable=True, existing_type=sa.Text())
		batch_op.alter_column('client_id', nullable=True, existing_type=sa.String(length=40))
		batch_op.alter_column('expires', nullable=True, existing_type=sa.DateTime())
		batch_op.alter_column('redirect_uri', nullable=True, existing_type=sa.String(length=255))
		batch_op.drop_constraint('fk_oauth2grant_user_id_user', 'foreignkey')
		batch_op.drop_column('user_id')

	with op.batch_alter_table('mfa_method', schema=None) as batch_op:
		batch_op.add_column(sa.Column('dn', sa.String(length=128), nullable=True))
	mfa_method = sa.Table('mfa_method', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('type', sa.Enum('RECOVERY_CODE', 'TOTP', 'WEBAUTHN', create_constraint=True, name='ck_mfa_method_type'), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('name', sa.String(length=128), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('dn', sa.String(length=128), nullable=True),
		sa.Column('recovery_salt', sa.String(length=64), nullable=True),
		sa.Column('recovery_hash', sa.String(length=256), nullable=True),
		sa.Column('totp_key', sa.String(length=64), nullable=True),
		sa.Column('webauthn_cred', sa.Text(), nullable=True),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_mfa_method_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_mfa_method'))
	)
	op.execute(mfa_method.update().values(dn=sa.select(user_table.c.dn).where(mfa_method.c.user_id==user_table.c.id).as_scalar()))
	op.execute(mfa_method.delete().where(mfa_method.c.dn==None))
	with op.batch_alter_table('mfa_method', copy_from=mfa_method) as batch_op:
		batch_op.drop_constraint('fk_mfa_method_user_id_user', 'foreignkey')
		batch_op.alter_column('type', existing_type=sa.Enum('RECOVERY_CODE', 'TOTP', 'WEBAUTHN', create_constraint=True, name='ck_mfa_method_type'), nullable=True)
		batch_op.alter_column('created', existing_type=sa.DateTime(), nullable=True)
		batch_op.drop_column('user_id')

	with op.batch_alter_table('invite_grant', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_dn', sa.String(length=128), nullable=True))
	invite_grant = sa.Table('invite_grant', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('invite_id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('user_dn', sa.String(length=128), nullable=False),
		sa.ForeignKeyConstraint(['invite_id'], ['invite.id'], name=op.f('fk_invite_grant_invite_id_invite'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_invite_grant_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_invite_grant'))
	)
	op.execute(invite_grant.update().values(user_dn=sa.select(user_table.c.dn).where(invite_grant.c.user_id==user_table.c.id).as_scalar()))
	op.execute(invite_grant.delete().where(invite_grant.c.user_dn==None))
	with op.batch_alter_table('invite_grant', copy_from=invite_grant) as batch_op:
		batch_op.drop_constraint('fk_invite_grant_user_id_user', 'foreignkey')
		batch_op.drop_constraint(batch_op.f('fk_invite_grant_invite_id_invite'), type_='foreignkey')
		batch_op.create_foreign_key('fk_invite_grant_invite_id_invite', 'invite', ['invite_id'], ['id'])
		batch_op.drop_column('user_id')

	with op.batch_alter_table('invite', schema=None) as batch_op:
		batch_op.add_column(sa.Column('creator_dn', sa.String(length=128), nullable=True))
	invite = sa.Table('invite', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('token', sa.String(length=128), nullable=False),
		sa.Column('created', sa.DateTime(), nullable=False),
		sa.Column('creator_id', sa.Integer(), nullable=True),
		sa.Column('creator_dn', sa.String(length=128), nullable=True),
		sa.Column('valid_until', sa.DateTime(), nullable=False),
		sa.Column('single_use', sa.Boolean(create_constraint=True, name=op.f('ck_invite_single_use')), nullable=False),
		sa.Column('allow_signup', sa.Boolean(create_constraint=True, name=op.f('ck_invite_allow_signup')), nullable=False),
		sa.Column('used', sa.Boolean(create_constraint=True, name=op.f('ck_invite_used')), nullable=False),
		sa.Column('disabled', sa.Boolean(create_constraint=True, name=op.f('ck_invite_disabled')), nullable=False),
		sa.ForeignKeyConstraint(['creator_id'], ['user.id'], name=op.f('fk_invite_creator_id_user')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_invite')),
		sa.UniqueConstraint('token', name=op.f('uq_invite_token'))
	)
	op.execute(invite.update().values(creator_dn=sa.select(user_table.c.dn).where(invite.c.creator_id==user_table.c.id).as_scalar()))
	with op.batch_alter_table('invite', copy_from=invite) as batch_op:
		batch_op.drop_constraint('fk_invite_creator_id_user', 'foreignkey')
		batch_op.drop_column('creator_id')

	with op.batch_alter_table('device_login_confirmation', schema=None) as batch_op:
		batch_op.add_column(sa.Column('user_dn', sa.String(length=128), nullable=True))
	device_login_confirmation = sa.Table('device_login_confirmation', meta,
		sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
		sa.Column('initiation_id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('user_dn', sa.String(length=128), nullable=False),
		sa.Column('code0', sa.String(length=32), nullable=False),
		sa.Column('code1', sa.String(length=32), nullable=False),
		sa.ForeignKeyConstraint(['initiation_id'], ['device_login_initiation.id'], name=op.f('fk_device_login_confirmation_initiation_id_')),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_device_login_confirmation_user_id_user')),
		sa.PrimaryKeyConstraint('id', name=op.f('pk_device_login_confirmation')),
		sa.UniqueConstraint('initiation_id', 'code0', name='uq_device_login_confirmation_initiation_id_code0'),
		sa.UniqueConstraint('initiation_id', 'code1', name='uq_device_login_confirmation_initiation_id_code1'),
		sa.UniqueConstraint('user_dn', name=op.f('uq_device_login_confirmation_user_dn'))
	)
	op.execute(device_login_confirmation.update().values(user_dn=sa.select(user_table.c.dn).where(device_login_confirmation.c.user_id==user_table.c.id).as_scalar()))
	op.execute(device_login_confirmation.delete().where(device_login_confirmation.c.user_dn==None))
	with op.batch_alter_table('device_login_confirmation', copy_from=device_login_confirmation) as batch_op:
		batch_op.drop_constraint('fk_device_login_confirmation_user_id_user', 'foreignkey')
		batch_op.drop_constraint('fk_device_login_confirmation_initiation_id_', type_='foreignkey')
		batch_op.create_foreign_key('fk_device_login_confirmation_initiation_id_', 'device_login_initiation', ['initiation_id'], ['id'])
		batch_op.drop_column('user_id')

	with op.batch_alter_table('role_members', schema=None) as batch_op:
		batch_op.add_column(sa.Column('dn', sa.String(length=128), nullable=True))
	op.rename_table('role_members', 'role-user')
	role_members_table = sa.Table('role-user', meta,
		sa.Column('dn', sa.String(length=128), nullable=True),
		sa.Column('role_id', sa.Integer(), nullable=True),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_role_members_user_id_user'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role_members_role_id_role'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('role_id', 'user_id', name=op.f('pk_role_members'))
	)
	op.execute(role_members_table.update().values(dn=sa.select(user_table.c.dn).where(role_members_table.c.user_id==user_table.c.id).as_scalar()))
	op.execute(role_members_table.delete().where(role_members_table.c.dn==None))
	with op.batch_alter_table('role-user', copy_from=role_members_table, recreate='always') as batch_op:
		batch_op.drop_constraint('fk_role_members_role_id_role', 'foreignkey')
		batch_op.create_foreign_key(batch_op.f('fk_role-user_role_id_role'), 'role', ['role_id'], ['id'])
		batch_op.alter_column('dn', nullable=False, existing_type=sa.String(length=128))
		batch_op.add_column(sa.Column('id', sa.Integer(), nullable=True))
		batch_op.drop_constraint('fk_role_members_user_id_user', 'foreignkey')
		batch_op.drop_constraint('pk_role_members', 'primary')
		batch_op.create_primary_key('pk_role-user', ['id'])
		batch_op.alter_column('id', autoincrement=True, nullable=False, existing_type=sa.Integer())
		batch_op.create_unique_constraint(batch_op.f('uq_role-user_dn'), ['dn', 'role_id'])
		batch_op.alter_column('role_id', existing_type=sa.Integer(), nullable=False)
		batch_op.drop_column('user_id')

	with op.batch_alter_table('role_groups', schema=None) as batch_op:
		batch_op.add_column(sa.Column('group_dn', sa.String(length=128), nullable=True))
	op.rename_table('role_groups', 'role-group')
	role_groups_table = sa.Table('role-group', meta,
		sa.Column('role_id', sa.Integer(), nullable=False),
		sa.Column('group_dn', sa.String(length=128), nullable=True),
		sa.Column('group_id', sa.Integer(), nullable=False),
		sa.Column('requires_mfa', sa.Boolean(create_constraint=False), nullable=False),
		sa.CheckConstraint('requires_mfa in (0,1)', name=op.f('ck_role_groups_requires_mfa')),
		sa.ForeignKeyConstraint(['group_id'], ['group.id'], name=op.f('fk_role_groups_group_id_group'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_role_groups_role_id_role'), onupdate='CASCADE', ondelete='CASCADE'),
		sa.PrimaryKeyConstraint('role_id', 'group_id', name=op.f('pk_role_groups'))
	)
	op.execute(role_groups_table.update().values(group_dn=sa.select(group_table.c.dn).where(role_groups_table.c.group_id==group_table.c.id).as_scalar()))
	op.execute(role_groups_table.delete().where(role_groups_table.c.group_dn==None))
	with op.batch_alter_table('role-group', copy_from=role_groups_table) as batch_op:
		batch_op.drop_constraint('fk_role_groups_group_id_group', 'foreignkey')
		batch_op.drop_constraint('fk_role_groups_role_id_role', 'foreignkey')
		batch_op.drop_constraint('ck_role_groups_requires_mfa', 'check')
		batch_op.create_check_constraint('ck_role-group_requires_mfa', role_groups_table.c.requires_mfa.in_([0,1]))
		batch_op.alter_column('group_dn', nullable=False, existing_type=sa.String(length=128))
		batch_op.drop_constraint('pk_role_groups', 'primary')
		batch_op.create_primary_key('pk_role-group', ['role_id', 'group_dn'])
		batch_op.create_foreign_key(batch_op.f('fk_role-group_role_id_role'), 'role', ['role_id'], ['id'])
		batch_op.drop_column('group_id')

	op.drop_table('mail_receive_address')
	op.drop_table('mail_destination_address')
	op.drop_table('mail')
	op.drop_table('user_groups')
	op.drop_table('user')
	op.drop_table('group')
