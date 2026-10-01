import os
import unittest
from uuid import UUID

from flask import url_for
import flask_migrate

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

class AppTestCase(unittest.TestCase):
	DISABLE_SQLITE_MEMORY_DB = False

	def setUp(self):
		config = {
			'TESTING': True,
			'DEBUG': True,
			'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
			'SECRET_KEY': 'DEBUGKEY',
			'MAIL_SKIP_SEND': True,
			'SELF_SIGNUP': True,
		}
		if self.DISABLE_SQLITE_MEMORY_DB:
			try:
				os.remove('/tmp/uffd-migration-test-db.sqlite3')
			except FileNotFoundError:
				pass
			config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/uffd-migration-test-db.sqlite3'
		if os.environ.get('TEST_WITH_MYSQL'):
			import MySQLdb
			conn = MySQLdb.connect(user='root', unix_socket='/var/run/mysqld/mysqld.sock')
			cur = conn.cursor()
			try:
				cur.execute('DROP DATABASE uffd_tests')
			except:
				pass
			cur.execute('CREATE DATABASE uffd_tests CHARACTER SET utf8mb4 COLLATE utf8mb4_nopad_bin')
			conn.close()
			config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqldb:///uffd_tests?unix_socket=/var/run/mysqld/mysqld.sock&charset=utf8mb4'
		self.app = create_app(config)
		self.setUpApp()

	def setUpApp(self):
		pass

	def tearDown(self):
		if self.DISABLE_SQLITE_MEMORY_DB:
			try:
				os.remove('/tmp/uffd-migration-test-db.sqlite3')
			except FileNotFoundError:
				pass

class MigrationTestCase(AppTestCase):
	DISABLE_SQLITE_MEMORY_DB = True

	REVISION = None

	def setUp(self):
		super().setUp()
		self.request_context = self.app.test_request_context()
		self.request_context.__enter__()
		if self.REVISION:
			flask_migrate.upgrade(revision=self.REVISION + '-1')

	def upgrade(self, revision='+1'):
		db.session.commit()
		flask_migrate.upgrade(revision=revision)

	def downgrade(self, revision='-1'):
		db.session.commit()
		flask_migrate.downgrade(revision=revision)

	def tearDown(self):
		db.session.rollback()
		self.request_context.__exit__(None, None, None)
		super().tearDown()

class ModelTestCase(AppTestCase):
	def setUp(self):
		super().setUp()
		self.request_context = self.app.test_request_context()
		self.request_context.__enter__()
		db.create_all()
		db.session.commit()

	def tearDown(self):
		db.session.rollback()
		self.request_context.__exit__(None, None, None)
		super().tearDown()

class UffdTestCase(AppTestCase):
	def setUp(self):
		super().setUp()
		self.client = self.app.test_client()
		self.client.__enter__()
		# Just do some request so that we can use url_for
		self.client.get(path='/')
		db.create_all()
		# This reflects the old LDAP example data
		users_group = Group(name='users', unix_gid=20001, uuid=UUID('a1111111-1111-1111-1111-111111111111'), description='Base group for all users')
		db.session.add(users_group)
		access_group = Group(name='uffd_access', unix_gid=20002, uuid=UUID('b2222222-2222-2222-2222-222222222222'), description='Access to Single-Sign-On and Selfservice')
		db.session.add(access_group)
		admin_group = Group(name='uffd_admin', unix_gid=20003, uuid=UUID('c3333333-3333-3333-3333-333333333333'), description='Admin access to uffd')
		db.session.add(admin_group)
		testuser = User(loginname='testuser', unix_uid=10000, uuid=UUID('d4444444-4444-4444-4444-444444444444'), password='userpassword', primary_email_address='test@example.com', displayname='Test User', groups=[users_group, access_group])
		db.session.add(testuser)
		testadmin = User(loginname='testadmin', unix_uid=10001, uuid=UUID('e5555555-5555-5555-5555-555555555555'), password='adminpassword', primary_email_address='admin@example.com', displayname='Test Admin', groups=[users_group, access_group, admin_group])
		db.session.add(testadmin)
		testmail = Mail(uid='test', receivers=['test1@example.com', 'test2@example.com'], destinations=['testuser@mail.example.com'])
		db.session.add(testmail)
		self.setUpDB()
		db.session.commit()

	def setUpDB(self):
		pass

	def tearDown(self):
		self.client.__exit__(None, None, None)
		super().tearDown()

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
