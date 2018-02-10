import aiohttp


def HttpCodeException(code, text=""):
	return aiohttp.web.Response(status=code, text=text)
