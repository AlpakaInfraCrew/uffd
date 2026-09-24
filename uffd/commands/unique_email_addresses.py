import click
from flask.cli import with_appcontext
from sqlalchemy.exc import IntegrityError

from uffd.database import db
from uffd.models import User, UserEmail, FeatureFlag

# pylint completely fails to understand SQLAlchemy's query functions
# pylint: disable=no-member

@click.group('unique-email-addresses', help='Enable/disable e-mail address uniqueness checks')
def unique_email_addresses_command():
	pass

@unique_email_addresses_command.command('enable')
@with_appcontext
def enable_unique_email_addresses_command():
	if FeatureFlag.unique_email_addresses:
		raise click.ClickException('Uniqueness checks for e-mail addresses are already enabled')
	query = db.select(UserEmail.address_normalized, UserEmail.user_id)\
		.group_by(UserEmail.address_normalized, UserEmail.user_id)\
		.having(db.func.count(UserEmail.id.distinct()) > 1)
	for address_normalized, user_id in db.session.execute(query).fetchall():
		user = User.query.get(user_id)
		user_emails = UserEmail.query.filter_by(address_normalized=address_normalized, user_id=user_id)
		click.echo(f'User "{user.loginname}" has the same e-mail address multiple times:', err=True)
		for user_email in user_emails:
			if user_email.verified:
				click.echo(f'- {user_email.address}', err=True)
			else:
				click.echo(f'- {user_email.address} (unverified)', err=True)
		click.echo()
	query = db.select(UserEmail.address_normalized, UserEmail.address)\
		.where(UserEmail.verified)\
		.group_by(UserEmail.address_normalized)\
		.having(db.func.count(UserEmail.id.distinct()) > 1)
	for address_normalized, address in db.session.execute(query).fetchall():
		click.echo(f'E-mail address "{address}" is used by multiple users:', err=True)
		user_emails = UserEmail.query.filter_by(address_normalized=address_normalized, verified=True)
		for user_email in user_emails:
			if user_email.address != address:
				click.echo(f'- {user_email.user.loginname} ({user_email.address})', err=True)
			else:
				click.echo(f'- {user_email.user.loginname}', err=True)
		click.echo()
	try:
		FeatureFlag.unique_email_addresses.enable()
	except IntegrityError:
		# pylint: disable=raise-missing-from
		raise click.ClickException('''Some existing e-mail addresses violate uniqueness checks

You need to fix this manually in the admin interface. Then run this command
again to continue.''')
	db.session.commit()
	click.echo('Uniqueness checks for e-mail addresses enabled')

@unique_email_addresses_command.command('disable')
@with_appcontext
def disable_unique_email_addresses_command():
	if not FeatureFlag.unique_email_addresses:
		raise click.ClickException('Uniqueness checks for e-mail addresses are already disabled')
	click.echo('''Please note that the option to disable email address uniqueness checks will
be remove in uffd v3.
''', err=True)
	FeatureFlag.unique_email_addresses.disable()
	db.session.commit()
	click.echo('Uniqueness checks for e-mail addresses disabled')
