import secrets
import math
import base64

def token_with_alphabet(alphabet, nbytes=None):
	'''Return random text token that consists of characters from `alphabet`'''
	if nbytes is None:
		nbytes = max(secrets.DEFAULT_ENTROPY, 32)
	nbytes_per_char = math.log(len(alphabet), 256)
	nchars = math.ceil(nbytes / nbytes_per_char)
	return ''.join([secrets.choice(alphabet) for _ in range(nchars)])

def token_typeable(nbytes=None):
	'''Return random text token that is easy to type (on mobile)'''
	alphabet = '123456789abcdefghkmnopqrstuvwx' # No '0ijlyz'
	return token_with_alphabet(alphabet, nbytes=nbytes)

def token_urlfriendly(nbytes=None):
	'''Return random text token that is URL safe and works around common parsing bugs'''
	alphabet = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
	return token_with_alphabet(alphabet, nbytes=nbytes)

def nopad_b32decode(value):
	if isinstance(value, bytes):
		value = value.decode()
	return base64.b32decode(value + ('=' * (-len(value) % 8)))

def nopad_b32encode(value):
	return base64.b32encode(value).rstrip(b'=')

def nopad_urlsafe_b64decode(value):
	if isinstance(value, bytes):
		value = value.decode()
	return base64.urlsafe_b64decode(value + ('=' * (-len(value) % 4)))

def nopad_urlsafe_b64encode(value):
	return base64.urlsafe_b64encode(value).rstrip(b'=')
