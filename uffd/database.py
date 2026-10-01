import uuid

from sqlalchemy import MetaData, event
from sqlalchemy.types import TypeDecorator, Text, CHAR
from sqlalchemy.ext.mutable import MutableList
from flask_sqlalchemy import SQLAlchemy

convention = {
	'ix': 'ix_%(column_0_label)s',
	'uq': 'uq_%(table_name)s_%(column_0_name)s',
	'ck': 'ck_%(table_name)s_%(column_0_name)s',
	'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
	'pk': 'pk_%(table_name)s'
}
metadata = MetaData(naming_convention=convention)

db = SQLAlchemy(metadata=metadata)

def enable_sqlite_foreign_key_support(dbapi_connection, connection_record):
	# pylint: disable=unused-argument
	cursor = dbapi_connection.cursor()
	cursor.execute('PRAGMA foreign_keys=ON')
	cursor.close()

# We want to enable SQLite foreign key support for app and test code, but not
# for migrations.
# The common way to add the handler to the Engine class (so it applies to all
# instances) would also affect the migrations. With flask_sqlalchemy v2.4 and
# newer we could overwrite SQLAlchemy.create_engine and add our handler there.
# However Debian Buster and Bullseye ship v2.1, so we do this here and call
# this function in create_app.
def customize_db_engine(engine):
	if engine.name == 'sqlite':
		event.listen(engine, 'connect', enable_sqlite_foreign_key_support)
	elif engine.name in ('mysql', 'mariadb'):
		@event.listens_for(engine, 'connect')
		def receive_connect(dbapi_connection, connection_record): # pylint: disable=unused-argument
			cursor = dbapi_connection.cursor()
			cursor.execute('SHOW VARIABLES LIKE "character_set_connection"')
			character_set_connection = cursor.fetchone()[1]
			if character_set_connection != 'utf8mb4':
				raise Exception(f'Unsupported connection charset "{character_set_connection}". Make sure to add "?charset=utf8mb4" to SQLALCHEMY_DATABASE_URI!')
			cursor.execute('SHOW VARIABLES LIKE "collation_database"')
			collation_database  = cursor.fetchone()[1]
			if collation_database != 'utf8mb4_nopad_bin':
				raise Exception(f'Unsupported database collation "{collation_database}". Create the database with "CHARACTER SET utf8mb4 COLLATE utf8mb4_nopad_bin"!')
			cursor.execute('SET NAMES utf8mb4 COLLATE utf8mb4_nopad_bin')
			cursor.close()

class CommaSeparatedList(TypeDecorator):
	# For some reason TypeDecorator.process_literal_param and
	# TypeEngine.python_type are abstract but not actually required
	# pylint: disable=abstract-method

	impl = Text
	cache_ok = True

	def process_bind_param(self, value, dialect):
		if value is None:
			return None
		for item in value:
			if ',' in item:
				raise ValueError('Items of comma-separated list must not contain commas')
		return ','.join(value)

	def process_result_value(self, value, dialect):
		if value is None:
			return None
		return MutableList(value.split(','))

class Uuid(TypeDecorator):
	# Identical to Uuid type in SQLAlchemy 2 on SQLite and MariaDB. When we drop Debian Bookworm
	# support, we  can replace this with the built-in Uuid type (maybe with native_uuid=False).
	# pylint: disable=abstract-method

	impl = CHAR(32)
	cache_ok = True

	def process_bind_param(self, value, dialect):
		if value is None:
			return None
		return str(value).lower().replace('-', '')

	def process_result_value(self, value, dialect):
		if value is None:
			return None
		return uuid.UUID(value)
