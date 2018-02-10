#!/usr/bin/python3
# coding=utf-8
# pylint: disable-msg=C6310

import asyncio
import datetime
import json
import logging
import os
import random
import re
import time
import signal
import sys

import aiohttp.web
from jinja2 import Template

import auth
import constants
import game_storage

HTTP_PORT = 8080

index_template = Template(
    open(os.path.join(os.path.dirname(__file__), 'index.html')).read())
login_template = Template(
    open(os.path.join(os.path.dirname(__file__), 'login.html')).read())


def user_and_game(request):
	user = auth.get_current_user(request)
	game_key = request.query.get('g')
	game = game_storage.get(game_key)
	if not user or not game:
		raise aiohttp.web.HTTPNotFound(text="No such game.")
	return user, game


@auth.authenticated
async def getplayer_page(request):
	user = auth.get_current_user(request)
	return aiohttp.web.Response(text=json.dumps(user.to_dict()))


async def login_page(request):
	game_key = request.match_info.get('g')
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

	print("Main page:", user, game_key)

	if not user:
		if game_key is not None:
			return aiohttp.web.HTTPFound("/loginpage?g=" + str(game_key))
		else:
			return aiohttp.web.HTTPFound("/loginpage")

	if not game_key:
		game, game_key = game_storage.new(user)
		print("New game from " + str(user))
	else:
		game = game_storage.get(game_key)
		if not game:
			raise aiohttp.web.HTTPNotFound(text="Game not found")

		print("-- Game userX: " + game.userX_id)
		print("-- User      : " + user.id)
		if game.userX_id == user.id:
			# Same player tried to join.
			pass
		elif not game.userO_id:
			# Current user joins this game as the second player.
			game.userO = user
			game.userO_id = user.id
			logging.info("User " + str(user) + " joins the game.")
		elif (user.id != game.userO_id and user.id != game.userX_id):
			print("Observer", user, "joined", game.key)

	game_link = '/?g=' + game_key
	if not original_game_key:
		return aiohttp.web.HTTPFound(game_link)

	#token = channel.create_channel(user.user_id())
	token = "123"

	returnable_games_html = ""
	joinable_games_html = ""
	observable_games_html = ""
	# joinable_games_html = recent_games.joinable_html(game_key)
	# if len(joinable_games_html) > 0:
	# 	joinable_games_html = "Or join another available game below:<br />" + joinable_games_html
	# observable_games_html = recent_games.observable_html(game_key)
	# if len(observable_games_html) > 0:
	# 	observable_games_html = "<p />Observe an existing game:<br />" + observable_games_html
	# returnable_games_html = recent_games.returnable_html(game_key)
	# if len(returnable_games_html) > 0:
	# 	returnable_games_html = "<p />Return to your existing game:<br />" + returnable_games_html

	# p = player.get(user.user_id(), user)
	# top_list = player.TopPlayers()
	template_values = {
	    'token':
	    token,
	    'me':
	    user,
	    'game_key':
	    game_key,
	    'game_link':
	    game_link,
	    'initial_message':
	    game_storage.GameUpdater(game).get_game_message(),
	    'recent_games':
	    returnable_games_html + "\n" + joinable_games_html + "\n" +
	    observable_games_html,
	    'rating':
	    0,
	    # 'top_players': top_list.html(),
	    'top_players':
	    "",
	    'wins':
	    0,
	    'losses':
	    0
	}

	return aiohttp.web.Response(
	    text=index_template.render(**template_values),
	    content_type="text/html")


@auth.authenticated
async def getstate_handler(request):
	user, game = user_and_game(request)
	json_data = game_storage.GameUpdater(game).get_game_message()
	return aiohttp.web.Response(text=json_data)


@auth.authenticated
async def move_handler(request):
	user, game = user_and_game(request)
	from_id = request.query.get('from')
	to_id = request.query.get('to')
	if from_id and to_id:
		updater = game_storage.GameUpdater(game)
		if updater.move(user, from_id, to_id):
			updater.send_update()
	else:
		raise aiohttp.web.HTTPBadRequest(text="Need from and to IDs.")
	return aiohttp.web.Response(text="OK")


@auth.authenticated
async def newgame_handler(request):
	user, game = user_and_game(request)

	current_userX = game.userX
	current_userO = game.userO
	current_userX_id = game.userX_id
	current_userO_id = game.userO_id
	current_observers = game.observers
	# TODO: Check that game is finished.
	if current_userX == user or current_userO == user:
		# Create a new game.
		game, _ = game_storage.new(user, game.key)
		# Set properties.
		game.userX = current_userX
		game.userO = current_userO
		game.userX_id = current_userX_id
		game.userO_id = current_userO_id
		game.observers = current_observers
		game_storage.GameUpdater(game).send_update()

	return aiohttp.web.Response(text="OK")


