import asyncio
import json
import unittest
import urllib.parse

import aiohttp
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

import board
import constants
import realtimechess


class User:
	def __init__(self, client, name):
		self.client = client
		self.name = name

	async def call(self, name, data={}):
		encoded_params = urllib.parse.urlencode(data)
		return await self.request(
		    "/" + name + "?g=" + self.game + "&" + encoded_params,
		    data=data,
		    method="POST")

	async def connect(self):
		# Access implementation detail to clear cookies.
		self.client.session._cookie_jar = aiohttp.CookieJar(unsafe=True)

		response = await self.client.request(
		    "POST", "/anonymous_login", data={
		        "name": self.name
		    })
		response.raise_for_status()
		self.game = response.url.query.get("g")

		self.ws = await self.client.ws_connect("/websocket?g=" + self.game)

		# Access implementation detail to store cookies.
		self.cookie_jar = self.client.session._cookie_jar
		self.client.session._cookie_jar = aiohttp.CookieJar(unsafe=True)

	async def disable_time(self):
		await self.call("setdebug")

	async def enable_time(self):
		await self.call("setdebug", {"debug": 0})

	async def expect_websocket(self):
		return json.loads((await self.ws.receive()).data)

	async def get_state(self):
		return GameState(await self.call("getstate"))

	async def join_game(self, host):
		await self.ws.close()
		data = await self.request("/?g=" + host.game)
		self.game = host.game
		self.ws = await self.client.ws_connect("/websocket?g=" + self.game)
		return data

	async def losses(self):
		map = json.loads(await self.request("/getplayer"))
		return int(map["losses"])

	async def move(self, from_pos, to_pos):
		await self.call("move", {"from": from_pos, "to": to_pos})

	async def move_websocket(self, from_pos, to_pos):
		await self.ws.send_str("/move?g={}&from={}&to={}".format(
		    self.game, from_pos, to_pos))

	async def new_game(self):
		# Access implementation detail to restore cookies.
		self.client.session._cookie_jar = self.cookie_jar
		response = await self.client.request("GET", "/")
		response.raise_for_status()
		self.game = response.url.query.get("g")

	async def rating(self):
		map = json.loads(await self.request("/getplayer"))
		return int(map["rating"])

	async def request(self, path, data=None, method="GET"):
		# Access implementation detail to restore cookies.
		self.client.session._cookie_jar = self.cookie_jar

		response = await self.client.request(method, path, data=data)
		response.raise_for_status()
		return await response.text()

	async def wins(self):
		map = json.loads(await self.request("/getplayer"))
		return int(map["wins"])


class GameState:
	def __init__(self, json_string):
		self.data = json.loads(json_string)

		self.data["state"] = int(self.data["state"])

	def board(self):
		pieces = []
		for i in range(32):
			pieces.append(self.data["p" + str(i)])
		return board.Board(pieces)

	def moving(self, piece):
		pass

	def ready(self, color):
		assert color == constants.WHITE or color == constants.BLACK
		if color == constants.WHITE:
			return self.data["userXReady"]
		else:
			return self.data["userOReady"]

	def game_state(self):
		return self.data["state"]

	def __str__(self):
		return str(self.data)


