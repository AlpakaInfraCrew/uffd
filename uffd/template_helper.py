import random
import base64
from datetime import timedelta, datetime
import io

from markupsafe import Markup

import qrcode
import qrcode.image.svg

def register_template_helper(app):
	# debian ships jinja2 without this test...
	def equalto(a, b):
		return a == b

	@app.template_filter()
	def qrcode_svg(content, **attrs): #pylint: disable=unused-variable
		img = qrcode.make(content, image_factory=qrcode.image.svg.SvgPathImage, border=4)
		svg = img.get_image()
		for key, value, in attrs.items():
			svg.set(key, value)
		buf = io.BytesIO()
		img.save(buf)
		return Markup(
			buf.getvalue().decode()
			.replace('<?xml version=\'1.0\' encoding=\'UTF-8\'?>\n', '')
			.replace(' id="qr-path" ', ' ')
			.replace('<svg ', '<svg class="qrcode" ')
		)

	@app.template_filter()
	def datauri(data, mimetype='text/plain'): #pylint: disable=unused-variable
		return Markup('data:%s;base64,%s'%(mimetype, base64.b64encode(data.encode()).decode()))

	app.jinja_env.trim_blocks = True
	app.jinja_env.lstrip_blocks = True

	app.add_template_global(random.randint, name='randint')
	app.add_template_global(datetime, name='datetime')
	app.add_template_global(timedelta, name='timedelta')
	app.add_template_global(min, name='min')
	app.add_template_global(max, name='max')
	app.add_template_global(equalto, name='equalto')
