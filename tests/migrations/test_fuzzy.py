import os
import sys
import datetime

from uffd.database import db
from uffd.models import (
	User, UserEmail, Group,
	RecoveryCodeMethod, TOTPMethod, WebauthnMethod,
	Role, RoleGroup,
	Signup,
	Invite, InviteGrant, InviteSignup,
	DeviceLoginConfirmation,
	Service,
	OAuth2Client, OAuth2LogoutURI, OAuth2Grant, OAuth2Token, OAuth2DeviceLoginInitiation,
	PasswordToken,
	Session,
)

from tests.utils import MigrationTestCase

class TestFuzzy(MigrationTestCase):
	def setUpApp(self):
		self.app.config['LDAP_SERVICE_MOCK'] = True
		self.app.config['OAUTH2_CLIENTS'] = {
			'test': {
				'service_name': 'test',
				'client_secret': 'testsecret',
				'redirect_uris': ['http://localhost:5004/oauthproxy/callback'],
				'logout_urls': ['http://localhost:5004/oauthproxy/logout']
			}
		}
		self.app.config['API_CLIENTS_2'] = {
			'test': {
				'service_name': 'test',
				'client_secret': 'testsecret',
				'scopes': ['checkpassword', 'getusers', 'getmails']
			},
		}
		self.app.config['DELETE_ALL_MAIL_FORWARDINGS'] = True

	# Runs every upgrade/downgrade script with data. To do this we first upgrade
	# to head, create data, then downgrade, upgrade, downgrade for every revision.
	def test_migrations_fuzzy(self):
		self.upgrade('head')
		# Users and groups were created by 878b25c4fae7_ldap_to_db because we set LDAP_SERVICE_MOCK to True
		user = User.query.first()
		group = Group.query.first()
		db.session.add(RecoveryCodeMethod(user=user))
		db.session.add(TOTPMethod(user=user, name='mytotp'))
		db.session.add(WebauthnMethod(user=user, name='mywebauthn', cred=b''))
		role = Role(name='role', groups={group: RoleGroup(group=group)})
		db.session.add(role)
		role.members.append(user)
		db.session.add(Role(name='base', included_roles=[role], locked=True, is_default=True, moderator_group=group, groups={group: RoleGroup(group=group)}))
		db.session.add(Signup(loginname='newuser', displayname='New User', mail='newuser@example.com', password='newpassword'))
		db.session.add(Signup(loginname='testuser', displayname='Testuser', mail='testuser@example.com', password='testpassword', user=user))
		invite = Invite(valid_until=datetime.datetime.now(), roles=[role])
		db.session.add(invite)
		invite.signups.append(InviteSignup(loginname='newuser', displayname='New User', mail='newuser@example.com', password='newpassword'))
		invite.grants.append(InviteGrant(user=user))
		db.session.add(Invite(creator=user, valid_until=datetime.datetime.now()))
		service = Service(name='testservice', access_group=group)
		oauth2_client = OAuth2Client(service=service, client_id='testclient', client_secret='testsecret', redirect_uris=['http://localhost:1234/callback'], logout_uris=[OAuth2LogoutURI(method='GET', uri='http://localhost:1234/callback')])
		db.session.add_all([service, oauth2_client])
		session = Session(
			user=user,
			secret='0919de9da3f7dc6c33ab849f44c20e8221b673ca701030de17488f3269fc5469f100e2ce56e5fd71305b23d8ecbb06d80d22004adcd3fefc5f5fcb80a436e31f2c2d9cc8fe8c59ae44871ae4524408d312474570280bf29d3ba145a4bd00010ca758eaa0795b180ec12978b42d13bf4c4f06f72103d44077022ce656610be855',
			ip_address='127.0.0.1',
			user_agent='Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0',
		)
		db.session.add(session)
		db.session.add(OAuth2Grant(session=session, client=oauth2_client, _code='testcode', redirect_uri='http://example.com/callback', expires=datetime.datetime.now()))
		db.session.add(OAuth2Token(session=session, client=oauth2_client, token_type='Bearer', _access_token='testcode', _refresh_token='testcode', expires=datetime.datetime.now()))
		db.session.add(OAuth2DeviceLoginInitiation(client=oauth2_client, confirmations=[DeviceLoginConfirmation(session=session)]))
		db.session.add(PasswordToken(user=user))
		db.session.commit()
		revs = [s.split('_', 1)[0] for s in os.listdir('uffd/migrations/versions') if '_' in s and s.endswith('.py')]
		for rev in revs:
			self.downgrade('-1')
			self.upgrade('+1')
			self.downgrade('-1')
