import base64
import hashlib
import logging
import math
import os
import re

import aiohttp

SECRET_KEY = os.environ.get('SECRET_KEY')
if SECRET_KEY:
	SECRET_KEY = SECRET_KEY.encode('utf-8')
else:
	SECRET_KEY = b"Chess secret key that no one knows."

LONG_TIME_IN_SECONDS = 10 * 365 * 24 * 60 * 60


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


class UserManager:
	def __init__(self, unsafe_debug=False):
		self._users = {}
		# If set to True, will allow @debug_authenticated methods and
		# will overwrite users on anonymous requests.
		self.unsafe_debug = unsafe_debug

	def get_current_user(self, request):
		name = request.cookies.get("name")
		if name is None:
			return None

		p = request.cookies.get("password")
		if p == self._password(name):
			user = self._users.get(name, None)
			if user is None:
				# Valid login, but we do not know this user. Must have
				# forgotten about them. Better create the user and
				# pretend it didn't happen.
				user = User(name, self._password(name))
				self._users[name] = user
				logging.warning("User %s logged in but not found. Recreated.",
				                name)
			return user
		else:
			logging.error("Incorrect password for %s.", name)
			return None

	def login(self, name):
		if name in self._users and not self.unsafe_debug:
			raise aiohttp.web.HTTPUnauthorized(text="User already exists.")
		password = self._password(name)
		self._users[name] = User(name, password)
		return password

	def top_players_html(self, limit=4):
		top_players = list(self._users.values())
		top_players.sort(key=lambda u: u.rating, reverse=True)

		self.top_list = []
		for user in top_players[:limit]:
			self.top_list.append((user.name, user.rating))

		text = ""
		for name, rating in self.top_list:
			text += """<tr><td>%s</td><td>%s</td></tr>\n""" % (name, rating)
		return text

	def _password(self, name):
		sha256 = hashlib.sha256()
		sha256.update(name.encode("utf-8"))
		sha256.update(SECRET_KEY)
		return base64.b64encode(sha256.digest()).decode("ascii")


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


def authenticated(handler):
	def call_handler_if_ok(request):
		manager = request.app["user_manager"]
		user = manager.get_current_user(request)
		if user is None:
			raise aiohttp.web.HTTPForbidden(text="Not logged in.")
		return handler(request)

	return call_handler_if_ok


def debug_authenticated(handler):
	def call_handler_if_ok(request):
		manager = request.app["user_manager"]
		if not manager.unsafe_debug:
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
	if len(name) > 20 or re.match(r"^[\sa-zA-Z0-9_-]+$", name) is None:
		raise aiohttp.web.HTTPBadRequest(text="Invalid name.")

	manager = request.app["user_manager"]
	password = manager.login(name)
	logging.info("Anonymous user: %s.", name)

	response = aiohttp.web.HTTPFound(destination)
	response.set_cookie('name', name, max_age=LONG_TIME_IN_SECONDS, path='/')
	response.set_cookie(
	    'password', password, max_age=LONG_TIME_IN_SECONDS, path='/')
	return response
