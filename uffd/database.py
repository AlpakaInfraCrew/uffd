from collections import OrderedDict

from sqlalchemy import MetaData
from flask_sqlalchemy import SQLAlchemy
from flask.json import JSONEncoder

convention = {
	'ix': 'ix_%(column_0_label)s',
	'uq': 'uq_%(table_name)s_%(column_0_name)s',
	'ck': 'ck_%(table_name)s_%(column_0_name)s',
	'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
	'pk': 'pk_%(table_name)s'
}
metadata = MetaData(naming_convention=convention)

# pylint: disable=C0103
db = SQLAlchemy(metadata=metadata)
# pylint: enable=C0103

class SQLAlchemyJSON(JSONEncoder):
	def default(self, o):
		if isinstance(o, db.Model):
			result = OrderedDict()
			for key in o.__mapper__.c.keys():
				result[key] = getattr(o, key)
			return result
		return JSONEncoder.default(self, o)