@auth.authenticated
async def opened_handler(request):
	user, game = user_and_game(request)
	print("Opened:", user, game.key)
	game_storage.GameUpdater(game).send_update()
	return aiohttp.web.Response(text="OK")


@auth.authenticated
async def ping_handler(request):
	user, game = user_and_game(request)
	print("Ping:", user, game.key)
	game_storage.GameUpdater(game).send_update()

	if game.state == constants.STATE_GAMEOVER and not game.results_are_written:
		if game.winner == constants.WHITE:
			auth.change_ratings(game.userX, game.userO)
		else:
			auth.change_ratings(game.userO, game.userX)

		print("White player after update ", game.userX)
		print("Black player after update ", game.userO)

		game.results_are_written = True
		game.put()

	return aiohttp.web.Response(text="OK")


@auth.authenticated
async def randomize_handler(request):
	user, game = user_and_game(request)
	await request.post()

	current_userX_id = game.userX_id
	current_userO_id = game.userO_id
	if current_userX_id == user.id or current_userO_id == user.id:
		updater = game_storage.GameUpdater(game)
		updater.randomize()
		updater.send_update()

	return aiohttp.web.Response(text="OK")


@auth.authenticated
async def ready_handler(request):
	user, game = user_and_game(request)
	data = await request.post()
	ready = data.get("ready")
	print("User", user, "ready:", ready, "data:", data)
	game_storage.GameUpdater(game).set_ready(user.id, ready)
	return aiohttp.web.Response(text="OK")


async def websocket_handler(request):
	# Anyone can listen to updates for a game.game_key
	key = request.query.get('g')
	game = game_storage.get(key)
	if not game:
		raise aiohttp.web.HTTPNotFound(text="Game not found.")
	print('Websocket connection starting')
	ws = aiohttp.web.WebSocketResponse()
	await ws.prepare(request)
	print('Websocket connection ready')

	game.observers.append(ws)

	async for msg in ws:
		print("Received", msg, "over websocket.")
		if msg.type == aiohttp.WSMsgType.TEXT:
			if msg.data == 'close':
				await ws.close()

	print('Websocket connection closed')
	return ws


@auth.authenticated
async def resetplayer_handler(request):
	# TODO: Implement
	return aiohttp.web.Response(text="OK")


@auth.debug_authenticated
async def setdebug_handler(request):
	user, game = user_and_game(request)
	data = await request.post()
	debug = data.get("debug")
	if debug is None or debug == "" or int(debug) == 1:
		game.debug_no_time = True
		print("Debug mode on for game ", game.key)
	else:
		game.debug_no_time = False
		print("Debug mode off for game ", game.key)
	return aiohttp.web.Response(text="OK")


def setup_loop(loop):
	app = aiohttp.web.Application()
	app.router.add_get('/', main_page)
	app.router.add_get('/getplayer', getplayer_page)
	app.router.add_get('/loginpage', login_page)
	app.router.add_static('/game',
	                      os.path.join(os.path.dirname(__file__), "game"))

	app.router.add_post('/anonymous_login', auth.anonymous_login_handler)
	app.router.add_post('/getstate', getstate_handler)
	app.router.add_post('/move', move_handler)
	app.router.add_post('/newgame', newgame_handler)
	app.router.add_post('/opened', opened_handler)
	app.router.add_post('/ping', ping_handler)
	app.router.add_post('/randomize', randomize_handler)
	app.router.add_post('/ready', ready_handler)

	app.router.add_route('GET', '/websocket', websocket_handler)

	if auth.IS_UNSAFE_DEBUG:
		app.router.add_post('/resetplayer', resetplayer_handler)
		app.router.add_post('/setdebug', setdebug_handler)

	handler = app.make_handler()
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
	if len(sys.argv) < 2 or (sys.argv[1] != "run" and sys.argv[1] != "debug"):
		print("Specify", sys.argv[0], " run/debug to run.")
		sys.exit(0)
	if sys.argv[1] == "debug":
		auth.IS_UNSAFE_DEBUG = True
	loop = asyncio.get_event_loop()
	stop = setup_loop(loop)
	if os.name != "nt":
		loop.add_signal_handler(signal.SIGTERM, loop.stop)

	print("Server started.")
	try:
		loop.run_forever()
	except KeyboardInterrupt:
		print("KeyboardInterrupt.")
		pass

	stop()
	loop.close()
	print("Server closed.")
