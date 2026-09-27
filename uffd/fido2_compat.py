# pylint: skip-file

from flask_babel import gettext as _
from warnings import warn
from flask import request, current_app
import urllib.parse


# WebAuthn support is optional because fido2 has a pretty unstable
# interface and might be difficult to install with the correct version

try:
	import fido2 as __fido2

	if __fido2.__version__.startswith('0.9.'):
		from fido2.client import ClientData
		from fido2.webauthn import PublicKeyCredentialRpEntity
		from fido2.server import Fido2Server
		from fido2.ctap2 import AttestationObject, AuthenticatorData, AttestedCredentialData
		from fido2 import cbor
	elif __fido2.__version__.startswith('1.'):
		from fido2.webauthn import PublicKeyCredentialRpEntity, CollectedClientData as ClientData, AttestationObject, AuthenticatorData, AttestedCredentialData
		from fido2.server import Fido2Server
		from fido2 import cbor
	else:
		raise ImportError(f'Unsupported fido2 version: {__fido2.__version__}')

	def get_webauthn_server():
		hostname = urllib.parse.urlsplit(request.url).hostname
		return Fido2Server(PublicKeyCredentialRpEntity(id=current_app.config.get('MFA_RP_ID', hostname),
		                                               name=current_app.config['MFA_RP_NAME']))

	WEBAUTHN_SUPPORTED = True
except ImportError as err:
	warn(_('2FA WebAuthn support disabled because import of the fido2 module failed (%s)')%err)
	WEBAUTHN_SUPPORTED = False
