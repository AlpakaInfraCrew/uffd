import os
import secrets
import sys

from flask import Flask, redirect, url_for, request
from flask_babel import Babel
from werkzeug.routing import IntegerConverter
from werkzeug.serving import make_ssl_devcert
from werkzeug.contrib.profiler import ProfilerMiddleware
from werkzeug.exceptions import InternalServerError
from flask_migrate import Migrate

sys.path.append('deps/ldapalchemy')

# pylint: disable=wrong-import-position
from uffd.database import db, SQLAlchemyJSON
import uffd.ldap
from uffd.template_helper import register_template_helper
from uffd.navbar import setup_navbar
# pylint: enable=wrong-import-position

def load_config_file(app, cfg_name, silent=False):
	cfg_path = os.path.join(app.instance_path, cfg_name)
	if not os.path.exists(cfg_path):
		if not silent:
			raise Exception(f"Config file {cfg_path} not found")
		return False

	if cfg_path.endswith(".json"):
		app.config.from_json(cfg_path)
	elif cfg_path.endswith(".yaml") or cfg_path.endswith(".yml"):
		import yaml  # pylint: disable=import-outside-toplevel disable=import-error
		with open(cfg_path, encoding='utf-8') as ymlfile:
			data = yaml.safe_load(ymlfile)
		app.config.from_mapping(data)
	else:
		app.config.from_pyfile(cfg_path, silent=True)
	return True

def create_app(test_config=None): # pylint: disable=too-many-locals
	# create and configure the app
	app = Flask(__name__, instance_relative_config=False)
	app.json_encoder = SQLAlchemyJSON

	# set development default config values
	app.config.from_mapping(
		SECRET_KEY=secrets.token_hex(128),
		SQLALCHEMY_DATABASE_URI="sqlite:///{}".format(os.path.join(app.instance_path, 'uffd.sqlit3')),
	)
	app.config.from_pyfile('default_config.cfg')

	# load config
	if test_config is not None:
		app.config.from_mapping(test_config)
	elif os.environ.get("CONFIG_FILENAME"):
		load_config_file(app, os.environ["CONFIG_FILENAME"], silent=False)
	else:
		for cfg_name in ["config.cfg", "config.json", "config.yml", "config.yaml"]:
			if load_config_file(app, cfg_name, silent=True):
				break

	register_template_helper(app)
	setup_navbar(app)

	os.makedirs(app.instance_path, exist_ok=True)

	db.init_app(app)
	Migrate(app, db, render_as_batch=True)
	# pylint: disable=C0415
	from uffd import user, selfservice, role, mail, session, csrf, mfa, oauth2, services, signup, rolemod, invite, api
	# pylint: enable=C0415

	for i in user.bp + selfservice.bp + role.bp + mail.bp + session.bp + csrf.bp + mfa.bp + oauth2.bp + services.bp + rolemod.bp + api.bp:
		app.register_blueprint(i)

	if app.config['LDAP_SERVICE_USER_BIND'] and (app.config['ENABLE_INVITE'] or
												app.config['SELF_SIGNUP'] or
												app.config['ENABLE_PASSWORDRESET']):
		raise InternalServerError(description="You cannot use INVITES, SIGNUP or PASSWORDRESET when using a USER_BIND!")

	if app.config['ENABLE_INVITE'] or app.config['SELF_SIGNUP']:
		for i in signup.bp:
			app.register_blueprint(i)
	if app.config['ENABLE_INVITE']:
		for i in invite.bp:
			app.register_blueprint(i)

	@app.shell_context_processor
	def push_request_context(): #pylint: disable=unused-variable
		app.test_request_context().push() # LDAP ORM requires request context
		return {'db': db, 'ldap': uffd.ldap.ldap}

	@app.route("/")
	def index(): #pylint: disable=unused-variable
		return redirect(url_for('selfservice.index'))

	@app.route('/lang', methods=['POST'])
	def setlang(): #pylint: disable=unused-variable
		resp = redirect(request.values.get('ref', '/'))
		if 'lang' in request.values:
			resp.set_cookie('language', request.values['lang'])
		return resp

	@app.teardown_request
	def close_connection(exception): #pylint: disable=unused-variable,unused-argument
		if hasattr(request, "ldap_connection"):
			request.ldap_connection.unbind()

	@app.cli.command("gendevcert", help='Generates a self-signed TLS certificate for development')
	def gendevcert(): #pylint: disable=unused-variable
		if os.path.exists('devcert.crt') or os.path.exists('devcert.key'):
			print('Refusing to overwrite existing "devcert.crt"/"devcert.key" file!')
			return
		make_ssl_devcert('devcert')
		print('Certificate written to "devcert.crt", private key to "devcert.key".')
		print('Run `flask run --cert devcert.crt --key devcert.key` to use it.')

	@app.cli.command("profile", help='Runs app with profiler')
	def profile(): #pylint: disable=unused-variable
		# app.run() is silently ignored if executed from commands. We really want
		# to do this, so we overwrite the check by overwriting the environment
		# variable.
		os.environ['FLASK_RUN_FROM_CLI'] = 'false'
		app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30])
		app.run(debug=True)

	babel = Babel(app)

	@babel.localeselector
	def get_locale(): #pylint: disable=unused-variable
		language_cookie = request.cookies.get('language')
		if language_cookie is not None and language_cookie in app.config['LANGUAGES']:
			return language_cookie
		return request.accept_languages.best_match(list(app.config['LANGUAGES']))

	app.add_template_global(get_locale)

	return app
