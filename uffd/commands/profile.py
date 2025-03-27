import os

from flask import current_app
from flask.cli import with_appcontext
import click
try:
	from werkzeug.middleware.profiler import ProfilerMiddleware
except ImportError:
	from werkzeug.contrib.profiler import ProfilerMiddleware

@click.command("profile", help='Runs app with profiler')
@with_appcontext
def profile_command(): #pylint: disable=unused-variable
	# app.run() is silently ignored if executed from commands. We really want
	# to do this, so we overwrite the check by overwriting the environment
	# variable.
	os.environ['FLASK_RUN_FROM_CLI'] = 'false'
	current_app.wsgi_app = ProfilerMiddleware(current_app.wsgi_app, restrictions=[30])
	current_app.run(debug=True, threaded=False)
