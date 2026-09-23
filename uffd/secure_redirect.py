import re

from flask import redirect

def secure_local_redirect(target):
	# Only accept local and absolute URLs
	if not re.match('^/[a-zA-Z0-9]', target):
		target = '/'
	return redirect(target)
