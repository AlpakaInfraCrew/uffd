import os
import secrets
import sys

from flask import Flask, redirect, url_for, request, render_template
from flask_babel import Babel
from werkzeug.routing import IntegerConverter
from werkzeug.serving import make_ssl_devcert
try:
	from werkzeug.middleware.profiler import ProfilerMiddleware
except ImportError:
	from werkzeug.contrib.profiler import ProfilerMiddleware
from werkzeug.exceptions import InternalServerError, Forbidden
from flask_migrate import Migrate

from uffd.database import db, SQLAlchemyJSON
from uffd.template_helper import register_template_helper
from uffd.navbar import setup_navbar
from uffd.secure_redirect import secure_local_redirect
from uffd import user, selfservice, role, mail, session, csrf, mfa, oauth2, services, signup, rolemod, invite, api
from uffd.user.models import User, Group
from uffd.role.models import Role, RoleGroup
from uffd.mail.models import Mail

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

def init_config(app: Flask, test_config):
	# set development default config values
	app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(app.instance_path, 'uffd.sqlit3')}"
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
	# Prior to v1.1 login required ACL_SELFSERVICE_GROUP and ACL_ACCESS_GROUP did not exist
	app.config.setdefault('ACL_ACCESS_GROUP', app.config['ACL_SELFSERVICE_GROUP'])

	if "UFFD_SECRET_KEY" in os.environ:
		app.config["SECRET_KEY"] = os.environ["UFFD_SECRET_KEY"]

	if app.env == "production" and app.secret_key is None:
		raise Exception("SECRET_KEY not configured and we are running in production mode!")
	app.config.setdefault("SECRET_KEY", secrets.token_hex(128))

def create_app(test_config=None): # pylint: disable=too-many-locals,too-many-statements
	# create and configure the app
	app = Flask(__name__, instance_relative_config=False)
	app.json_encoder = SQLAlchemyJSON

	init_config(app, test_config)

	register_template_helper(app)

	# Sort the navbar positions by their blueprint names (from the left)
	positions = ["selfservice", "services", "rolemod", "invite", "user", "group", "role", "mail"]
	setup_navbar(app, positions)

	# We never want to fail here, but at a file access that doesn't work.
	# We might only have read access to app.instance_path
	try:
		os.makedirs(app.instance_path, exist_ok=True)
	except: # pylint: disable=bare-except
		pass

	db.init_app(app)
	Migrate(app, db, render_as_batch=True, directory=os.path.join(app.root_path, 'migrations'))

	for i in user.bp + selfservice.bp + role.bp + mail.bp + session.bp + csrf.bp + mfa.bp + oauth2.bp + services.bp + rolemod.bp + api.bp:
		app.register_blueprint(i)

	if app.config['ENABLE_INVITE'] or app.config['SELF_SIGNUP']:
		for i in signup.bp:
			app.register_blueprint(i)
	if app.config['ENABLE_INVITE']:
		for i in invite.bp:
			app.register_blueprint(i)

	@app.shell_context_processor
	def push_request_context(): #pylint: disable=unused-variable
		app.test_request_context().push() # LDAP ORM requires request context
		return {'db': db, 'User': User, 'Group': Group, 'Role': Role, 'Mail': Mail}

	@app.errorhandler(403)
	def handle_403(error):
		return render_template('403.html', description=error.description if error.description != Forbidden.description else None), 403

	@app.route("/")
	def index(): #pylint: disable=unused-variable
		return redirect(url_for('selfservice.index'))

	@app.route('/lang', methods=['POST'])
	def setlang(): #pylint: disable=unused-variable
		resp = secure_local_redirect(request.values.get('ref', '/'))
		if 'lang' in request.values:
			resp.set_cookie('language', request.values['lang'])
		return resp

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
