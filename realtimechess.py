#!/usr/bin/python3

import asyncio
import cProfile
import io
import json
import logging
import os
import pstats
import signal
import sys
import urllib.parse

import aiohttp.web
from jinja2 import Template

import auth
import constants
import game_storage
import util

HTTP_PORT = 8080

index_template = Template(
    open(os.path.join(os.path.dirname(__file__), 'index.html')).read())
login_template = Template(
    open(os.path.join(os.path.dirname(__file__), 'login.html')).read())
error_template = Template(
    open(os.path.join(os.path.dirname(__file__), 'error.html')).read())

logging.getLogger().setLevel(logging.WARNING)


def user_and_game(request):
	user = auth.get_current_user(request)
	game_key = request.query.get('g')
	game = game_storage.get(game_key)
	if not user or not game:
		raise aiohttp.web.HTTPNotFound(text="No such game.")
	return user, game


def error_response(status, message):
	html = error_template.render({"status": status, "message": message})
	return aiohttp.web.Response(
	    status=status, text=html, content_type="text/html")


async def anonymous_login_handler(request):
	try:
		return await auth.anonymous_login_handler(request)
	except aiohttp.web.HTTPException as ex:
		return error_response(ex.status, ex.text)


@auth.authenticated
async def getplayer_page(request):
	user = auth.get_current_user(request)
	return aiohttp.web.Response(text=json.dumps(user.to_dict()))


async def login_page(request):
	game_key = request.query.get('g')
	if game_key is not None:
		destination = "/?g=" + str(game_key)
	else:
		destination = "/"
	template_values = {
	    'destination': destination,
	    'login_link': "",
	    'top_players': ""
	}
	return aiohttp.web.Response(
	    text=login_template.render(**template_values),
	    content_type="text/html")


async def main_page(request):
	"""Renders the main page. When this page is shown, we create a new
	channel to push asynchronous updates to the client."""
	user = auth.get_current_user(request)
	game_key = request.query.get('g')
	original_game_key = game_key

	logging.info("Main page: %s %s", user, game_key)

	if not user:
		if game_key is not None:
			return aiohttp.web.HTTPFound("/loginpage?g=" + str(game_key))
		else:
			return aiohttp.web.HTTPFound("/loginpage")

	recent_games = game_storage.RecentGamesList(user, game_key)

	if not game_key:
		game, game_key = game_storage.new(user)
		logging.info("New game from %s." + str(user))
	else:
		game = game_storage.get(game_key)
		if not game:
			return error_response(404, "Game not found")

		logging.info("Game userX: %s.", game.userX)
		logging.info("User      : %s.", user.id)
		if game.userX.id == user.id:
			# Same player tried to join.
			pass
		elif not game.userO:
			# Current user joins this game as the second player.
			game.userO = user
			game.userO.id = user.id
			logging.info("User %s joins the game.", user)
		elif (user.id != game.userO.id and user.id != game.userX.id):
			logging.info("Observer %s joined %s.", user, game.key)

	game_link = '/?g=' + game_key
	if not original_game_key:
		return aiohttp.web.HTTPFound(game_link)

	joinable_games_html = recent_games.joinable_html(game_key)
	if len(joinable_games_html) > 0:
		joinable_games_html = "Or join another available game below:<br />" + joinable_games_html
	observable_games_html = recent_games.observable_html(game_key)
	if len(observable_games_html) > 0:
		observable_games_html = "<p />Observe an existing game:<br />" + observable_games_html
	returnable_games_html = recent_games.returnable_html(game_key)
	if len(returnable_games_html) > 0:
		returnable_games_html = "<p />Return to your existing game:<br />" + returnable_games_html
	recent_games = (returnable_games_html + "\n" + joinable_games_html + "\n" +
	                observable_games_html)

	top_list = auth.TopPlayers()
	template_values = {
	    'me': user,
	    'game_key': game_key,
	    'game_link': game_link,
	    'initial_message': game.get_game_message(),
	    'recent_games': recent_games,
	    'rating': user.rating,
	    'top_players': top_list.html(),
	    'wins': user.wins,
	    'losses': user.losses
	}

	return aiohttp.web.Response(
	    text=index_template.render(**template_values),
	    content_type="text/html")


