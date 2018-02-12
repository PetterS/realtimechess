import base64
import hashlib
import logging
import math
import os
import re

import aiohttp

# If set to True, will allow @debug_authenticated methods and
# will overwrite users on anonymous requests.
IS_UNSAFE_DEBUG = False

SECRET_KEY = os.environ.get('SECRET_KEY')
if SECRET_KEY:
	SECRET_KEY = SECRET_KEY.encode('utf-8')
else:
	SECRET_KEY = b"Chess secret key that no one knows."

users = {}


class User:
	def __init__(self, name, password):
		self.id = name + "@anon.com"
		self.name = name
		self.password = password
		self.rating = 1000
		self.wins = 0
		self.losses = 0

	def to_dict(self):
		result = {}
		for attr in dir(self):
			if attr != "user" and not callable(getattr(
			    self, attr)) and not attr.startswith("_"):
				result[attr] = getattr(self, attr)
		return result

	def __str__(self):
		return self.id

	def __eq__(self, other):
		return self.id == other.id


def change_ratings(winner, loser):
	# http://en.wikipedia.org/wiki/Elo_rating_system#Mathematical_details
	diff = loser.rating - winner.rating
	EA = 1.0 / (1 + math.pow(10, diff / 400.0))
	score = 1.0
	delta = int(round(32.0 * (score - EA)))
	winner.rating += delta
	loser.rating -= delta
	winner.wins += 1
	loser.losses += 1


def _password(name):
	sha256 = hashlib.sha256()
	sha256.update(name.encode("utf-8"))
	sha256.update(SECRET_KEY)
	return base64.b64encode(sha256.digest()).decode("ascii")


def get_current_user(request):
	name = request.cookies.get("name")
	if name is None:
		return None

	p = request.cookies.get("password")
	if p == _password(name):
		return users.get(name, None)
	else:
		logging.info("Incorrect password for %s.", name)
		return None


def authenticated(handler):
	def call_handler_if_ok(request):
		user = get_current_user(request)
		if user is None:
			raise aiohttp.web.HTTPForbidden(text="Not logged in.")
		return handler(request)

	return call_handler_if_ok


def debug_authenticated(handler):
	def call_handler_if_ok(request):
		if not IS_UNSAFE_DEBUG:
			raise aiohttp.web.HTTPForbidden(text="No debug allowed.")
		return handler(request)

	return call_handler_if_ok


async def anonymous_login_handler(request):
	data = await request.post()
	logging.info("LOGIN %s", data)
	name = data.get('name', None)
	if name is None:
		raise aiohttp.web.HTTPBadRequest(text="Need name.")
	destination = data.get("destination", None)
	if destination is None:
		destination = "/"

	# Require A-Z for now.
	if len(name) > 20 or re.match("^[a-zA-Z0-9_-]+$", name) is None:
		raise aiohttp.web.HTTPBadRequest(text="Invalid name.")

	if name in users and not IS_UNSAFE_DEBUG:
		raise aiohttp.web.HTTPUnauthorized(text="User already exists.")
	users[name] = User(name, _password(name))

	logging.info("Anonymous user: %s.", name)

	response = aiohttp.web.HTTPFound(destination)
	response.set_cookie('name', name, expires=None, path='/')
	response.set_cookie('password', _password(name), expires=None, path='/')
	return response


class TopPlayers:
	def __init__(self, limit=4):
		top_players = list(users.values())
		top_players.sort(key=lambda u: u.rating, reverse=True)

		self.top_list = []
		for user in top_players[:limit]:
			self.top_list.append((user.name, user.rating))

	def html(self):
		text = ""
		for name, rating in self.top_list:
			text += """<tr><td>%s</td><td>%s</td></tr>\n""" % (name, rating)
		return text
