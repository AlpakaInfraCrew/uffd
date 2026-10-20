from flask import redirect, url_for, request, render_template
from werkzeug.exceptions import Forbidden

from uffd.secure_redirect import secure_local_redirect

from . import session, selfservice, signup, oauth2, user, group, service, role, invite, api, rolemod

def init_app(app):
	@app.errorhandler(403)
	def handle_403(error):
		return render_template('403.html', description=error.description if error.description != Forbidden.description else None), 403

	@app.route("/")
	def index(): #pylint: disable=unused-variable
		if app.config['DEFAULT_PAGE_SERVICES']:
			return redirect(url_for('service.overview'))
		return redirect(url_for('selfservice.index'))

	@app.route('/lang', methods=['POST'])
	def setlang(): #pylint: disable=unused-variable
		resp = secure_local_redirect(request.values.get('ref', '/'))
		if 'lang' in request.values:
			resp.set_cookie('language', request.values['lang'])
		return resp

	app.register_blueprint(session.bp)
	app.register_blueprint(selfservice.bp)
	app.register_blueprint(signup.bp)
	app.register_blueprint(oauth2.bp)
	app.register_blueprint(user.bp)
	app.register_blueprint(group.bp)
	app.register_blueprint(service.bp)
	app.register_blueprint(role.bp)
	app.register_blueprint(invite.bp)
	app.register_blueprint(api.bp)
	app.register_blueprint(rolemod.bp)

	app.add_url_rule("/metrics", view_func=api.prometheus_metrics)