@auth.authenticated
async def error_handler(request):
	user, game = user_and_game(request)
	data = await request.post()
	logging.error("JavaScript error: %s %s %s.", user, request.query, data)
	return aiohttp.web.Response(text="OK")


@auth.authenticated
async def getstate_handler(request):
	user, game = user_and_game(request)
	json_data = game.get_game_message()
	return aiohttp.web.Response(text=json_data)


@auth.authenticated
async def move_handler(request):
	user, game = user_and_game(request)
	from_id = request.query.get('from')
	to_id = request.query.get('to')
	if from_id and to_id:
		if game.move(user, from_id, to_id):
			await game.send_update()
	else:
		raise aiohttp.web.HTTPBadRequest(text="Need from and to IDs.")
	return aiohttp.web.Response(text="OK")


async def move_websocket_handler(user, game, query):
	from_id = query.get('from')
	to_id = query.get('to')
	if from_id and to_id:
		res = False
		try:
			res = game.move(user, from_id[0], to_id[0])
		except util.HttpCodeException as ex:
			# We can not return a code because we need the socket
			# to stay open.
			pass
		if res:
			await game.send_update()


@auth.authenticated
async def newgame_handler(request):
	user, game = user_and_game(request)
	if game.state != constants.STATE_GAMEOVER:
		raise aiohttp.web.HTTPForbidden(text="Game is not finished.")

	if game.userX == user or game.userO == user:
		# Create a new game.
		oldgame = game
		game, _ = game_storage.new(user, game.key)
		# Set properties.
		game.userX = oldgame.userX
		game.userO = oldgame.userO
		game.observers = oldgame.observers
		await game.send_update()
	else:
		raise aiohttp.web.HTTPForbidden(
		    text="Modifying this game not allowed.")

	return aiohttp.web.Response(text="OK")


@auth.authenticated
async def opened_handler(request):
	user, game = user_and_game(request)
	logging.info("Opened: %s %s.", user, game.key)
	await game.send_update()
	return aiohttp.web.Response(text="OK")


@auth.authenticated
async def ping_handler(request):
	user, game = user_and_game(request)
	logging.info("Ping: %s %s", user, game.key)
	await game.send_update()

	if game.state == constants.STATE_GAMEOVER and not game.results_are_written:
		if game.winner == constants.WHITE:
			auth.change_ratings(game.userX, game.userO)
		else:
			auth.change_ratings(game.userO, game.userX)

		logging.info("White player after update %s.", game.userX)
		logging.info("Black player after update %s.", game.userO)

		game.results_are_written = True
		game.put()

	return aiohttp.web.Response(text="OK")


@auth.authenticated
async def randomize_handler(request):
	user, game = user_and_game(request)
	await request.post()
	if user == game.userX or user == game.userO:
		game.randomize()
		await game.send_update()

	return aiohttp.web.Response(text="OK")


@auth.authenticated
async def ready_handler(request):
	user, game = user_and_game(request)
	await request.post()
	ready = request.query.get("ready")
	if ready is None:
		return aiohttp.web.Response(text="OK")
	logging.info("User %s ready: %s.", user, ready)
	await game.set_ready(user.id, ready)
	return aiohttp.web.Response(text="OK")


