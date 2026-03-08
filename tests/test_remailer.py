from uffd.remailer import remailer

from tests.utils import UffdTestCase

USER_ID = 1234
SERVICE1_ID = 4223
SERVICE2_ID = 3242
ADDR_V1_S1 = 'v1-WzQyMjMsMTIzNF0.MeO6bHGTgIyPvvq2r3xriokLMCU@remailer.example.com'
ADDR_V1_S2 = 'v1-WzMyNDIsMTIzNF0.p2a_RkJc0oHBc9u4_S8G9METflA@remailer.example.com'
ADDR_V2_S1 = 'v2-lm2demrtfqytemzulu-ghr3u3drsoaizd567k3k67dlrkeqwmbf@remailer.example.com'
ADDR_V2_S2 = 'v2-lmztenbsfqytemzulu-u5tl6rscltjidqlt3o4p2lyg6targ7sq@remailer.example.com'

class TestRemailer(UffdTestCase):
	def test_is_remailer_domain(self):
		self.app.config['REMAILER_DOMAIN'] = 'remailer.example.com'
		self.assertTrue(remailer.is_remailer_domain('remailer.example.com'))
		self.assertTrue(remailer.is_remailer_domain('REMAILER.EXAMPLE.COM'))
		self.assertTrue(remailer.is_remailer_domain(' remailer.example.com '))
		self.assertFalse(remailer.is_remailer_domain('other.remailer.example.com'))
		self.assertFalse(remailer.is_remailer_domain('example.com'))
		self.app.config['REMAILER_OLD_DOMAINS'] = [' OTHER.remailer.example.com ']
		self.assertTrue(remailer.is_remailer_domain(' OTHER.remailer.example.com '))
		self.assertTrue(remailer.is_remailer_domain('remailer.example.com'))
		self.assertTrue(remailer.is_remailer_domain('other.remailer.example.com'))
		self.assertFalse(remailer.is_remailer_domain('example.com'))

	def test_build_v1_address(self):
		self.app.config['REMAILER_DOMAIN'] = 'remailer.example.com'
		self.assertEqual(remailer.build_v1_address(SERVICE1_ID, USER_ID), ADDR_V1_S1)
		self.assertEqual(remailer.build_v1_address(SERVICE2_ID, USER_ID), ADDR_V1_S2)
		long_addr = remailer.build_v1_address(1000, 1000000)
		self.assertLessEqual(len(long_addr.split('@')[0]), 64)
		self.assertLessEqual(len(long_addr), 256)
		self.app.config['REMAILER_OLD_DOMAINS'] = ['old.remailer.example.com']
		self.assertEqual(remailer.build_v1_address(SERVICE1_ID, USER_ID), ADDR_V1_S1)
		self.app.config['REMAILER_SECRET_KEY'] = self.app.config['SECRET_KEY']
		self.assertEqual(remailer.build_v1_address(SERVICE1_ID, USER_ID), ADDR_V1_S1)
		self.app.config['REMAILER_SECRET_KEY'] = 'REMAILER-DEBUGKEY'
		self.assertNotEqual(remailer.build_v1_address(SERVICE1_ID, USER_ID), ADDR_V1_S1)

	def test_build_v2_address(self):
		self.app.config['REMAILER_DOMAIN'] = 'remailer.example.com'
		self.assertEqual(remailer.build_v2_address(SERVICE1_ID, USER_ID), ADDR_V2_S1)
		self.assertEqual(remailer.build_v2_address(SERVICE2_ID, USER_ID), ADDR_V2_S2)
		long_addr = remailer.build_v2_address(1000, 1000000)
		self.assertLessEqual(len(long_addr.split('@')[0]), 64)
		self.assertLessEqual(len(long_addr), 256)
		self.app.config['REMAILER_OLD_DOMAINS'] = ['old.remailer.example.com']
		self.assertEqual(remailer.build_v2_address(SERVICE1_ID, USER_ID), ADDR_V2_S1)
		self.app.config['REMAILER_SECRET_KEY'] = self.app.config['SECRET_KEY']
		self.assertEqual(remailer.build_v2_address(SERVICE1_ID, USER_ID), ADDR_V2_S1)
		self.app.config['REMAILER_SECRET_KEY'] = 'REMAILER-DEBUGKEY'
		self.assertNotEqual(remailer.build_v2_address(SERVICE1_ID, USER_ID), ADDR_V2_S1)

	def test_parse_address(self):
		# REMAILER_DOMAIN behavior
		self.app.config['REMAILER_DOMAIN'] = None
		self.assertIsNone(remailer.parse_address(ADDR_V1_S2))
		self.assertIsNone(remailer.parse_address(ADDR_V2_S2))
		self.assertIsNone(remailer.parse_address('foo@example.com'))
		self.app.config['REMAILER_DOMAIN'] = 'remailer.example.com'
		self.assertEqual(remailer.parse_address(ADDR_V1_S2), (SERVICE2_ID, USER_ID))
		self.assertEqual(remailer.parse_address(ADDR_V2_S2), (SERVICE2_ID, USER_ID))
		self.assertIsNone(remailer.parse_address('foo@example.com'))
		self.assertIsNone(remailer.parse_address('foo@remailer.example.com'))
		self.assertIsNone(remailer.parse_address('v1-foo@remailer.example.com'))
		self.assertIsNone(remailer.parse_address('v2-foo@remailer.example.com'))
		self.assertIsNone(remailer.parse_address('v2-foo-bar@remailer.example.com'))
		self.app.config['REMAILER_DOMAIN'] = 'new-remailer.example.com'
		self.assertIsNone(remailer.parse_address(ADDR_V1_S2))
		self.assertIsNone(remailer.parse_address(ADDR_V2_S2))
		self.app.config['REMAILER_OLD_DOMAINS'] = ['remailer.example.com']
		self.assertEqual(remailer.parse_address(ADDR_V1_S2), (SERVICE2_ID, USER_ID))
		self.assertEqual(remailer.parse_address(ADDR_V2_S2), (SERVICE2_ID, USER_ID))
		# REMAILER_SECRET_KEY behavior
		self.app.config['REMAILER_DOMAIN'] = 'remailer.example.com'
		self.app.config['REMAILER_OLD_DOMAINS'] = []
		self.assertEqual(remailer.parse_address(ADDR_V1_S2), (SERVICE2_ID, USER_ID))
		self.assertEqual(remailer.parse_address(ADDR_V2_S2), (SERVICE2_ID, USER_ID))
		self.app.config['REMAILER_SECRET_KEY'] = self.app.config['SECRET_KEY']
		self.assertEqual(remailer.parse_address(ADDR_V1_S2), (SERVICE2_ID, USER_ID))
		self.assertEqual(remailer.parse_address(ADDR_V2_S2), (SERVICE2_ID, USER_ID))
		self.app.config['REMAILER_SECRET_KEY'] = 'REMAILER-DEBUGKEY'
		self.assertIsNone(remailer.parse_address(ADDR_V1_S2))
		self.assertIsNone(remailer.parse_address(ADDR_V2_S2))
