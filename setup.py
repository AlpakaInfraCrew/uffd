from setuptools import setup, find_packages
import os

with open('README.md', 'r', encoding='utf-8') as f:
	long_description = f.read()
	long_description = '**DO NOT INSTALL FROM PIP FOR PRODUCTION DEPLOYMENTS**, see [Deployment](#Deployment) for more information.\n\n\n\n' + long_description

setup(
	name='uffd',
	version=os.environ.get('PACKAGE_VERSION', 'local'),
	description='Web-based user management and single sign-on software',
	long_description=long_description,
	long_description_content_type='text/markdown',
	url='https://git.cccv.de/uffd/uffd',
	classifiers=[
		'Programming Language :: Python :: 3',
		'Development Status :: 5 - Production/Stable',
		'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
		'Operating System :: OS Independent',
		'Topic :: System :: Systems Administration :: Authentication/Directory :: LDAP',
		'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
		'Environment :: Web Environment',
		'Framework :: Flask',
	],
	author='CCCV',
	author_email='it@cccv.de',
	license='AGPL3',
	packages=['uffd'],
	include_package_data=True,
	zip_safe=False,
	python_requires='>=3.11',
	install_requires=[
		# Versions Debian Bookworm packages are based on.
		# DO NOT USE FOR PRODUCTION, those in the setup.py are not updated regularly
		'flask==2.2.2',
		'Flask-SQLAlchemy==3.0.3',
		'qrcode==7.4.2',
		'fido2==0.9.1',
		'cryptography==38.0.4',
		'pyjwt==2.6.0',
		'Flask-Migrate==4.0.4',
		'Flask-Babel==2.0.0',
		'argon2-cffi==21.1.0',
		'itsdangerous==2.1.2',
		'prometheus-client==0.16.0',
		'ua-parser==0.16.1',

		# The main dependencies on their own lead to version collisions and pip is
		# not very good at resolving them, so we pin the versions from Debian Bookworm
		# for all dependencies.
		'alembic==1.9.0', # Bookworm ships 1.8.1, but flask-migrate 4.0.4 depends on alembic>=1.9.0
		'cffi',
		'click==8.1.3',
		'Jinja2==3.1.2',
		'MarkupSafe==2.1.2',
		'pycparser==2.21',
		'six==1.12.0',
		'SQLAlchemy==1.4.46',
		'Werkzeug==2.2.2',
		'Mako==1.2.4',
		'Babel==2.10.3',
		'pytz==2022.7.1',
		'typing-extensions==4.4.0',
		'pypng==0.20220715.0',
		'greenlet==3.1.0', # Bookworm ships 2.0.2, but this does not build on Trixie
	],
)
