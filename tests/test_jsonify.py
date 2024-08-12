from flask import jsonify

from tests.utils import UffdTestCase

class TestViews(UffdTestCase):
	def test_jsonify(self):
		print(repr(jsonify({'foo': 'bar'}).data))
		print(repr(jsonify({'foo': b'bar'}).data))
		self.assertTrue(False)
