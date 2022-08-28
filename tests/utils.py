import os
import tempfile
import shutil
import unittest

from flask import request, url_for

from uffd import create_app, db
from uffd.models import User, Group, Mail

def dump(basename, resp):
	basename = basename.replace('.', '_').replace('/', '_')
	suffix = '.html'
	root = os.environ.get('DUMP_PAGES')
	if not root:
		return
	os.makedirs(root, exist_ok=True)
	path = os.path.join(root, basename+suffix)
	with open(path, 'wb') as f:
		f.write(resp.data)

def db_flush():
	db.session.rollback()
	db.session.expire_all()

class UffdTestCase(unittest.TestCase):
	def get_user(self):
		return User.query.filter_by(loginname='testuser').one_or_none()

	def get_admin(self):
		return User.query.filter_by(loginname='testadmin').one_or_none()

	def get_admin_group(self):
		return Group.query.filter_by(name='uffd_admin').one_or_none()

	def get_access_group(self):
		return Group.query.filter_by(name='uffd_access').one_or_none()

	def get_users_group(self):
		return Group.query.filter_by(name='users').one_or_none()

	def get_mail(self):
		return Mail.query.filter_by(uid='test').one_or_none()

	def login_as(self, user, ref=None):
		# It is currently not possible to login while already logged in as another
		# user, so make sure that we are not logged in first
		self.client.get(path=url_for('session.logout'), follow_redirects=True)
		loginname = None
		password = None
		if user == 'user':
			loginname = 'testuser'
			password = 'userpassword'
		elif user == 'admin':
			loginname = 'testadmin'
			password = 'adminpassword'
		return self.client.post(path=url_for('session.login', ref=ref),
								data={'loginname': loginname, 'password': password}, follow_redirects=True)

	def setUp(self):
		# It would be far better to create a minimal app here, but since the
		# session module depends on almost everything else, that is not really feasable
		config = {
			'TESTING': True,
			'DEBUG': True,
			'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
			'SECRET_KEY': 'DEBUGKEY',
			'MAIL_SKIP_SEND': True,
			'SELF_SIGNUP': True,
		}
		config = self.setUpConfig(config)
		self.app = create_app(config)
		self.setUpApp()
		self.client = self.app.test_client()
		self.client.__enter__()
		# Just do some request so that we can use url_for
		self.client.get(path='/')
		db.create_all()
		# This reflects the old LDAP example data
		users_group = Group(name='users', unix_gid=20001, description='Base group for all users')
		db.session.add(users_group)
		access_group = Group(name='uffd_access', unix_gid=20002, description='Access to Single-Sign-On and Selfservice')
		db.session.add(access_group)
		admin_group = Group(name='uffd_admin', unix_gid=20003, description='Admin access to uffd')
		db.session.add(admin_group)
		testuser = User(loginname='testuser', unix_uid=10000, password='userpassword', primary_email_address='test@example.com', displayname='Test User', groups=[users_group, access_group])
		db.session.add(testuser)
		testadmin = User(loginname='testadmin', unix_uid=10001, password='adminpassword', primary_email_address='admin@example.com', displayname='Test Admin', groups=[users_group, access_group, admin_group])
		db.session.add(testadmin)
		testmail = Mail(uid='test', receivers=['test1@example.com', 'test2@example.com'], destinations=['testuser@mail.example.com'])
		db.session.add(testmail)
		self.setUpDB()
		db.session.commit()

	def setUpConfig(self, config):
		return config

	def setUpApp(self):
		pass

	def setUpDB(self):
		pass

	def tearDown(self):
		self.client.__exit__(None, None, None)
