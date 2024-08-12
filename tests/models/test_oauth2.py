import unittest
import datetime

import jwt

from uffd.database import db
from uffd.models import OAuth2Key

from tests.utils import UffdTestCase

TEST_JWK = dict(
	id='HvOn74G7njK1GoFNe8Dta087casdWMsm06pNhOXRgJU',
	created=datetime.datetime(2023, 11, 9, 0, 21, 10),
	active=True,
	algorithm='RS256',
	private_key_jwk='''{
		"kty": "RSA",
		"key_ops": ["sign"],
		"n": "vrznqUy8Xamph6s0Z02fFMIyjwLAMio35i9DXYjXP1ZQwSZ3SsIh3m2ablMnlu8PVlnYUzoj8rXyAWND0FSfWoQQxv1rq15pllKueddLoJsv321N_NRB8beGsLrsndw8QO0q3RWqV9O3kqhlTMjgj6bquX42wLaXrPLJyfbT3zObBsToG4UxpOyly84aklJXU5wIs0cbmjbfd8Xld38BG8Oh7Ozy5b93vPpJW6rudZRxU6QYC0r9bFFLIHJWrR4bzQMLGoJ63xjPOCl4WNpOYc9B7PNgnWTLXlFd51Hw9CaT2MRWsKNCSU77f6nZkfjWa1IsQdF0I48m46qgq7bEOOl9DbThbCnpblWrctdyg6du-OvCyVmkAo1KGtANl0027pgqUI_9HBMi33y3UPQm1ALHXIyIDBZtExH3lD6MMK3XGJfUxZuIOBndK-PXm5Fed52bgLOcf-24X6aHFn-8oyDVIj9OHkKWjy7jtKdmqZc4pBdVuCaMCYzj8iERWA3H",
		"e": "AQAB",
		"d": "G7yoH5mLcZTA6ia-byCoN-zpofGvdga9AZnxPO0vsq6K_cY_O2gxuVZ3n6reAKKbuLNGCbb_D_Dffs4q8rprlfkgi3TCLzXX5Zv5HWTD7a4Y7xpxEzQ2sWo-iagVIqZVPh0pyjliqnTyUWnFmWiY0gBe9UHianHjFVZqe8E2HFOKgW3UUbQz0keg8JtJ3T9gzZrM38KWbqhOJO0VVSRAoANPTSnumfRsUCyWywrMtIfgAbQaKazqX3xkOsAF1L-iNfd6slzPvRyIQVflVDMdfKnsu-lHiKJ0DK_lg9f55T5FymgcXsq43EKBQ2H4v2dafIm-vtWx_TRZWj_msD32BEPBA-zTqh_oP1r6a3DZh4DBtWY3vzSiuhAC0erlRs-hRTX_e9ET5fUbJnmNxjnxQD9zZmwq4ujMK6KFnHct8t77Qxj3a-wDR_XyDJ4_EKYqHlcVHfxGNBSvIdjuZJkPJnVpVtfCtpyamQIR4u5oNV7fIwYe_tFnw0Y90rGoJMzB",
		"p": "-A-FnH21HJ7GPWUm9k3mxsxSchy89QEUCZZiH6EcB4ZP8wJsxrQsUSIHCR74YmZEI3Ulsum1Ql4x50k7Q2sNh9SnwKvmctjksehGy4yCrdunAqjqyz3wFwGaKWnhn3frkiqH5ATjkOoc8qHz8saa7reeVClj47ZWyy-Nl559ycLMs0rI1N_THzO07C3jSbJhyPj0yeygAflsRqqnNvEQ6ps1VLiqf9G5jfSvUUn5DyKIpep9iGo29caGSIPIy_2h",
		"q": "xNe1-QWskxOcY_GiHpFWdvzqr1o9fxg5whgpNcGi3caokw2iNHRYut4cbVvFFBlv_9B5QCl9WVfR2ADG0AtvkvUxEZqCdxEvcqjIANeRLKHDjW5kMuPS0_fcskFP-r7mCM9SBfPplfMVCF5nuNWf5LzNopWfsTChIDD1rSpPjItNYuwLXszm_3R81HHHeQLcyvoMxLCmeLy5TXX2hXOMHh2IMZCXAHopJmLJUVnQ48kr5jd2l0kLbmx3aBqdccJn",
		"dp": "MLS7g1KbcRcrzXpDADGjkn0j4wwJfgHMMWW5toQnwMJ6iDh9qzZNTVDlGMFf-9IgpuWllU-WK4XbPpJ-dGpcqcLzfT1DbmFv5g65d9YLAqASVs9b6rQqpBnIb0E-79TYCEcZj4f2NsoBDRMHly-v1BdxmwzVdCylNhgMMS0Jfcgl8T5J2KJqDcJVT9piumGwGYnoZo1zjW-v9uAjHQKQU8BN5Git8ZL4YAsfMVLY-EPLmOhF5bcVO4TTcQGPN56B",
		"dq": "HiiSl-G3rB0QE_v8g8Ruw_JCHrWrwGI8zzEWd0cApgv-3fDzzieZRKAtKNArpMW09DPDsAHrU5nx669KxqtJ3_EzIGhU3ttCMsYLRp3Af18VcADe1zEypwlNxf3dvCQtaGIjRgg13KSOr2aPa7FHOyt2MhfMjMBPn3gA3BQkdfsN0z8pCtBIABGf4ojAMBkxLOQcurH5_3uixGxzZcTrTd3mdPmbORZ-YYQ3JgCl0ZCL6kzLHaiyWKvDq66QOtK3",
		"qi": "ySqD9cUxbq3wkCsPQId_YfQLIqb5RK_JJIMjtBOdTdo4aT5tmodYCSmjBmhrYXjDWtyJdelvPfdSfgncHJhf8VgkZ8TPvUeaQwsQFBwB5llwpdb72eEEJrmG1SVwNMoFCLXdNT3ACad16cUDMnWmklH0X07OzdxGOBnGhgLZUs4RbPjLH7OpYTyQqVy2L8vofqJR42cfePZw8WQM4k0PPbhralhybExIkSCmaQyYbACZ5k0OVQErEqnj4elglA0h"
	}''',
	public_key_jwk='''{
		"kty": "RSA",
		"key_ops": ["verify"],
		"n": "vrznqUy8Xamph6s0Z02fFMIyjwLAMio35i9DXYjXP1ZQwSZ3SsIh3m2ablMnlu8PVlnYUzoj8rXyAWND0FSfWoQQxv1rq15pllKueddLoJsv321N_NRB8beGsLrsndw8QO0q3RWqV9O3kqhlTMjgj6bquX42wLaXrPLJyfbT3zObBsToG4UxpOyly84aklJXU5wIs0cbmjbfd8Xld38BG8Oh7Ozy5b93vPpJW6rudZRxU6QYC0r9bFFLIHJWrR4bzQMLGoJ63xjPOCl4WNpOYc9B7PNgnWTLXlFd51Hw9CaT2MRWsKNCSU77f6nZkfjWa1IsQdF0I48m46qgq7bEOOl9DbThbCnpblWrctdyg6du-OvCyVmkAo1KGtANl0027pgqUI_9HBMi33y3UPQm1ALHXIyIDBZtExH3lD6MMK3XGJfUxZuIOBndK-PXm5Fed52bgLOcf-24X6aHFn-8oyDVIj9OHkKWjy7jtKdmqZc4pBdVuCaMCYzj8iERWA3H",
		"e": "AQAB"
	}''',
)

