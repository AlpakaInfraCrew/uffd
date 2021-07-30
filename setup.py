from setuptools import setup, find_packages
import os

with open('README.md', 'r', encoding='utf-8') as f:
	long_description = f.read()

setup(
	name='uffd',
	version=os.environ.get('PACKAGE_VERSION', 'local'),
	description='UserFerwaltungsFrontend: Ldap based single sign on and user management web software',
	long_description=long_description,
	long_description_content_type='text/markdown',
	url='https://git.cccv.de/uffd/uffd',
	classifiers=[
		'Programming Language :: Python :: 3',
		'Development Status :: 4 - Beta',
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
	packages=find_packages(),
	zip_safe=False,
	python_requires='>=3.7',
)