async def websocket_handler(request):
	# Anyone can listen to updates for a game.
	key = request.query.get('g')
	game = game_storage.get(key)
	if not game:
		raise aiohttp.web.HTTPNotFound(text="Game not found.")
	user = auth.get_current_user(request)
	logging.info('Websocket connection starting')
	ws = aiohttp.web.WebSocketResponse()
	await ws.prepare(request)
	logging.info('Websocket connection ready')

	game.observers.append(ws)

	async for msg in ws:
		logging.info("Received %s over websocket.", msg)
		if msg.type == aiohttp.WSMsgType.TEXT:
			url = urllib.parse.urlparse(msg.data)
			query = urllib.parse.parse_qs(url.query)
			if user and url.path == '/move':
				await move_websocket_handler(user, game, query)
			elif url.path == '/close':
				await ws.close()
			else:
				logging.error("Invalid Websocket command: %s %s %s.", user,
				              url, query)

	logging.info('Websocket connection closed')
	return ws


@auth.debug_authenticated
async def setdebug_handler(request):
	user, game = user_and_game(request)
	data = await request.post()
	debug = data.get("debug")
	if debug is None or debug == "" or int(debug) == 1:
		game.debug_no_time = True
		logging.info("Debug mode on for game %s.", game.key)
	else:
		game.debug_no_time = False
		logging.info("Debug mode off for game %s.", game.key)
	return aiohttp.web.Response(text="OK")


def setup_loop(loop):
	app = aiohttp.web.Application()
	app.router.add_get('/', main_page)
	app.router.add_get('/getplayer', getplayer_page)
	app.router.add_get('/loginpage', login_page)
	app.router.add_static('/game',
	                      os.path.join(os.path.dirname(__file__), "game"))

	app.router.add_post('/anonymous_login', anonymous_login_handler)
	app.router.add_post('/error', error_handler)
	app.router.add_post('/getstate', getstate_handler)
	app.router.add_post('/move', move_handler)
	app.router.add_post('/newgame', newgame_handler)
	app.router.add_post('/opened', opened_handler)
	app.router.add_post('/ping', ping_handler)
	app.router.add_post('/randomize', randomize_handler)
	app.router.add_post('/ready', ready_handler)

	app.router.add_route('GET', '/websocket', websocket_handler)

	if auth.IS_UNSAFE_DEBUG:
		app.router.add_post('/setdebug', setdebug_handler)

	handler = app.make_handler(access_log=logging.getLogger())
	web_server = loop.run_until_complete(
	    loop.create_server(handler, '0.0.0.0', HTTP_PORT))

	def every_second():
		"""Useful for catching Ctrl+C on Windows."""
		loop.call_later(1.0, every_second)

	loop.call_soon(every_second)

	def stop():
		web_server.close()
		loop.run_until_complete(web_server.wait_closed())
		loop.run_until_complete(app.shutdown())
		loop.run_until_complete(handler.shutdown(1.0))
		loop.run_until_complete(app.cleanup())

	return stop


if __name__ == '__main__':
	use_profiling = False

	if len(sys.argv) < 2 or (sys.argv[1] != "run" and sys.argv[1] != "debug"):
		print("Specify", sys.argv[0], " run/debug to run.")
		sys.exit(0)
	if sys.argv[1] == "debug":
		auth.IS_UNSAFE_DEBUG = True
		logging.getLogger().setLevel(logging.INFO)
	loop = asyncio.get_event_loop()
	stop = setup_loop(loop)
	if os.name != "nt":
		loop.add_signal_handler(signal.SIGTERM, loop.stop)

	logging.info("Server started.")
	print("Server started.")
	if use_profiling:
		pr = cProfile.Profile()
		pr.enable()
	try:
		loop.run_forever()
	except KeyboardInterrupt:
		print("KeyboardInterrupt.")
		pass
	if use_profiling:
		pr.disable()
		s = io.StringIO()
		sortby = 'cumulative'
		ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
		# This file can be visualized nicely with
		#  $  gprof2dot -f pstats cProfile.log | dot -Tpdf > cProfile.pdf
		ps.dump_stats('cProfile.log')

	stop()
	loop.close()
	logging.info("Server closed.")
