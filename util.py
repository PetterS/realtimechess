import aiohttp


class HttpCodeException(aiohttp.web.HTTPException):
	def __init__(self, code, *args):
		self.status_code = code
		aiohttp.web.HTTPException.__init__(self, *args)