class GameTest(AioHTTPTestCase):
	async def get_application(self):
		return realtimechess.make_app(True)

	async def setUpAsync(self):
		self.user1 = User(self.client, "user1")
		await self.user1.connect()
		self.user2 = User(self.client, "user2")
		await self.user2.connect()

		self.assertEqual(constants.STATE_START,
		                 (await self.user1.get_state()).game_state())
		await self.user2.join_game(self.user1)
		self.assertEqual(constants.STATE_START,
		                 (await self.user1.get_state()).game_state())
		await self.user1.call("ready", {"ready": 1})
		self.assertEqual(constants.STATE_START,
		                 (await self.user2.get_state()).game_state())
		await self.user2.call("ready", {"ready": 1})

		# TODO: Figure out why user2’s websocket is blocking here.
		await self.user1.expect_websocket()
		await self.user2.expect_websocket()
		self.assertEqual(constants.STATE_PLAY,
		                 (await self.user1.get_state()).game_state())

	async def tearDownAsync(self):
		pass

	@unittest_run_loop
	async def test_redirect_to_loginpage(self):
		# Access implementation detail to clear cookies.
		self.client.session._cookie_jar = aiohttp.CookieJar(unsafe=True)

		response = await self.client.request("GET", "/")
		assert response.status == 200
		text = await response.text()
		self.assertIn("Choose your name", text)

	@unittest_run_loop
	async def test_state(self):
		self.assertTrue((await self.user1.get_state()).board().has_piece("A2"))
		self.assertEqual(board.PAWN,
		                 (await
		                  self.user1.get_state()).board().piece("A2").type)
		self.assertEqual(board.WHITE,
		                 (await
		                  self.user1.get_state()).board().piece("A2").color)

	@unittest_run_loop
	async def test_move(self):
		self.assertTrue((await self.user1.get_state()).board().has_piece("A2"))

		await self.user1.move("A2", "A3")
		await self.user1.expect_websocket()
		await self.user2.expect_websocket()

		self.assertFalse((await
		                  self.user1.get_state()).board().has_piece("A2"))
		await self.user1.disable_time()
		self.assertTrue((await self.user1.get_state()).board().has_piece("A3"))

	@unittest_run_loop
	async def test_move_websocket(self):
		self.assertTrue((await self.user1.get_state()).board().has_piece("A2"))

		await self.user1.move_websocket("A2", "A3")
		await self.user1.expect_websocket()
		await self.user2.expect_websocket()

		state = await self.user1.get_state()
		self.assertFalse(state.board().has_piece("A2"))
		await self.user1.disable_time()
		state = await self.user1.get_state()
		self.assertTrue((await self.user1.get_state()).board().has_piece("A3"))

	@unittest_run_loop
	async def test_move_other_players(self):
		with self.assertRaises(aiohttp.ClientResponseError) as cm:
			await self.user1.move("A7", "A6")
		self.assertEqual(403, cm.exception.code)

	@unittest_run_loop
	async def test_move_from_invalid_position(self):
		with self.assertRaises(aiohttp.ClientResponseError) as cm:
			await self.user1.move("Q9", "A6")
		self.assertEqual(400, cm.exception.code)

	@unittest_run_loop
	async def test_move_to_invalid_position(self):
		with self.assertRaises(aiohttp.ClientResponseError) as cm:
			await self.user1.move("A2", "P0")
		self.assertEqual(400, cm.exception.code)

	@unittest_run_loop
	async def test_move_from_empty(self):
		with self.assertRaises(aiohttp.ClientResponseError) as cm:
			await self.user1.move("A3", "A4")
		self.assertEqual(404, cm.exception.code)

	@unittest_run_loop
	async def test_move_moving(self):
		await self.user1.move("A2", "A3")
		with self.assertRaises(aiohttp.ClientResponseError) as cm:
			await self.user1.move("A3", "A4")
		# There is no piece in A3 (yet).
		self.assertEqual(404, cm.exception.code)
		self.assertFalse((await
		                  self.user1.get_state()).board().has_piece("A4"))

	@unittest_run_loop
	async def test_capture(self):
		await self.user1.disable_time()

		await self.user1.move("E2", "E3")
		await self.user1.move("D1", "G4")  #QG4
		self.assertEqual(board.QUEEN,
		                 (await
		                  self.user1.get_state()).board().piece("G4").type)
		await self.user2.move("D7", "D6")
		await self.user2.move("C8", "G4")  #BG4
		self.assertEqual(board.BISHOP,
		                 (await
		                  self.user1.get_state()).board().piece("G4").type)
		await self.user2.move("G4", "F3")  #BF3
		self.assertIs(None, (await self.user1.get_state()).board().piece("A3"))

	@unittest_run_loop
	async def test_capture2(self):
		await self.user1.disable_time()

		await self.user1.move("B2", "B3")
		await self.user1.move("C1", "B2")
		self.assertEqual(constants.PAWN,
		                 (await
		                  self.user1.get_state()).board().piece("C7").type)
		await self.user1.move("B2", "G7")
		self.assertEqual(constants.BISHOP,
		                 (await
		                  self.user1.get_state()).board().piece("G7").type)
		self.assertEqual(constants.ROOK,
		                 (await
		                  self.user1.get_state()).board().piece("H8").type)
		await self.user1.move("G7", "H8")
		self.assertEqual(constants.BISHOP,
		                 (await
		                  self.user1.get_state()).board().piece("H8").type)

	@unittest_run_loop
	async def test_promotion_white(self):
		await self.user1.disable_time()

		await self.user1.move("B2", "B4")
		await self.user1.move("B4", "B5")
		await self.user1.move("B5", "B6")
		await self.user1.move("B6", "C7")
		self.assertEqual(constants.KNIGHT,
		                 (await
		                  self.user1.get_state()).board().piece("B8").type)
		await self.user1.move("C7", "B8")
		self.assertEqual(constants.QUEEN,
		                 (await
		                  self.user1.get_state()).board().piece("B8").type)

	@unittest_run_loop
	async def test_promotion_black(self):
		await self.user1.disable_time()

		await self.user2.move("H7", "H5")
		await self.user2.move("H5", "H4")
		await self.user2.move("H4", "H3")
		await self.user2.move("H3", "G2")
		self.assertEqual(constants.ROOK,
		                 (await
		                  self.user1.get_state()).board().piece("H1").type)
		self.assertEqual(constants.WHITE,
		                 (await
		                  self.user1.get_state()).board().piece("H1").color)
		await self.user2.move("G2", "H1")
		self.assertEqual(constants.QUEEN,
		                 (await
		                  self.user1.get_state()).board().piece("H1").type)
		self.assertEqual(constants.BLACK,
		                 (await
		                  self.user1.get_state()).board().piece("H1").color)

	@unittest_run_loop
	async def test_full_games(self):
		self.assertEqual(1000, await self.user1.rating())
		self.assertEqual(1000, await self.user2.rating())
		self.assertEqual(0, await self.user1.wins())
		self.assertEqual(0, await self.user1.losses())
		self.assertEqual(0, await self.user2.wins())
		self.assertEqual(0, await self.user2.losses())
		await self.user1.disable_time()

		await self.user1.move("B1", "C3")
		await self.user1.move("C3", "D5")
		await self.user1.move("D5", "C7")
		self.assertEqual(constants.STATE_PLAY,
		                 (await self.user1.get_state()).game_state())
		await self.user1.move("C7", "E8")
		await self.user1.call("ping")
		self.assertEqual(constants.STATE_GAMEOVER,
		                 (await self.user1.get_state()).game_state())
		self.assertEqual(1016, await self.user1.rating())
		self.assertEqual(1000 + 1000 - await self.user1.rating(), await
		                 self.user2.rating())
		self.assertEqual(1, await self.user1.wins())
		self.assertEqual(0, await self.user1.losses())
		self.assertEqual(0, await self.user2.wins())
		self.assertEqual(1, await self.user2.losses())

		# Can not move in STATE_GAMEOVER.
		with self.assertRaises(aiohttp.ClientResponseError) as cm:
			await self.user1.move("B2", "B3")
		self.assertEqual(403, cm.exception.code)
		# Can not randomize in STATE_GAMEOVER.
		with self.assertRaises(aiohttp.ClientResponseError) as cm:
			await self.user1.call("randomize")
		self.assertEqual(403, cm.exception.code)

		await self.user2.call("newgame")
		self.assertEqual(constants.STATE_START,
		                 (await self.user1.get_state()).game_state())
		# Can not move in STATE_START.
		with self.assertRaises(aiohttp.ClientResponseError) as cm:
			await self.user1.move("B1", "C3")
		self.assertEqual(403, cm.exception.code)

		await self.user2.call("ready", {"ready": 1})
		await self.user1.call("ready", {"ready": 1})
		self.assertEqual(constants.STATE_PLAY,
		                 (await self.user1.get_state()).game_state())

		await self.user1.disable_time()
		await self.user1.move("E2", "E4")
		await self.user1.move("E4", "E5")
		await self.user1.move("E5", "E6")
		await self.user1.move("E6", "F7")
		await self.user1.move("F7", "E8")
		await self.user1.call("ping")
		self.assertEqual(constants.STATE_GAMEOVER,
		                 (await self.user1.get_state()).game_state())
		self.assertEqual(1031, await self.user1.rating())
		self.assertEqual(1000 + 1000 - await self.user1.rating(), await
		                 self.user2.rating())
		self.assertEqual(2, await self.user1.wins())
		self.assertEqual(0, await self.user1.losses())
		self.assertEqual(0, await self.user2.wins())
		self.assertEqual(2, await self.user2.losses())

		await self.user1.call("newgame")
		await self.user1.call("ready", {"ready": 1})
		await self.user2.call("ready", {"ready": 1})
		await self.user1.disable_time()
		await self.user2.move("E7", "E5")
		await self.user2.move("D8", "H4")
		await self.user2.move("H4", "F2")
		await self.user2.move("F2", "E1")
		await self.user2.call("ping")
		self.assertEqual(constants.STATE_GAMEOVER,
		                 (await self.user1.get_state()).game_state())
		self.assertEqual(1012, await self.user1.rating())
		self.assertEqual(1000 + 1000 - await self.user1.rating(), await
		                 self.user2.rating())
		self.assertEqual(2, await self.user1.wins())
		self.assertEqual(1, await self.user1.losses())
		self.assertEqual(1, await self.user2.wins())
		self.assertEqual(2, await self.user2.losses())

	@unittest_run_loop
	async def test_ping(self):
		await self.user1.call("ping", {"tag": "123"})
		await self.user2.call("ping", {"tag": "567"})

	@unittest_run_loop
	async def test_black_dodge(self):
		await self.user1.disable_time()
		await self.user2.move("E7", "E6")
		await self.user2.move("D8", "G5")
		await self.user1.move("D2", "D3")
		await self.user1.enable_time()

		await self.user1.move("C1", "G5")
		# Dodge this capture.
		await self.user2.move("G5", "F5")

	@unittest_run_loop
	async def test_white_dodge(self):
		await self.user1.disable_time()
		await self.user1.move("D2", "D4")
		await self.user1.move("C1", "G5")
		await self.user2.move("E7", "E6")
		await self.user1.enable_time()

		await self.user2.move("D8", "G5")
		# Dodge this capture.
		await self.user1.move("G5", "F4")

	@unittest_run_loop
	async def test_move_to_same(self):
		await self.user1.move("G1", "F3")
		# Server does not return error, but does not execute.
		await self.user1.move("F2", "F3")
		await self.user1.disable_time()
		await self.user1.move("A2", "A3")
		self.assertEqual(constants.PAWN,
		                 (await
		                  self.user1.get_state()).board().piece("F2").type)
		self.assertEqual(constants.KNIGHT,
		                 (await
		                  self.user1.get_state()).board().piece("F3").type)

	@unittest_run_loop
	async def test_join_game_page(self):
		# User 2 goes to the front page.
		front_page = await self.user2.request("/?g=" + self.user2.game)
		key1 = self.user1.game
		self.assertIn(str(key1), front_page)
		self.assertIn("user1", front_page)

	@unittest_run_loop
	async def test_make_up_game_url(self):
		with self.assertRaises(aiohttp.ClientResponseError) as cm:
			await self.user1.request("/?g=123")
		self.assertEqual(404, cm.exception.code)

	@unittest_run_loop
	async def test_pawn_move(self):
		await self.user1.disable_time()

		await self.user1.move("A2", "A3")
		self.assertIsNone((await self.user1.get_state()).board().piece("A2"))

		await self.user1.move("B2", "B4")
		self.assertIsNotNone((await
		                      self.user1.get_state()).board().piece("B4"))

		await self.user1.move("C2", "C5")
		self.assertIsNotNone((await
		                      self.user1.get_state()).board().piece("C2"))

		await self.user1.move("D2", "D3")
		await self.user1.move("D3", "D5")
		self.assertIsNone((await self.user1.get_state()).board().piece("D5"))
		self.assertIsNotNone((await
		                      self.user1.get_state()).board().piece("D3"))

		await self.user2.move("A7", "A6")
		self.assertIsNone((await self.user2.get_state()).board().piece("A7"))

		await self.user2.move("B7", "B5")
		self.assertIsNotNone((await
		                      self.user2.get_state()).board().piece("B5"))

		await self.user2.move("C7", "C4")
		self.assertIsNotNone((await
		                      self.user2.get_state()).board().piece("C7"))

		await self.user2.move("D7", "D6")
		await self.user2.move("D6", "D4")
		self.assertIsNone((await self.user2.get_state()).board().piece("D4"))
		self.assertIsNotNone((await
		                      self.user2.get_state()).board().piece("D6"))

	@unittest_run_loop
	async def test_capture_respects_time_difference_1(self):
		await self.user1.disable_time()
		await self.user1.move("E2", "E3")
		await self.user1.move("D1", "G4")
		await self.user2.move("D7", "D6")
		await self.user1.enable_time()

		# Queen moves the shorter distance.
		await self.user1.move("G4", "F5")
		await self.user2.move("C8", "F5")
		F5 = (await self.user1.get_state()).board().piece("F5")
		self.assertIsNone(F5)

		await self.user1.disable_time()
		F5 = (await self.user1.get_state()).board().piece("F5")
		self.assertEqual(constants.BISHOP, F5.type)
		self.assertEqual(constants.BLACK, F5.color)

	@unittest_run_loop
	async def test_capture_respects_time_difference_2(self):
		await self.user1.disable_time()
		await self.user1.move("E2", "E3")
		await self.user1.move("D1", "G4")
		await self.user2.move("D7", "D6")
		await self.user1.enable_time()

		# Queen moves the shorter distance.
		await self.user2.move("C8", "F5")
		await self.user1.move("G4", "F5")
		F5 = (await self.user1.get_state()).board().piece("F5")
		self.assertIsNone(F5)

		await self.user1.disable_time()
		F5 = (await self.user1.get_state()).board().piece("F5")
		self.assertEqual(constants.BISHOP, F5.type)
		self.assertEqual(constants.BLACK, F5.color)

	@unittest_run_loop
	async def test_capture_respects_time_difference_3(self):
		await self.user1.disable_time()
		await self.user1.move("E2", "E3")
		await self.user1.move("D1", "G4")
		await self.user2.move("D7", "D6")

		# Bishop moves the shorter distance.
		await self.user1.enable_time()
		await self.user1.move("G4", "D7")
		await self.user2.move("C8", "D7")
		D7 = (await self.user1.get_state()).board().piece("D7")
		self.assertIsNone(D7)

		await self.user1.disable_time()
		D7 = (await self.user1.get_state()).board().piece("D7")
		self.assertEqual(constants.QUEEN, D7.type)
		self.assertEqual(constants.WHITE, D7.color)

	@unittest_run_loop
	async def test_capture_respects_time_difference_4(self):
		await self.user1.disable_time()
		await self.user1.move("E2", "E3")
		await self.user1.move("D1", "G4")
		await self.user2.move("D7", "D6")
		await self.user1.enable_time()

		# Bishop moves the shorter distance.
		await self.user2.move("C8", "D7")
		await self.user1.move("G4", "D7")
		D7 = (await self.user1.get_state()).board().piece("D7")
		self.assertIsNone(D7)

		await self.user1.disable_time()
		D7 = (await self.user1.get_state()).board().piece("D7")
		self.assertEqual(constants.QUEEN, D7.type)
		self.assertEqual(constants.WHITE, D7.color)

	@unittest_run_loop
	async def test_third_player_joins(self):
		user3 = User(self.client, "user3")
		await user3.connect()
		await user3.join_game(self.user1)

		with self.assertRaises(aiohttp.ClientResponseError) as cm:
			await user3.move("A7", "A6")
		self.assertEqual(403, cm.exception.code)

		with self.assertRaises(aiohttp.ClientResponseError) as cm:
			await user3.call("ready", {"ready": 1})
		self.assertEqual(403, cm.exception.code)

		await self.user1.move("E2", "E3")
		await self.user2.move("D7", "D6")

	@unittest_run_loop
	async def test_new_game_check_finished(self):
		await self.user1.move("E2", "E3")
		# Game is not finished.
		with self.assertRaises(aiohttp.ClientResponseError) as cm:
			await self.user1.call("newgame")
		self.assertEqual(403, cm.exception.code)

	@unittest_run_loop
	async def test_error(self):
		await self.user1.call("error")


