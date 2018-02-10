import aiohttp
import logging


class HttpCodeException(aiohttp.web.HTTPException):
	def __init__(self, code, *args):
		self.status_code = code
		aiohttp.web.HTTPException.__init__(self, *args)


def log_error(game, *args):
	msg = ""
	for arg in args:
		msg += str(arg) + " "
	if game is not None:
		for attr in dir(game):
			if not callable(getattr(game, attr)) and not attr.startswith("_"):
				msg += "\n" + str(attr) + " = \"" + str(getattr(game,
				                                                attr)) + "\""
	logging.error(msg)
