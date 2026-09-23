from uffd.secure_redirect import secure_local_redirect

from tests.utils import UffdTestCase

class TestSecureRedirect(UffdTestCase):
	def test_valid(self):
		self.assertEqual(secure_local_redirect('/').location, '/')
		self.assertEqual(secure_local_redirect('/foo/bar?foo=bar').location, '/foo/bar?foo=bar')

	def test_invalid(self):
		self.assertEqual(secure_local_redirect('example.com/foo').location, '/')
		self.assertEqual(secure_local_redirect('https://example.com/foo').location, '/')
		self.assertEqual(secure_local_redirect('https%3A%2F%2Fexample.com/foo').location, '/')
		self.assertEqual(secure_local_redirect('//example.com/foo').location, '/')
		self.assertEqual(secure_local_redirect('/\\example.com/foo').location, '/')
		self.assertEqual(secure_local_redirect('/%2Fexample.com/foo').location, '/')
