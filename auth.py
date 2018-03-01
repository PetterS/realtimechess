import base64
import hashlib
import logging
import math
import os
import re
import sqlite3

import aiohttp

SECRET_KEY = os.environ.get('SECRET_KEY')
if SECRET_KEY:
	SECRET_KEY = SECRET_KEY.encode('utf-8')
else:
	SECRET_KEY = b"Chess secret key that no one knows."

LONG_TIME_IN_SECONDS = 10 * 365 * 24 * 60 * 60


class User:
	def __init__(self, name, rating, wins, losses):
		self.id = name + "@anon.com"
		self.name = name
		self.rating = rating
		self.wins = wins
		self.losses = losses

	def __str__(self):
		return self.id

	def __eq__(self, other):
		return self.id == other.id

	def put(self, conn):
		conn.execute("""UPDATE user
		             SET rating = ?, wins = ?, losses = ?
		             WHERE name = ?""",
		             (self.rating, self.wins, self.losses, self.name))


class UserManager:
	def __init__(self, unsafe_debug=False):
		# If set to True, will allow @debug_authenticated methods and
		# will overwrite users on anonymous requests.
		self.unsafe_debug = unsafe_debug

		if unsafe_debug:
			self.conn = sqlite3.connect(":memory:")
		else:
			self.conn = sqlite3.connect("auth.db")

		self.conn.execute("""CREATE TABLE IF NOT EXISTS
		                  user(name STRING PRIMARY KEY NOT NULL,
		                       rating INTEGER DEFAULT 1000 NOT NULL,
		                       wins INTEGER DEFAULT 0 NOT NULL,
		                       losses INTEGER DEFAULT 0 NOT NULL);""")

	def get_current_user(self, request):
		name = request.cookies.get("name")
		if name is None:
			return None

		p = request.cookies.get("password")
		if p == self._password(name):
			query = "SELECT rating, wins, losses FROM user WHERE name = ?;"
			cur = self.conn.execute(query, (name, ))
			result = cur.fetchone()
			if result is None:
				# Valid login, but we do not know this user. Must have
				# forgotten about them. Better create the user and
				# pretend it didn't happen.
				self._create_new_user(name)
				logging.warning("User %s logged in but not found. Recreated.",
				                name)
				cur = self.conn.execute(query, (name, ))
				result = cur.fetchone()
			rating, wins, losses = result
			user = User(name, rating, wins, losses)
			return user
		else:
			logging.error("Incorrect password for %s.", name)
			return None

	def login(self, name):
		exists = (self.conn.execute("SELECT 1 FROM user WHERE name=? LIMIT 1;",
		                            (name, )).fetchone())
		if exists and not self.unsafe_debug:
			raise aiohttp.web.HTTPUnauthorized(text="User already exists.")
		password = self._password(name)
		self._create_new_user(name)
		return password

	def top_players_html(self, limit=4):
		cur = self.conn.execute(
		    "SELECT name, rating FROM user ORDER BY rating DESC LIMIT ?;",
		    (limit, ))
		text = ""
		for name, rating in cur.fetchall():
			text += """<tr><td>%s</td><td>%s</td></tr>\n""" % (name, rating)
		return text

	def _create_new_user(self, name):
		# Check that the database does not grow without bounds.
		count, = self.conn.execute("SELECT COUNT(*) FROM user;").fetchone()
		if count > 10 * 1000 * 1000:
			raise aiohttp.web.HTTPInternalServerError(text="Too many users.")
		self.conn.execute("INSERT OR REPLACE INTO user(name) VALUES (?)",
		                  (name, ))
		self.conn.commit()

	def _password(self, name):
		sha256 = hashlib.sha256()
		sha256.update(name.encode("utf-8"))
		sha256.update(SECRET_KEY)
		return base64.b64encode(sha256.digest()).decode("ascii")

	def change_ratings(self, winner, loser):
		# http://en.wikipedia.org/wiki/Elo_rating_system#Mathematical_details
		diff = loser.rating - winner.rating
		EA = 1.0 / (1 + math.pow(10, diff / 400.0))
		score = 1.0
		delta = int(round(32.0 * (score - EA)))
		winner.rating += delta
		loser.rating -= delta
		winner.wins += 1
		loser.losses += 1

		winner.put(self.conn)
		loser.put(self.conn)
		self.conn.commit()


def authenticated(handler):
	async def call_handler_if_ok(request):
		manager = request.app["user_manager"]
		user = manager.get_current_user(request)
		if user is None:
			raise aiohttp.web.HTTPForbidden(text="Not logged in.")
		return await handler(request)

	return call_handler_if_ok


def debug_authenticated(handler):
	async def call_handler_if_ok(request):
		manager = request.app["user_manager"]
		if not manager.unsafe_debug:
			raise aiohttp.web.HTTPForbidden(text="No debug allowed.")
		return await handler(request)

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
	raise response
