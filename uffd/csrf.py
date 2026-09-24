from functools import wraps

from flask import Blueprint, request, session

bp = Blueprint("csrf", __name__)

csrf_endpoints = []

def csrf_protect(blueprint=None, endpoint=None):
	def wraper(func):
		urlendpoint = endpoint
		if not urlendpoint:
			if blueprint:
				urlendpoint = "{}.{}".format(blueprint.name, func.__name__)
			else:
				urlendpoint = func.__name__
		csrf_endpoints.append(urlendpoint)
		@wraps(func)
		def decorator(*args, **kwargs):
			if '_csrf_token' in request.values:
				token = request.values['_csrf_token']
			elif request.get_json() and ('_csrf_token' in request.get_json()):
				token = request.get_json()['_csrf_token']
			else:
				token = None
			if ('_csrf_token' not in session) or (session['_csrf_token'] != token) or not token:
				return 'csrf test failed', 403
			return func(*args, **kwargs)
		return decorator
	return wraper

@bp.app_url_defaults
def csrf_inject(endpoint, values):
	if endpoint not in csrf_endpoints or not session.get('_csrf_token'):
		return
	values['_csrf_token'] = session['_csrf_token']
