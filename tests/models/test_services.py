import itertools

from uffd.remailer import remailer
from uffd.tasks import cleanup_task
from uffd.database import db
from uffd.models import Service, ServiceUser, User, UserEmail, RemailerMode

from tests.utils import UffdTestCase

class TestServiceUser(UffdTestCase):
	def setUp(self):
		super().setUp()
		db.session.add_all([Service(name='service1', limit_access=False), Service(name='service2', remailer_mode=RemailerMode.ENABLED_V1, limit_access=False)])
		db.session.commit()

	def test_auto_create(self):
		service_count = Service.query.count()
		user_count = User.query.count()
		self.assertEqual(ServiceUser.query.count(), service_count * user_count)
		db.session.add(User(loginname='newuser1', displayname='New User', primary_email_address='new1@example.com'))
		db.session.commit()
		self.assertEqual(ServiceUser.query.count(), service_count * (user_count + 1))
		db.session.add(Service(name='service3'))
		db.session.commit()
		self.assertEqual(ServiceUser.query.count(), (service_count + 1) * (user_count + 1))
		db.session.add(User(loginname='newuser2', displayname='New User', primary_email_address='new2@example.com'))
		db.session.add(User(loginname='newuser3', displayname='New User', primary_email_address='new3@example.com'))
		db.session.add(Service(name='service4'))
		db.session.add(Service(name='service5'))
		db.session.commit()
		self.assertEqual(ServiceUser.query.count(), (service_count + 3) * (user_count + 3))

	def test_create_missing(self):
		service_count = Service.query.count()
		user_count = User.query.count()
		self.assertEqual(ServiceUser.query.count(), service_count * user_count)
		db.session.delete(ServiceUser.query.first())
		db.session.commit()
		self.assertEqual(ServiceUser.query.count(), service_count * user_count - 1)
		cleanup_task.run()
		db.session.commit()
		self.assertEqual(ServiceUser.query.count(), service_count  * user_count)

	def test_effective_remailer_mode(self):
		self.app.config['REMAILER_DOMAIN'] = 'remailer.example.com'
		user = self.get_user()
		service = Service.query.filter_by(name='service1').first()
		service.remailer_mode = RemailerMode.ENABLED_V2
		service_user = ServiceUser.query.get((service.id, user.id))
		self.assertEqual(service_user.effective_remailer_mode, RemailerMode.ENABLED_V2)
		service_user.remailer_overwrite_mode = RemailerMode.ENABLED_V1
		service.remailer_mode = RemailerMode.DISABLED
		self.assertEqual(service_user.effective_remailer_mode, RemailerMode.ENABLED_V1)
		self.app.config['REMAILER_DOMAIN'] = ''
		self.assertEqual(service_user.effective_remailer_mode, RemailerMode.DISABLED)

	def test_service_email(self):
		user = self.get_user()
		service = Service.query.filter_by(name='service1').first()
		service_user = ServiceUser.query.get((service.id, user.id))
		self.assertEqual(service_user.service_email, None)
		service_user.service_email = UserEmail(user=user, address='foo@bar', verified=True)
		with self.assertRaises(Exception):
			service_user.service_email = UserEmail(user=user, address='foo2@bar', verified=False)
		with self.assertRaises(Exception):
			service_user.service_email = UserEmail(user=self.get_admin(), address='foo3@bar', verified=True)

	def test_real_email(self):
		user = self.get_user()
		service = Service.query.filter_by(name='service1').first()
		service_user = ServiceUser.query.get((service.id, user.id))
		self.assertEqual(service_user.real_email, user.primary_email.address)
		service_user.service_email = UserEmail(user=user, address='foo@bar', verified=True)
		self.assertEqual(service_user.real_email, user.primary_email.address)
		service.enable_email_preferences = True
		self.assertEqual(service_user.real_email, service_user.service_email.address)
		service.limit_access = True
		self.assertEqual(service_user.real_email, user.primary_email.address)
		service.access_group = self.get_admin_group()
		self.assertEqual(service_user.real_email, user.primary_email.address)
		service.access_group = self.get_users_group()
		self.assertEqual(service_user.real_email, service_user.service_email.address)

	def test_get_by_remailer_email(self):
		user = self.get_user()
		service = Service.query.filter_by(name='service1').first()
		service_user = ServiceUser.query.get((service.id, user.id))
		self.app.config['REMAILER_DOMAIN'] = 'remailer.example.com'
		remailer_email = remailer.build_v1_address(service.id, user.id)
		# 1. remailer not setup
		self.app.config['REMAILER_DOMAIN'] = ''
		self.assertIsNone(ServiceUser.get_by_remailer_email(user.primary_email.address))
		self.assertIsNone(ServiceUser.get_by_remailer_email(remailer_email))
		self.assertIsNone(ServiceUser.get_by_remailer_email('invalid'))
		# 2. remailer setup
		self.app.config['REMAILER_DOMAIN'] = 'remailer.example.com'
		self.assertIsNone(ServiceUser.get_by_remailer_email(user.primary_email.address))
		self.assertEqual(ServiceUser.get_by_remailer_email(remailer_email), service_user)
		self.assertIsNone(ServiceUser.get_by_remailer_email('invalid'))

	def test_email(self):
		user = self.get_user()
		service = Service.query.filter_by(name='service1').first()
		service_user = ServiceUser.query.get((service.id, user.id))
		self.app.config['REMAILER_DOMAIN'] = 'remailer.example.com'
		remailer_email = remailer.build_v1_address(service.id, user.id)
		# 1. remailer not setup
		self.app.config['REMAILER_DOMAIN'] = ''
		self.assertEqual(service_user.email, user.primary_email.address)
		# 2. remailer setup + remailer disabled
		self.app.config['REMAILER_DOMAIN'] = 'remailer.example.com'
		self.assertEqual(service_user.email, user.primary_email.address)
		# 3. remailer setup + remailer enabled
		service.remailer_mode = RemailerMode.ENABLED_V1
		db.session.commit()
		self.assertEqual(service_user.email, remailer_email)
		# 4. remailer setup + remailer disabled + user overwrite
		service.remailer_mode = RemailerMode.DISABLED
		service_user.remailer_overwrite_mode = RemailerMode.ENABLED_V1
		self.assertEqual(service_user.email, remailer_email)
		# 5. remailer setup + remailer enabled + user overwrite
		service.remailer_mode = RemailerMode.ENABLED_V1
		service_user.remailer_overwrite_mode = RemailerMode.DISABLED
		self.assertEqual(service_user.email, user.primary_email.address)

	def test_filter_query_by_email(self):
		service = Service.query.filter_by(name='service1').first()
		user = self.get_user()
		self.app.config['REMAILER_DOMAIN'] = 'remailer.example.com'
		remailer_email_v1 = remailer.build_v1_address(service.id, user.id)
		remailer_email_v2 = remailer.build_v2_address(service.id, user.id)
		email1 = user.primary_email
		email2 = UserEmail(user=user, address='test2@example.com', verified=True)
		db.session.add(email2)
		service_user = ServiceUser.query.get((service.id, user.id))
		all_service_users = ServiceUser.query.all()
		cases = itertools.product(
			# Input values
			[
				'test@example.com',
				'test2@example.com',
				'other@example.com',
				remailer_email_v1,
				remailer_email_v2,
			],
			# REMAILER_DOMAIN config
			[None, 'remailer.example.com'],
			# service.remailer_mode
			[RemailerMode.DISABLED, RemailerMode.ENABLED_V1, RemailerMode.ENABLED_V2],
			# service.enable_email_preferences
			[True, False],
			# service.limit_access, service.access_group
			[(False, None), (True, None), (True, self.get_admin_group()), (True, self.get_users_group())],
			# service_user.service_email
			[None, email1, email2],
			# service_user.remailer_overwrite_mode
			[None, RemailerMode.DISABLED, RemailerMode.ENABLED_V1, RemailerMode.ENABLED_V2],
		)
		for options in cases:
			value = options[0]
			self.app.config['REMAILER_DOMAIN'] = options[1]
			service.remailer_mode = options[2]
			service.enable_email_preferences = options[3]
			service.limit_access, service.access_group = options[4]
			service_user.service_email = options[5]
			service_user.remailer_overwrite_mode = options[6]
			a = {result for result in all_service_users if result.email == value}
			b = set(ServiceUser.filter_query_by_email(ServiceUser.query, value).all())
			if a != b:
				self.fail(f'{a} != {b} with ' + repr(options))