class TestOAuth2Key(UffdTestCase):
	def setUp(self):
		super().setUp()
		db.session.add(OAuth2Key(**TEST_JWK))
		db.session.add(OAuth2Key(
			id='1e9gdk7',
			created=datetime.datetime(2014, 11, 8, 0, 0, 0),
			active=True,
			algorithm='RS256',
			private_key_jwk='invalid',
			public_key_jwk='''{
				"kty":"RSA",
				"n":"w7Zdfmece8iaB0kiTY8pCtiBtzbptJmP28nSWwtdjRu0f2GFpajvWE4VhfJAjEsOcwYzay7XGN0b-X84BfC8hmCTOj2b2eHT7NsZegFPKRUQzJ9wW8ipn_aDJWMGDuB1XyqT1E7DYqjUCEOD1b4FLpy_xPn6oV_TYOfQ9fZdbE5HGxJUzekuGcOKqOQ8M7wfYHhHHLxGpQVgL0apWuP2gDDOdTtpuld4D2LK1MZK99s9gaSjRHE8JDb1Z4IGhEcEyzkxswVdPndUWzfvWBBWXWxtSUvQGBRkuy1BHOa4sP6FKjWEeeF7gm7UMs2Nm2QUgNZw6xvEDGaLk4KASdIxRQ",
				"e":"AQAB"
			}'''
		))
		db.session.commit()
		self.key = OAuth2Key.query.get('HvOn74G7njK1GoFNe8Dta087casdWMsm06pNhOXRgJU')
		self.key_oidc_spec = OAuth2Key.query.get('1e9gdk7')

	def test_private_key(self):
		self.key.private_key

	def test_public_key(self):
		self.key.private_key

	def test_public_key_jwks_dict(self):
		self.assertEqual(self.key.public_key_jwks_dict, {
				"kid": "HvOn74G7njK1GoFNe8Dta087casdWMsm06pNhOXRgJU",
				"kty": "RSA",
				"alg": "RS256",
				"use": "sig",
				"n": "vrznqUy8Xamph6s0Z02fFMIyjwLAMio35i9DXYjXP1ZQwSZ3SsIh3m2ablMnlu8PVlnYUzoj8rXyAWND0FSfWoQQxv1rq15pllKueddLoJsv321N_NRB8beGsLrsndw8QO0q3RWqV9O3kqhlTMjgj6bquX42wLaXrPLJyfbT3zObBsToG4UxpOyly84aklJXU5wIs0cbmjbfd8Xld38BG8Oh7Ozy5b93vPpJW6rudZRxU6QYC0r9bFFLIHJWrR4bzQMLGoJ63xjPOCl4WNpOYc9B7PNgnWTLXlFd51Hw9CaT2MRWsKNCSU77f6nZkfjWa1IsQdF0I48m46qgq7bEOOl9DbThbCnpblWrctdyg6du-OvCyVmkAo1KGtANl0027pgqUI_9HBMi33y3UPQm1ALHXIyIDBZtExH3lD6MMK3XGJfUxZuIOBndK-PXm5Fed52bgLOcf-24X6aHFn-8oyDVIj9OHkKWjy7jtKdmqZc4pBdVuCaMCYzj8iERWA3H",
				"e": "AQAB"
		})

	def test_encode_jwt(self):
		jwt_data = self.key.encode_jwt({'aud': 'test', 'foo': 'bar'})
		self.assertIsInstance(jwt_data, str)
		self.assertEqual(
			jwt.get_unverified_header(jwt_data),
			# typ is optional, x5u/x5c/jku/jwk are discoraged by OIDC Core 1.0 spec section 2
			{'kid': self.key.id, 'alg': self.key.algorithm, 'typ': 'JWT'}
		)
		self.assertEqual(
			OAuth2Key.decode_jwt(jwt_data, audience='test'),
			{'aud': 'test', 'foo': 'bar'}
		)
		self.key.active = False
		with self.assertRaises(jwt.exceptions.InvalidKeyError):
			self.key.encode_jwt({'aud': 'test', 'foo': 'bar'})

	def test_oidc_hash(self):
		# Example from OIDC Core 1.0 spec A.3
		self.assertEqual(
			self.key.oidc_hash(b'jHkWEdUXMU1BwAsC4vtUsZwnNvTIxEl0z9K3vx5KF0Y'),
			'77QmUPtjPfzWtF2AnpK9RQ'
		)
		# Example from OIDC Core 1.0 spec A.4
		self.assertEqual(
			self.key.oidc_hash(b'Qcb0Orv1zh30vL1MPRsbm-diHiMwcLyZvn1arpZv-Jxf_11jnpEX3Tgfvk'),
			'LDktKdoQak3Pk0cnXxCltA'
		)
		# Example from OIDC Core 1.0 spec A.6
		self.assertEqual(
			self.key.oidc_hash(b'jHkWEdUXMU1BwAsC4vtUsZwnNvTIxEl0z9K3vx5KF0Y'),
			'77QmUPtjPfzWtF2AnpK9RQ'
		)
		self.assertEqual(
			self.key.oidc_hash(b'Qcb0Orv1zh30vL1MPRsbm-diHiMwcLyZvn1arpZv-Jxf_11jnpEX3Tgfvk'),
			'LDktKdoQak3Pk0cnXxCltA'
		)

	def test_decode_jwt(self):
		# Example from OIDC Core 1.0 spec A.2
		jwt_data = (
			'eyJraWQiOiIxZTlnZGs3IiwiYWxnIjoiUlMyNTYifQ.ewogImlz'
			'cyI6ICJodHRwOi8vc2VydmVyLmV4YW1wbGUuY29tIiwKICJzdWIiOiAiMjQ4'
			'Mjg5NzYxMDAxIiwKICJhdWQiOiAiczZCaGRSa3F0MyIsCiAibm9uY2UiOiAi'
			'bi0wUzZfV3pBMk1qIiwKICJleHAiOiAxMzExMjgxOTcwLAogImlhdCI6IDEz'
			'MTEyODA5NzAsCiAibmFtZSI6ICJKYW5lIERvZSIsCiAiZ2l2ZW5fbmFtZSI6'
			'ICJKYW5lIiwKICJmYW1pbHlfbmFtZSI6ICJEb2UiLAogImdlbmRlciI6ICJm'
			'ZW1hbGUiLAogImJpcnRoZGF0ZSI6ICIwMDAwLTEwLTMxIiwKICJlbWFpbCI6'
			'ICJqYW5lZG9lQGV4YW1wbGUuY29tIiwKICJwaWN0dXJlIjogImh0dHA6Ly9l'
			'eGFtcGxlLmNvbS9qYW5lZG9lL21lLmpwZyIKfQ.rHQjEmBqn9Jre0OLykYNn'
			'spA10Qql2rvx4FsD00jwlB0Sym4NzpgvPKsDjn_wMkHxcp6CilPcoKrWHcip'
			'R2iAjzLvDNAReF97zoJqq880ZD1bwY82JDauCXELVR9O6_B0w3K-E7yM2mac'
			'AAgNCUwtik6SjoSUZRcf-O5lygIyLENx882p6MtmwaL1hd6qn5RZOQ0TLrOY'
			'u0532g9Exxcm-ChymrB4xLykpDj3lUivJt63eEGGN6DH5K6o33TcxkIjNrCD'
			'4XB1CKKumZvCedgHHF3IAK4dVEDSUoGlH9z4pP_eWYNXvqQOjGs-rDaQzUHl'
			'6cQQWNiDpWOl_lxXjQEvQ'
		)
		self.assertEqual(
			OAuth2Key.decode_jwt(jwt_data, options={'verify_exp': False, 'verify_aud': False}),
			{
				"iss": "http://server.example.com",
				"sub": "248289761001",
				"aud": "s6BhdRkqt3",
				"nonce": "n-0S6_WzA2Mj",
				"exp": 1311281970,
				"iat": 1311280970,
				"name": "Jane Doe",
				"given_name": "Jane",
				"family_name": "Doe",
				"gender": "female",
				"birthdate": "0000-10-31",
				"email": "janedoe@example.com",
				"picture": "http://example.com/janedoe/me.jpg"
			}
		)
		with self.assertRaises(jwt.exceptions.InvalidKeyError):
			# {"alg":"RS256"} -> no key id
			OAuth2Key.decode_jwt('eyJhbGciOiJSUzI1NiJ9.' + jwt_data.split('.', 1)[-1])
		with self.assertRaises(jwt.exceptions.InvalidKeyError):
			# {"kid":"XXXXX","alg":"RS256"} -> unknown key id
			OAuth2Key.decode_jwt('eyJraWQiOiJYWFhYWCIsImFsZyI6IlJTMjU2In0.' + jwt_data.split('.', 1)[-1])
		OAuth2Key.query.get('1e9gdk7').active = False
		with self.assertRaises(jwt.exceptions.InvalidKeyError):
			# not active
			OAuth2Key.decode_jwt(jwt_data)

	def test_generate_rsa_key(self):
		key = OAuth2Key.generate_rsa_key()
		self.assertEqual(key.algorithm, 'RS256')
