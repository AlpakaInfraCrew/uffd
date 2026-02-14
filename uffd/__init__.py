import json
import os
import secrets
import sys

from flask import Flask, redirect, url_for, request, render_template
from flask_babel import Babel
from babel.dates import LOCALTZ
from werkzeug.exceptions import Forbidden
from flask_migrate import Migrate

from .database import db, customize_db_engine
from .template_helper import register_template_helper
from .navbar import setup_navbar
from .csrf import bp as csrf_bp
from . import models, views, commands

def load_config_file(app, path, silent=False):
	if not os.path.exists(path):
		if not silent:
			raise Exception(f"Config file {path} not found")
		return False

	if path.endswith(".json"):
		app.config.from_file(path, load=json.load)
	elif path.endswith(".yaml") or path.endswith(".yml"):
		import yaml  # pylint: disable=import-outside-toplevel disable=import-error
		app.config.from_file(path, load=yaml.safe_load)
	else:
		app.config.from_pyfile(path, silent=True)
	return True

def init_config(app: Flask, test_config):
	# set development default config values
	app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(app.instance_path, 'uffd.sqlit3')}"
	app.config.from_pyfile('default_config.cfg')

	# load config
	if test_config is not None:
		app.config.from_mapping(test_config)
	elif os.environ.get('CONFIG_PATH'):
		load_config_file(app, os.environ['CONFIG_PATH'], silent=False)
	else:
		for filename in ["config.cfg", "config.json", "config.yml", "config.yaml"]:
			if load_config_file(app, os.path.join(app.instance_path, filename), silent=True):
				break

	if app.secret_key is None:
		if not app.debug:
			raise Exception("SECRET_KEY not configured and we are running in production mode!")
		app.secret_key = secrets.token_hex(128)

def create_app(test_config=None): # pylint: disable=too-many-locals,too-many-statements
	app = Flask(__name__, instance_relative_config=False)

	init_config(app, test_config)

	register_template_helper(app)

	# Sort the navbar positions by their blueprint names (from the left)
	if app.config['DEFAULT_PAGE_SERVICES']:
		positions = ["service", "selfservice"]
	else:
		positions = ["selfservice", "service"]
	positions += ["rolemod", "invite", "user", "group", "role", "mail"]
	setup_navbar(app, positions)

	app.register_blueprint(csrf_bp)

	views.init_app(app)
	commands.init_app(app)

	# We never want to fail here, but at a file access that doesn't work.
	# We might only have read access to app.instance_path
	try:
		os.makedirs(app.instance_path, exist_ok=True)
	except: # pylint: disable=bare-except
		pass

	db.init_app(app)
	Migrate(app, db, render_as_batch=True, directory=os.path.join(app.root_path, 'migrations'))
	with app.app_context():
		customize_db_engine(db.engine)

	@app.shell_context_processor
	def push_request_context(): #pylint: disable=unused-variable
		ctx = {name: getattr(models, name) for name in models.__all__}
		ctx.setdefault('db', db)
		return ctx

	# flask-babel requires pytz-style timezone objects, but in rare cases (e.g.
	# non-IANA TZ values) LOCALTZ is stdlib-style (without normalize/localize)
	if not hasattr(LOCALTZ, 'normalize'):
		LOCALTZ.normalize = lambda dt: dt
	if not hasattr(LOCALTZ, 'localize'):
		LOCALTZ.localize = lambda dt: dt.replace(tzinfo=LOCALTZ)

	app.config.setdefault('BABEL_DEFAULT_TIMEZONE', 'LOCALTZ')
	class PatchedBabel(Babel):
		@property
		def default_timezone(self):
			# Since flask-babel v3 get_babel().default_timezone would be more concise, but
			# Debian Bookworm ships flask-babel v2 and there is no functional difference
			if app.config['BABEL_DEFAULT_TIMEZONE'] == 'LOCALTZ':
				return LOCALTZ
			return super().default_timezone

	def get_locale(): #pylint: disable=unused-variable
		language_cookie = request.cookies.get('language')
		if language_cookie is not None and language_cookie in app.config['LANGUAGES']:
			return language_cookie
		return request.accept_languages.best_match(list(app.config['LANGUAGES']))

	if hasattr(PatchedBabel, 'localeselector'):
		# Support flask-babel v2 (Debian Bookworm)
		babel = PatchedBabel(app)
		babel.localeselector(get_locale)
	else:
		babel = PatchedBabel(app, locale_selector=get_locale) # pylint: disable=unexpected-keyword-arg

	app.add_template_global(get_locale)

	return app