class TestStart(AioHTTPTestCase):
	async def get_application(self):
		return realtimechess.make_app(True)

	async def setUpAsync(self):
		self.user1 = User(self.client, "user4")
		await self.user1.connect()
		self.user2 = User(self.client, "user5")
		await self.user2.connect()

	@unittest_run_loop
	async def test_join_own_game(self):
		self.assertEqual(constants.STATE_START,
		                 (await self.user1.get_state()).game_state())
		await self.user1.join_game(self.user1)

	@unittest_run_loop
	async def test_randomize(self):
		await self.user2.join_game(self.user1)
		await self.user1.call("ready", {"ready": 0})
		await self.user2.call("ready", {"ready": 1})
		self.assertEqual((await self.user1.get_state()).ready(constants.WHITE),
		                 False)
		self.assertEqual((await self.user1.get_state()).ready(constants.BLACK),
		                 True)
		await self.user1.call("randomize")
		self.assertEqual((await self.user1.get_state()).ready(constants.WHITE),
		                 False)
		self.assertEqual((await self.user1.get_state()).ready(constants.BLACK),
		                 True)
		await self.user2.call("randomize")


class TestConcurrency(AioHTTPTestCase):
	async def get_application(self):
		return realtimechess.make_app(True)

	@unittest_run_loop
	async def test_concurrency(self):
		# This test is a little awkward, but it was converted
		# from non-async code.

		N = 2
		user1 = []
		user2 = []
		for i in range(N):
			user1.append(User(self.client, "user1"))
			user2.append(User(self.client, "user2"))
		for u in user1 + user2:
			await u.connect()

		for i in range(1, N):
			user1[i].game = user1[0].game
		for i in range(N):
			await user2[i].join_game(user1[0])

		await user1[0].call("ready", {"ready": 1})
		await user2[0].call("ready", {"ready": 1})

		await user1[0].disable_time()
		for i in range(N):
			self.assertEqual(constants.STATE_PLAY, (await user1[i]
			                                        .get_state()).game_state())
			self.assertEqual(constants.STATE_PLAY, (await user2[i]
			                                        .get_state()).game_state())

		await user1[0].move("G2", "G4")
		await user1[1].move("H2", "H4")
		await user2[0].move("G7", "G6")
		await user2[1].move("H7", "H6")

		futures = []
		futures.append(user1[0].move("A2", "A3"))
		futures.append(user1[1].move("B2", "B3"))
		futures.append(user2[0].move("A7", "A6"))
		futures.append(user2[1].move("B7", "B6"))
		await asyncio.gather(*futures)

		await user1[0].move("B1", "C3")
		await user2[0].move("C7", "C6")

		futures = []
		futures.append(user1[0].move("C3", "D5"))
		futures.append(user1[1].move("E2", "E3"))
		futures.append(user2[0].move("D7", "D6"))
		futures.append(user2[1].move("E7", "E6"))
		await asyncio.gather(*futures)

		await user1[0].move("F2", "F3")
		await user2[0].move("F7", "F6")

		b = (await user1[0].get_state()).board()
		for pos in [
		    "A3", "B3", "E3", "F3", "A6", "B6", "C6", "D6", "E6", "F6"
		]:
			self.assertEqual(constants.PAWN, b.piece(pos).type)

		await user1[0].move("D5", "C7")
		self.assertEqual(constants.STATE_PLAY, (await user1[0]
		                                        .get_state()).game_state())
		await user1[0].move("C7", "E8")
		await user1[0].call("ping")
		self.assertEqual(constants.STATE_GAMEOVER, (await user1[0]
		                                            .get_state()).game_state())

		futures = []
		futures.append(user1[0].new_game())
		futures.append(user1[1].new_game())
		futures.append(user2[0].new_game())
		futures.append(user2[1].new_game())
		await asyncio.gather(*futures)


if __name__ == '__main__':
	unittest.main()
