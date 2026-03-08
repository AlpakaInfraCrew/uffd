from flask import current_app
from flask.cli import AppGroup
from sqlalchemy.exc import IntegrityError
import click

from uffd.database import db
from uffd.models import User, Role

user_command = AppGroup('user', help='Manage users')

# pylint: disable=too-many-arguments

def update_attrs(user, mail=None, displayname=None, password=None,
                 prompt_password=False, clear_roles=False,
                 add_role=tuple(), remove_role=tuple(), deactivate=None):
	if password is None and prompt_password:
		password = click.prompt('Password', hide_input=True, confirmation_prompt='Confirm password')
	if mail is not None and not user.set_primary_email_address(mail):
		raise click.ClickException('Invalid mail address')
	if displayname is not None and not user.set_displayname(displayname):
		raise click.ClickException('Invalid displayname')
	if password is not None and not user.set_password(password):
		raise click.ClickException('Invalid password')
	if deactivate is not None:
		user.is_deactivated = deactivate
	if clear_roles:
		user.roles.clear()
	for role_name in add_role:
		role = Role.query.filter_by(name=role_name).one_or_none()
		if role is None:
			raise click.ClickException(f'Role {role_name} not found')
		role.members.append(user)
	for role_name in remove_role:
		role = Role.query.filter_by(name=role_name).one_or_none()
		if role is None:
			raise click.ClickException(f'Role {role_name} not found')
		role.members.remove(user)
	user.update_groups()

@user_command.command(help='List login names of all users')
def list():
	with current_app.test_request_context():
		for user in User.query:
			click.echo(user.loginname)

@user_command.command(help='Show details of user')
@click.argument('loginname')
def show(loginname):
	with current_app.test_request_context():
		user = User.query.filter_by(loginname=loginname).one_or_none()
		if user is None:
			raise click.ClickException(f'User {loginname} not found')
		click.echo(f'Loginname: {user.loginname}')
		click.echo(f'Deactivated: {user.is_deactivated}')
		click.echo(f'Displayname: {user.displayname}')
		click.echo(f'Mail: {user.primary_email.address}')
		click.echo(f'Service User: {user.is_service_user}')
		click.echo(f'Roles: {", ".join([role.name for role in user.roles])}')
		click.echo(f'Groups: {", ".join([group.name for group in user.groups])}')

@user_command.command(help='Create new user')
@click.argument('loginname')
@click.option('--mail', required=True, metavar='EMAIL_ADDRESS', help='E-Mail address')
@click.option('--displayname', help='Set display name. Defaults to login name.')
@click.option('--service/--no-service', default=False, help='Create service or regular (default) user. '+\
                                                            'Regular users automatically have roles marked as default. '+\
                                                            'Service users do not.')
@click.option('--password', help='Password for SSO login. Login disabled if unset.')
@click.option('--prompt-password', is_flag=True, flag_value=True, default=False, help='Read password interactively from terminal.')
@click.option('--add-role', multiple=True, help='Add role to user. Repeat to add multiple roles.', metavar='ROLE_NAME')
@click.option('--deactivate', is_flag=True, flag_value=True, default=None, help='Deactivate account.')
def create(loginname, mail, displayname, service, password, prompt_password, add_role, deactivate):
	with current_app.test_request_context():
		if displayname is None:
			displayname = loginname
		user = User(is_service_user=service)
		if not user.set_loginname(loginname, ignore_blocklist=True):
			raise click.ClickException('Invalid loginname')
		try:
			db.session.add(user)
			update_attrs(user, mail, displayname, password, prompt_password, add_role=add_role, deactivate=deactivate)
			db.session.commit()
		except IntegrityError:
			# pylint: disable=raise-missing-from
			raise click.ClickException('Login name or e-mail address is already in use')

@user_command.command(help='Update user attributes and roles')
@click.argument('loginname')
@click.option('--mail', metavar='EMAIL_ADDRESS', help='Set e-mail address.')
@click.option('--displayname', help='Set display name.')
@click.option('--password', help='Set password for SSO login.')
@click.option('--prompt-password', is_flag=True, flag_value=True, default=False, help='Set password by reading it interactively from terminal.')
@click.option('--clear-roles', is_flag=True, flag_value=True, default=False, help='Remove all roles from user. Executed before --add-role.')
@click.option('--add-role', multiple=True, help='Add role to user. Repeat to add multiple roles.')
@click.option('--remove-role', multiple=True, help='Remove role from user. Repeat to remove multiple roles.')
@click.option('--deactivate/--activate', default=None, help='Deactivate or reactivate account.')
def update(loginname, mail, displayname, password, prompt_password, clear_roles, add_role, remove_role, deactivate):
	with current_app.test_request_context():
		user = User.query.filter_by(loginname=loginname).one_or_none()
		if user is None:
			raise click.ClickException(f'User {loginname} not found')
		try:
			update_attrs(user, mail, displayname, password, prompt_password, clear_roles, add_role, remove_role, deactivate)
			db.session.commit()
		except IntegrityError:
			# pylint: disable=raise-missing-from
			raise click.ClickException('E-mail address is already in use')

@user_command.command(help='Delete user')
@click.argument('loginname')
def delete(loginname):
	with current_app.test_request_context():
		user = User.query.filter_by(loginname=loginname).one_or_none()
		if user is None:
			raise click.ClickException(f'User {loginname} not found')
		db.session.delete(user)
		db.session.commit()
