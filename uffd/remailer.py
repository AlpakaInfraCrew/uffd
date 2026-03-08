from flask import current_app
import itsdangerous

from uffd.utils import nopad_b32decode, nopad_b32encode, nopad_urlsafe_b64decode, nopad_urlsafe_b64encode

class Remailer:
	'''The remailer feature improves user privacy by hiding real mail addresses
	from services and instead providing them with auto-generated pseudonymous
	remailer addresses. If a service sends a mail to a remailer address, the mail
	service uses an uffd API endpoint to get the real mail address and rewrites
	the remailer address with it. In case of a leak of user data from a service,
	the remailer addresses are useless for third-parties.

	Version 2 of the remailer address format is tolerant to case conversions at
	the cost of being slightly longer.'''

	@property
	def configured(self):
		return bool(current_app.config['REMAILER_DOMAIN'])

	def get_serializer(self):
		secret = current_app.config['REMAILER_SECRET_KEY'] or current_app.secret_key
		return itsdangerous.URLSafeSerializer(secret, salt='remailer_address_v1')

	def build_v1_address(self, service_id, user_id):
		payload = self.get_serializer().dumps([service_id, user_id])
		return 'v1-' + payload + '@' + current_app.config['REMAILER_DOMAIN']

	def build_v2_address(self, service_id, user_id):
		data, sign = self.get_serializer().dumps([service_id, user_id]).split('.', 1)
		data = nopad_b32encode(nopad_urlsafe_b64decode(data)).decode().lower()
		sign = nopad_b32encode(nopad_urlsafe_b64decode(sign)).decode().lower()
		payload = data + '-' + sign
		return 'v2-' + payload + '@' + current_app.config['REMAILER_DOMAIN']

	def is_remailer_domain(self, domain):
		domains = {domain.lower().strip() for domain in current_app.config['REMAILER_OLD_DOMAINS']}
		if current_app.config['REMAILER_DOMAIN']:
			domains.add(current_app.config['REMAILER_DOMAIN'].lower().strip())
		return domain.lower().strip() in domains

	def parse_v1_payload(self, payload):
		try:
			service_id, user_id = self.get_serializer().loads(payload)
		except itsdangerous.BadData:
			return None
		return (service_id, user_id)

	def parse_v2_payload(self, payload):
		data, sign = (payload.split('-', 1) + [''])[:2]
		try:
			data = nopad_urlsafe_b64encode(nopad_b32decode(data.upper())).decode()
			sign = nopad_urlsafe_b64encode(nopad_b32decode(sign.upper())).decode()
		except ValueError:
			return None
		payload = data + '.' + sign
		try:
			service_id, user_id = self.get_serializer().loads(payload)
		except itsdangerous.BadData:
			return None
		return (service_id, user_id)

	def parse_address(self, address):
		if '@' not in address:
			return None
		local_part, domain = address.rsplit('@', 1)
		if not self.is_remailer_domain(domain):
			return None
		prefix, payload = (local_part.strip().split('-', 1) + [''])[:2]
		if prefix == 'v1':
			return self.parse_v1_payload(payload)
		if prefix.lower() == 'v2':
			return self.parse_v2_payload(payload)
		return None

remailer = Remailer()
