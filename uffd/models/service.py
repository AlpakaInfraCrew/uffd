import enum

from flask import current_app
from flask_babel import get_locale
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Enum, DateTime
from sqlalchemy.orm import relationship, validates

from uffd.database import db
from uffd.remailer import remailer
from uffd.tasks import cleanup_task
from .user import User, UserEmail, user_groups

class RemailerMode(enum.Enum):
	DISABLED = 0
	ENABLED_V1 = 1
	ENABLED_V2 = 2

class Service(db.Model):
	__tablename__ = 'service'
	id = Column(Integer, primary_key=True, autoincrement=True)
	name = Column(String(255), unique=True, nullable=False)

	# If limit_access is False, all users have access and access_group is
	# ignored. This attribute exists for legacy API and OAuth2 clients that
	# were migrated from config definitions where a missing "required_group"
	# parameter meant no access restrictions. Representing this state by
	# setting access_group_id to NULL would lead to a bad/unintuitive ondelete
	# behaviour.
	limit_access = Column(Boolean(create_constraint=True), default=True, nullable=False)
	access_group_id = Column(Integer(), ForeignKey('group.id', onupdate='CASCADE', ondelete='SET NULL'), nullable=True)
	access_group = relationship('Group')

	oauth2_clients = relationship('OAuth2Client', back_populates='service', cascade='all, delete-orphan')
	api_clients = relationship('APIClient', back_populates='service', cascade='all, delete-orphan')

	remailer_mode = Column(Enum(RemailerMode, create_constraint=True), default=RemailerMode.DISABLED, nullable=False)
	enable_email_preferences = Column(Boolean(create_constraint=True), default=False, nullable=False)
	hide_deactivated_users = Column(Boolean(create_constraint=True), default=False, nullable=False)

