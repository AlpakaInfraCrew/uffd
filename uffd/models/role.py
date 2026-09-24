from sqlalchemy import Column, String, Integer, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import MappedCollection, collection

from uffd.database import db
from .user import User

class RoleGroup(db.Model):
	__tablename__ = 'role_groups'
	role_id = Column(Integer(), ForeignKey('role.id', onupdate='CASCADE', ondelete='CASCADE'), primary_key=True)
	role = relationship('Role', back_populates='groups')
	group_id = Column(Integer(), ForeignKey('group.id', onupdate='CASCADE', ondelete='CASCADE'), primary_key=True)
	group = relationship('Group')
	requires_mfa = Column(Boolean(create_constraint=True), default=False, nullable=False)

# pylint: disable=E1101
role_members = db.Table('role_members',
	db.Column('role_id', db.Integer(), db.ForeignKey('role.id', onupdate='CASCADE', ondelete='CASCADE'), primary_key=True),
	db.Column('user_id', db.Integer(), db.ForeignKey('user.id', onupdate='CASCADE', ondelete='CASCADE'), primary_key=True)
)

# pylint: disable=E1101
role_inclusion = db.Table('role-inclusion',
	Column('role_id', Integer, ForeignKey('role.id', onupdate='CASCADE', ondelete='CASCADE'), primary_key=True),
	Column('included_role_id', Integer, ForeignKey('role.id', onupdate='CASCADE', ondelete='CASCADE'), primary_key=True)
)

def flatten_recursive(objs, attr):
	'''Returns a set of objects and all objects included in object.`attr` recursively while avoiding loops'''
	objs = set(objs)
	new_objs = set(objs)
	while new_objs:
		for obj in getattr(new_objs.pop(), attr):
			if obj not in objs:
				objs.add(obj)
				new_objs.add(obj)
	return objs

def get_user_roles_effective(user):
	base = set(user.roles)
	if not user.is_service_user:
		base.update(Role.query.filter_by(is_default=True))
	return flatten_recursive(base, 'included_roles')

User.roles_effective = property(get_user_roles_effective)

def compute_user_groups(user, ignore_mfa=False):
	groups = set()
	for role in user.roles_effective:
		for group in role.groups:
			if ignore_mfa or not role.groups[group].requires_mfa or user.mfa_enabled:
				groups.add(group)
	return groups

User.compute_groups = compute_user_groups

def update_user_groups(user):
	current_groups = set(user.groups)
	groups = user.compute_groups()
	if groups == current_groups:
		return set(), set()
	groups_added = groups - current_groups
	groups_removed = current_groups - groups
	for group in groups_removed:
		user.groups.remove(group)
	for group in groups_added:
		user.groups.append(group)
	return groups_added, groups_removed

User.update_groups = update_user_groups

class RoleGroupMap(MappedCollection):
	def __init__(self):
		super().__init__(keyfunc=lambda rolegroup: rolegroup.group)

	@collection.internally_instrumented
	def __setitem__(self, key, value, _sa_initiator=None):
		value.group = key
		super().__setitem__(key, value, _sa_initiator)

class Role(db.Model):
	__tablename__ = 'role'
	id = Column(Integer(), primary_key=True, autoincrement=True)
	name = Column(String(32), unique=True, nullable=False)
	description = Column(Text(), default='', nullable=False)
	included_roles = relationship('Role', secondary=role_inclusion,
	                               primaryjoin=id == role_inclusion.c.role_id,
	                               secondaryjoin=id == role_inclusion.c.included_role_id,
																 backref='including_roles')

	moderator_group_id = Column(Integer(), ForeignKey('group.id', onupdate='CASCADE', ondelete='SET NULL'), nullable=True)
	moderator_group = relationship('Group')

	members = relationship('User', secondary='role_members', back_populates='roles')

	groups = relationship('RoleGroup', collection_class=RoleGroupMap, cascade='all, delete-orphan', back_populates='role')

	# Roles that are managed externally (e.g. by Ansible) can be locked to
	# prevent accidental editing of name, moderator group, included roles
	# and groups as well as deletion in the web interface.
	locked = Column(Boolean(create_constraint=True), default=False, nullable=False)

	is_default = Column(Boolean(create_constraint=True), default=False, nullable=False)

	@property
	def members_effective(self):
		members = set()
		for role in flatten_recursive([self], 'including_roles'):
			members.update(role.members)
			if role.is_default:
				members.update([user for user in User.query.all() if not user.is_service_user])
		return members

	@property
	def included_roles_recursive(self):
		return flatten_recursive(self.included_roles, 'included_roles')

	@property
	def groups_effective(self):
		groups = set(self.groups)
		for role in self.included_roles_recursive:
			groups.update(role.groups)
		return groups

	def update_member_groups(self):
		for user in self.members_effective:
			user.update_groups()