class ServiceUser(db.Model):
	'''Service-related configuration and state for a user

	ServiceUser objects are auto-created whenever a new User or Service is
	created, so there one for for every (Service, User) pair.

	Service- or User-related code should always use ServiceUser in queries
	instead of User/Service.'''
	__tablename__ = 'service_user'
	__table_args__ = (
		db.PrimaryKeyConstraint('service_id', 'user_id'),
	)

	service_id = Column(Integer(), ForeignKey('service.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	service = relationship('Service', viewonly=True)
	user_id = Column(Integer(), ForeignKey('user.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
	user = relationship('User', viewonly=True)

	needs_sync = Column(Boolean())
	last_sync = Column(DateTime())
	sync_token = Column(String(32))
	sync_started = Column(DateTime())

	@property
	def has_access(self):
		return not self.service.limit_access or self.service.access_group in self.user.groups

	@property
	def has_email_preferences(self):
		return self.has_access and self.service.enable_email_preferences

	remailer_overwrite_mode = Column(Enum(RemailerMode, create_constraint=True), default=None, nullable=True)

	@property
	def effective_remailer_mode(self):
		if not remailer.configured:
			return RemailerMode.DISABLED
		if current_app.config['REMAILER_LIMIT_TO_USERS'] is not None:
			if self.user.loginname not in current_app.config['REMAILER_LIMIT_TO_USERS']:
				return RemailerMode.DISABLED
		if self.remailer_overwrite_mode is not None:
			return self.remailer_overwrite_mode
		return self.service.remailer_mode

	service_email_id = Column(Integer(), ForeignKey('user_email.id', onupdate='CASCADE', ondelete='SET NULL'))
	service_email = relationship('UserEmail')

	@validates('service_email')
	def validate_service_email(self, key, value): # pylint: disable=unused-argument
		if value is not None:
			if not value.user:
				value.user = self.user
			if value.user != self.user:
				raise ValueError('UserEmail assigned to ServiceUser.service_email is not associated with user')
			if not value.verified:
				raise ValueError('UserEmail assigned to serviceUser.service_email is not verified')
		return  value

	# Actual e-mail address that mails from the service are sent to
	@property
	def real_email(self):
		if self.has_email_preferences and self.service_email:
			return self.service_email.address
		return self.user.primary_email.address

	@classmethod
	def get_by_remailer_email(cls, address):
		if not remailer.configured:
			return None
		result = remailer.parse_address(address)
		if result is None:
			return None
		# result is (service_id, user_id), i.e. our primary key
		return cls.query.get(result)

	# E-Mail address as seen by the service
	@property
	def email(self):
		if self.effective_remailer_mode == RemailerMode.ENABLED_V1:
			return remailer.build_v1_address(self.service_id, self.user_id)
		if self.effective_remailer_mode == RemailerMode.ENABLED_V2:
			return remailer.build_v2_address(self.service_id, self.user_id)
		return self.real_email

	@classmethod
	def filter_query_by_email(cls, query, email):
		'''Filter query of ServiceUser by ServiceUser.email'''
		# pylint completely fails to understand SQLAlchemy's query functions
		# pylint: disable=no-member,invalid-name,singleton-comparison
		service_user = cls.get_by_remailer_email(email)
		if service_user and service_user.email == email:
			return query.filter(cls.user_id == service_user.user_id, cls.service_id == service_user.service_id)

		AliasedUser = db.aliased(User)
		AliasedPrimaryEmail = db.aliased(UserEmail)
		AliasedServiceEmail = db.aliased(UserEmail)
		AliasedService = db.aliased(Service)
		aliased_user_groups = db.aliased(user_groups)

		query = query.join(cls.user.of_type(AliasedUser))
		query = query.join(AliasedUser.primary_email.of_type(AliasedPrimaryEmail))
		query = query.outerjoin(cls.service_email.of_type(AliasedServiceEmail))
		query = query.join(cls.service.of_type(AliasedService))

		remailer_enabled = db.case(
			whens=[
				(db.not_(remailer.configured), False),
				(
					db.not_(AliasedUser.loginname.in_(current_app.config['REMAILER_LIMIT_TO_USERS']))
						if current_app.config['REMAILER_LIMIT_TO_USERS'] is not None else db.and_(False),
					False
				),
				(cls.remailer_overwrite_mode != None, cls.remailer_overwrite_mode != RemailerMode.DISABLED)
			],
			else_=(AliasedService.remailer_mode != RemailerMode.DISABLED)
		)
		has_access = db.or_(
			db.not_(AliasedService.limit_access),
			db.exists().where(db.and_(
				aliased_user_groups.c.user_id == AliasedUser.id,
				aliased_user_groups.c.group_id == AliasedService.access_group_id,
			))
		)
		has_email_preferences = db.and_(
			has_access,
			AliasedService.enable_email_preferences,
		)
		real_email_matches = db.case(
			whens=[
				# pylint: disable=singleton-comparison
				(db.and_(has_email_preferences, cls.service_email != None), AliasedServiceEmail.address == email),
			],
			else_=(AliasedPrimaryEmail.address == email)
		)
		return query.filter(db.and_(db.not_(remailer_enabled), real_email_matches))

@db.event.listens_for(db.Session, 'after_flush') # pylint: disable=no-member
def mark_service_users_changed(session, flush_context): # pylint: disable=unused-argument
	user_ids = set()
	service_ids = set()
	for obj in session.dirty:
		if isinstance(obj, User):
			user_ids.add(obj.id)
		# We modify ServiceUser during the sync API call, so if we want to react
		# to ServiceUser changes, we must be more selective
		#elif isinstance(obj, ServiceUser):
		#	user_ids.add(obj.user_id)
		elif isinstance(obj, Service):
			service_ids.add(obj.id)
	ServiceUser.query.filter(db.or_(
		ServiceUser.service_id.in_(service_ids),
		ServiceUser.user_id.in_(user_ids),
	)).update(dict(
		needs_sync=True,
		sync_token=None,
	), synchronize_session=False)

@db.event.listens_for(db.Session, 'after_flush') # pylint: disable=no-member
def create_service_users(session, flush_context): # pylint: disable=unused-argument
	# pylint completely fails to understand SQLAlchemy's query functions
	# pylint: disable=no-member
	new_user_ids = [user.id for user in session.new if isinstance(user, User)]
	new_service_ids = [service.id for service in session.new if isinstance(service, Service)]
	if not new_user_ids and not new_service_ids:
		return
	db.session.execute(db.insert(ServiceUser).from_select(
		['service_id', 'user_id'],
		db.select([Service.id, User.id]).where(db.or_(
			Service.id.in_(new_service_ids),
			User.id.in_(new_user_ids),
		))
	))

# On databases with write concurrency (i.e. everything but SQLite), the
# after_flush handler above is racy. So in rare cases ServiceUser objects
# might be missing.
@cleanup_task.handler
def create_missing_service_users():
	# pylint completely fails to understand SQLAlchemy's query functions
	# pylint: disable=no-member
	db.session.execute(db.insert(ServiceUser).from_select(
		['service_id', 'user_id'],
		db.select([Service.id, User.id]).where(db.not_(
			ServiceUser.query.filter(
				ServiceUser.service_id == Service.id,
				ServiceUser.user_id == User.id
			).exists()
		))
	))

# The user-visible services show on the service overview page are read from
# the SERVICES config key. It is planned to gradually extend the Service model
# in order to finally replace the config-defined services.

def get_language_specific(data, field_name, default =''):
	return data.get(field_name + '_' + get_locale().language, data.get(field_name, default))

# pylint: disable=too-many-branches
def get_services(user=None):
	if not user and not current_app.config['SERVICES_PUBLIC']:
		return []
	services = []
	for service_data in current_app.config['SERVICES']:
		service_title = get_language_specific(service_data, 'title')
		if not service_title:
			continue
		service_description = get_language_specific(service_data, 'description')
		service = {
			'title': service_title,
			'subtitle': service_data.get('subtitle', ''),
			'description': service_description,
			'url': service_data.get('url', ''),
			'logo_url': service_data.get('logo_url', ''),
			'has_access': True,
			'permission': '',
			'groups': [],
			'infos': [],
			'links': [],
		}
		if service_data.get('required_group'):
			if not user or not user.has_permission(service_data['required_group']):
				service['has_access'] = False
		for permission_data in service_data.get('permission_levels', []):
			if permission_data.get('required_group'):
				if not user or not user.has_permission(permission_data['required_group']):
					continue
			if not permission_data.get('name'):
				continue
			service['has_access'] = True
			service['permission'] = permission_data['name']
		if service_data.get('confidential', False) and not service['has_access']:
			continue
		for group_data in service_data.get('groups', []):
			if group_data.get('required_group'):
				if not user or not user.has_permission(group_data['required_group']):
					continue
			if not group_data.get('name'):
				continue
			service['groups'].append(group_data)
		for info_data in service_data.get('infos', []):
			if info_data.get('required_group'):
				if not user or not user.has_permission(info_data['required_group']):
					continue
			info_title = get_language_specific(info_data, 'title')
			info_html = get_language_specific(info_data, 'html')
			if not info_title or not info_html:
				continue
			info_button_text = get_language_specific(info_data, 'button_text', info_title)
			info = {
				'title': info_title,
				'button_text': info_button_text,
				'html': info_html,
				'id': '%d-%d'%(len(services), len(service['infos'])),
			}
			service['infos'].append(info)
		for link_data in service_data.get('links', []):
			if link_data.get('required_group'):
				if not user or not user.has_permission(link_data['required_group']):
					continue
			if not link_data.get('url') or not link_data.get('title'):
				continue
			service['links'].append(link_data)
		services.append(service)
	return services
