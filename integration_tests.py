#!/usr/bin/python3

import concurrent.futures
import http.client
import json
import re
import unittest
import urllib

import board
from constants import *


class HttpCodeException(Exception):
	def __init__(self, code):
		self.code = code

	def __str__(self):
		return "HTTP error " + str(self.code)


class AnonymousUser:
	def __init__(self, name, server="localhost", port=8080):
		self.email = name
		self.server = server
		self.port = port

		self.GAME_ID_PATTERN = re.compile(
		    re.escape("/?g=") + """([a-zA-Z0-9]+)""")

		self.conn = http.client.HTTPConnection(self.server, self.port)
		encoded_params = urllib.parse.urlencode({"name": name})
		headers = {
		    "Content-type": "application/x-www-form-urlencoded",
		    "Accept": "text/plain"
		}
		self.conn.request("POST", "/anonymous_login", encoded_params, headers)
		response = self.conn.getresponse()
		response.read()
		assert response.status < 400
		self.cookie = response.getheader("Set-Cookie")

		self.new_game()

	def close(self):
		self.conn.close()

	def user_id(self):
		return self.email

	def request(self, path):
		header = {}
		header["Cookie"] = self.cookie
		self.conn.request("GET", path, None, header)
		response = self.conn.getresponse()
		data = response.read()
		if response.status != 200:
			raise HttpCodeException(response.status)

		return data

	def call(self, name, params={}):
		headers = {
		    "Content-type": "application/x-www-form-urlencoded",
		    "Accept": "text/plain",
		    "Cookie": self.cookie
		}
		encoded_params = urllib.parse.urlencode(params)
		self.conn.request(
		    "POST", "/" + name + "?g=" + self.game + "&" + encoded_params,
		    encoded_params, headers)
		response = self.conn.getresponse()
		data = response.read()

		if response.status == 408:
			# Retry
			return self.call(name, params)

		if response.status != 200:
			raise HttpCodeException(response.status)
		return data

	def new_game(self):
		header = {}
		assert self.cookie
		header["Cookie"] = self.cookie
		self.conn.request("GET", "/", headers=header)
		response = self.conn.getresponse()
		response.read()
		if response.status != 302:
			raise HttpCodeException(response.status)
		location = response.getheader("Location")
		self.game = self.GAME_ID_PATTERN.match(location).group(1)

	def join_game(self, host):
		data = self.request("/?g=" + host.game)
		self.game = host.game
		return data

	def move(self, from_pos, to_pos):
		self.call("move", {"from": from_pos, "to": to_pos})

	def get_state(self):
		json_string = self.call("getstate").decode("utf-8")
		return GameState(json_string)

	def disable_time(self):
		self.call("setdebug")

	def enable_time(self):
		self.call("setdebug", {"debug": 0})

	def rating(self):
		data = self.request("/getplayer")
		map = json.loads(data.decode("utf-8"))
		return int(map["rating"])

	def wins(self):
		data = self.request("/getplayer")
		map = json.loads(data.decode("utf-8"))
		return int(map["wins"])

	def losses(self):
		data = self.request("/getplayer")
		map = json.loads(data.decode("utf-8"))
		return int(map["losses"])


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
		assert (color == WHITE or color == BLACK)
		if color == WHITE:
			return self.data["userXReady"]
		else:
			return self.data["userOReady"]

	def game_state(self):
		return self.data["state"]

	def __str__(self):
		return str(self.data)


class TestNotLoggedIn(unittest.TestCase):
	@classmethod
	def setUpClass(self):
		self.conn = http.client.HTTPConnection("localhost", 8080)

	@classmethod
	def tearDownClass(self):
		self.conn.close()

	def testIndex(self):
		self.conn.request("GET", "/")
		response = self.conn.getresponse()
		response.read()
		self.assertEqual(302, response.status)

	def testLogin(self):
		self.conn.request("GET", "/loginpage")
		response = self.conn.getresponse()
		response.read()
		self.assertEqual(200, response.status)


class TestGame(unittest.TestCase):
	@classmethod
	def setUpClass(self):
		self.user1 = AnonymousUser("integration-user1")
		self.user2 = AnonymousUser("integration-user2")

	@classmethod
	def tearDownClass(self):
		self.user1.close()
		self.user2.close()

	def setUp(self):
		self.user1.new_game()
		self.assertEqual(STATE_START, self.user1.get_state().game_state())
		self.user2.join_game(self.user1)
		self.assertEqual(STATE_START, self.user1.get_state().game_state())
		self.user1.call("ready", {"ready": 1})
		self.assertEqual(STATE_START, self.user1.get_state().game_state())
		self.user2.call("ready", {"ready": 1})
		self.assertEqual(STATE_PLAY, self.user1.get_state().game_state())

	def test_state(self):
		self.assertTrue(self.user1.get_state().board().has_piece("A2"))
		self.assertEqual(board.PAWN,
		                 self.user1.get_state().board().piece("A2").type)
		self.assertEqual(board.WHITE,
		                 self.user1.get_state().board().piece("A2").color)

	def test_move(self):
		self.assertTrue(self.user1.get_state().board().has_piece("A2"))
		self.user1.move("A2", "A3")
		self.assertFalse(self.user1.get_state().board().has_piece("A2"))
		self.user1.disable_time()
		self.assertTrue(self.user1.get_state().board().has_piece("A3"))

	def test_move_other_players(self):
		with self.assertRaises(HttpCodeException) as cm:
			self.user1.move("A7", "A6")
		self.assertEqual(403, cm.exception.code)

	def test_move_from_invalid_position(self):
		with self.assertRaises(HttpCodeException) as cm:
			self.user1.move("Q9", "A6")
		self.assertEqual(400, cm.exception.code)

	def test_move_to_invalid_position(self):
		with self.assertRaises(HttpCodeException) as cm:
			self.user1.move("A2", "P0")
		self.assertEqual(400, cm.exception.code)

	def test_move_from_empty(self):
		with self.assertRaises(HttpCodeException) as cm:
			self.user1.move("A3", "A4")
		self.assertEqual(404, cm.exception.code)

	def test_move_moving(self):
		self.user1.move("A2", "A3")
		with self.assertRaises(HttpCodeException) as cm:
			self.user1.move("A3", "A4")
		# There is no piece in A3 (yet).
		self.assertEqual(404, cm.exception.code)
		self.assertFalse(self.user1.get_state().board().has_piece("A4"))

	def test_capture(self):
		self.user1.disable_time()

		self.user1.move("E2", "E3")
		self.user1.move("D1", "G4")  #QG4
		self.assertEqual(board.QUEEN,
		                 self.user1.get_state().board().piece("G4").type)
		self.user2.move("D7", "D6")
		self.user2.move("C8", "G4")  #BG4
		self.assertEqual(board.BISHOP,
		                 self.user1.get_state().board().piece("G4").type)
		self.user2.move("G4", "F3")  #BF3
		self.assertIs(None, self.user1.get_state().board().piece("A3"))

	def test_capture2(self):
		self.user1.disable_time()

		self.user1.move("B2", "B3")
		self.user1.move("C1", "B2")
		self.assertEqual(board.PAWN,
		                 self.user1.get_state().board().piece("C7").type)
		self.user1.move("B2", "G7")
		self.assertEqual(board.BISHOP,
		                 self.user1.get_state().board().piece("G7").type)
		self.assertEqual(board.ROOK,
		                 self.user1.get_state().board().piece("H8").type)
		self.user1.move("G7", "H8")
		self.assertEqual(board.BISHOP,
		                 self.user1.get_state().board().piece("H8").type)

	def test_promotion_white(self):
		self.user1.disable_time()

		self.user1.move("B2", "B4")
		self.user1.move("B4", "B5")
		self.user1.move("B5", "B6")
		self.user1.move("B6", "C7")
		self.assertEqual(board.KNIGHT,
		                 self.user1.get_state().board().piece("B8").type)
		self.user1.move("C7", "B8")
		self.assertEqual(board.QUEEN,
		                 self.user1.get_state().board().piece("B8").type)

	def test_promotion_black(self):
		self.user1.disable_time()

		self.user2.move("H7", "H5")
		self.user2.move("H5", "H4")
		self.user2.move("H4", "H3")
		self.user2.move("H3", "G2")
		self.assertEqual(ROOK, self.user1.get_state().board().piece("H1").type)
		self.assertEqual(WHITE,
		                 self.user1.get_state().board().piece("H1").color)
		self.user2.move("G2", "H1")
		self.assertEqual(QUEEN,
		                 self.user1.get_state().board().piece("H1").type)
		self.assertEqual(BLACK,
		                 self.user1.get_state().board().piece("H1").color)

	def test_full_games(self):
		self.assertEqual(1000, self.user1.rating())
		self.assertEqual(1000, self.user2.rating())
		self.assertEqual(0, self.user1.wins())
		self.assertEqual(0, self.user1.losses())
		self.assertEqual(0, self.user2.wins())
		self.assertEqual(0, self.user2.losses())
		self.user1.disable_time()

		self.user1.move("B1", "C3")
		self.user1.move("C3", "D5")
		self.user1.move("D5", "C7")
		self.assertEqual(STATE_PLAY, self.user1.get_state().game_state())
		self.user1.move("C7", "E8")
		self.user1.call("ping")
		self.assertEqual(STATE_GAMEOVER, self.user1.get_state().game_state())
		self.assertEqual(1016, self.user1.rating())
		self.assertEqual(1000 + 1000 - self.user1.rating(),
		                 self.user2.rating())
		self.assertEqual(1, self.user1.wins())
		self.assertEqual(0, self.user1.losses())
		self.assertEqual(0, self.user2.wins())
		self.assertEqual(1, self.user2.losses())

		self.user2.call("newgame")
		self.assertEqual(STATE_START, self.user1.get_state().game_state())
		self.user2.call("ready", {"ready": 1})
		self.user1.call("ready", {"ready": 1})
		self.assertEqual(STATE_PLAY, self.user1.get_state().game_state())

		self.user1.disable_time()
		self.user1.move("E2", "E4")
		self.user1.move("E4", "E5")
		self.user1.move("E5", "E6")
		self.user1.move("E6", "F7")
		self.user1.move("F7", "E8")
		self.user1.call("ping")
		self.assertEqual(STATE_GAMEOVER, self.user1.get_state().game_state())
		self.assertEqual(1031, self.user1.rating())
		self.assertEqual(1000 + 1000 - self.user1.rating(),
		                 self.user2.rating())
		self.assertEqual(2, self.user1.wins())
		self.assertEqual(0, self.user1.losses())
		self.assertEqual(0, self.user2.wins())
		self.assertEqual(2, self.user2.losses())

		self.user1.call("newgame")
		self.user1.call("ready", {"ready": 1})
		self.user2.call("ready", {"ready": 1})
		self.user1.disable_time()
		self.user2.move("E7", "E5")
		self.user2.move("D8", "H4")
		self.user2.move("H4", "F2")
		self.user2.move("F2", "E1")
		self.user2.call("ping")
		self.assertEqual(STATE_GAMEOVER, self.user1.get_state().game_state())
		self.assertEqual(1012, self.user1.rating())
		self.assertEqual(1000 + 1000 - self.user1.rating(),
		                 self.user2.rating())
		self.assertEqual(2, self.user1.wins())
		self.assertEqual(1, self.user1.losses())
		self.assertEqual(1, self.user2.wins())
		self.assertEqual(2, self.user2.losses())

	def test_ping(self):
		self.user1.call("ping", {"tag": "123"})
		self.user2.call("ping", {"tag": "567"})

	def test_black_dodge(self):
		self.user1.disable_time()
		self.user2.move("E7", "E6")
		self.user2.move("D8", "G5")
		self.user1.move("D2", "D3")
		self.user1.enable_time()

		self.user1.move("C1", "G5")
		# Dodge this capture.
		self.user2.move("G5", "F5")

	def test_white_dodge(self):
		self.user1.disable_time()
		self.user1.move("D2", "D4")
		self.user1.move("C1", "G5")
		self.user2.move("E7", "E6")
		self.user1.enable_time()

		self.user2.move("D8", "G5")
		# Dodge this capture.
		self.user1.move("G5", "F4")

	def test_move_to_same(self):
		self.user1.move("G1", "F3")
		# Server does not return error, but does not execute.
		self.user1.move("F2", "F3")
		self.user1.disable_time()
		self.user1.move("A2", "A3")
		self.assertEqual(PAWN, self.user1.get_state().board().piece("F2").type)
		self.assertEqual(KNIGHT,
		                 self.user1.get_state().board().piece("F3").type)

	def test_join_game_page(self):
		# User 2 goes to the front page.
		front_page = self.user2.request("/?g=" + self.user2.game).decode(
		    "utf-8")
		key1 = self.user1.game
		self.assertIn(str(key1), front_page)
		self.assertIn(str("integration-user1"), front_page)

	def test_make_up_game_url(self):
		with self.assertRaises(HttpCodeException) as cm:
			self.user1.request("/?g=123")
		self.assertEqual(404, cm.exception.code)

	def test_pawn_move(self):
		self.user1.disable_time()

		self.user1.move("A2", "A3")
		self.assertIsNone(self.user1.get_state().board().piece("A2"))

		self.user1.move("B2", "B4")
		self.assertIsNotNone(self.user1.get_state().board().piece("B4"))

		self.user1.move("C2", "C5")
		self.assertIsNotNone(self.user1.get_state().board().piece("C2"))

		self.user1.move("D2", "D3")
		self.user1.move("D3", "D5")
		self.assertIsNone(self.user1.get_state().board().piece("D5"))
		self.assertIsNotNone(self.user1.get_state().board().piece("D3"))

		self.user2.move("A7", "A6")
		self.assertIsNone(self.user2.get_state().board().piece("A7"))

		self.user2.move("B7", "B5")
		self.assertIsNotNone(self.user2.get_state().board().piece("B5"))

		self.user2.move("C7", "C4")
		self.assertIsNotNone(self.user2.get_state().board().piece("C7"))

		self.user2.move("D7", "D6")
		self.user2.move("D6", "D4")
		self.assertIsNone(self.user2.get_state().board().piece("D4"))
		self.assertIsNotNone(self.user2.get_state().board().piece("D6"))

	def test_capture_respects_time_difference_1(self):
		self.user1.disable_time()
		self.user1.move("E2", "E3")
		self.user1.move("D1", "G4")
		self.user2.move("D7", "D6")
		self.user1.enable_time()

		# Queen moves the shorter distance.
		self.user1.move("G4", "F5")
		self.user2.move("C8", "F5")
		F5 = self.user1.get_state().board().piece("F5")
		self.assertIsNone(F5)

		self.user1.disable_time()
		F5 = self.user1.get_state().board().piece("F5")
		self.assertEqual(BISHOP, F5.type)
		self.assertEqual(BLACK, F5.color)

	def test_capture_respects_time_difference_2(self):
		self.user1.disable_time()
		self.user1.move("E2", "E3")
		self.user1.move("D1", "G4")
		self.user2.move("D7", "D6")
		self.user1.enable_time()

		# Queen moves the shorter distance.
		self.user2.move("C8", "F5")
		self.user1.move("G4", "F5")
		F5 = self.user1.get_state().board().piece("F5")
		self.assertIsNone(F5)

		self.user1.disable_time()
		F5 = self.user1.get_state().board().piece("F5")
		self.assertEqual(BISHOP, F5.type)
		self.assertEqual(BLACK, F5.color)

	def test_capture_respects_time_difference_3(self):
		self.user1.disable_time()
		self.user1.move("E2", "E3")
		self.user1.move("D1", "G4")
		self.user2.move("D7", "D6")

		# Bishop moves the shorter distance.
		self.user1.enable_time()
		self.user1.move("G4", "D7")
		self.user2.move("C8", "D7")
		D7 = self.user1.get_state().board().piece("D7")
		self.assertIsNone(D7)

		self.user1.disable_time()
		D7 = self.user1.get_state().board().piece("D7")
		self.assertEqual(QUEEN, D7.type)
		self.assertEqual(WHITE, D7.color)

	def test_capture_respects_time_difference_4(self):
		self.user1.disable_time()
		self.user1.move("E2", "E3")
		self.user1.move("D1", "G4")
		self.user2.move("D7", "D6")
		self.user1.enable_time()

		# Bishop moves the shorter distance.
		self.user2.move("C8", "D7")
		self.user1.move("G4", "D7")
		D7 = self.user1.get_state().board().piece("D7")
		self.assertIsNone(D7)

		self.user1.disable_time()
		D7 = self.user1.get_state().board().piece("D7")
		self.assertEqual(QUEEN, D7.type)
		self.assertEqual(WHITE, D7.color)

	def test_third_player_joins(self):
		user3 = AnonymousUser("integration-user3")
		user3.join_game(self.user1)

		with self.assertRaises(HttpCodeException) as cm:
			user3.move("A7", "A6")
		self.assertEqual(403, cm.exception.code)

		self.user1.move("E2", "E3")
		self.user2.move("D7", "D6")
		user3.close()

	def test_new_game_check_finished(self):
		self.user1.move("E2", "E3")
		# Game is not finished.
		with self.assertRaises(HttpCodeException) as cm:
			self.user1.call("newgame")
		self.assertEqual(403, cm.exception.code)


class TestStart(unittest.TestCase):
	@classmethod
	def setUpClass(self):
		self.user1 = AnonymousUser("integration-user4")
		self.user2 = AnonymousUser("integration-user5")

	@classmethod
	def tearDownClass(self):
		self.user1.close()
		self.user2.close()

	def test_join_own_game(self):
		self.assertEqual(STATE_START, self.user1.get_state().game_state())
		self.user1.join_game(self.user1).decode("utf-8")

	def test_randomize(self):
		self.user2.join_game(self.user1)
		self.user1.call("ready", {"ready": 0})
		self.user2.call("ready", {"ready": 1})
		self.assertEqual(self.user1.get_state().ready(WHITE), False)
		self.assertEqual(self.user1.get_state().ready(BLACK), True)
		self.user1.call("randomize")
		self.assertEqual(self.user1.get_state().ready(WHITE), False)
		self.assertEqual(self.user1.get_state().ready(BLACK), True)
		self.user2.call("randomize")


class TestConcurrency(unittest.TestCase):
	def test_concurrency(self):
		N = 2
		user1 = []
		user2 = []
		for i in range(N):
			user1.append(AnonymousUser("integration-user1"))
			user2.append(AnonymousUser("integration-user2"))

		for i in range(1, N):
			user1[i].game = user1[0].game
		for i in range(N):
			user2[i].join_game(user1[0])

		user1[0].call("ready", {"ready": 1})
		user2[0].call("ready", {"ready": 1})

		user1[0].disable_time()
		for i in range(N):
			self.assertEqual(STATE_PLAY, user1[i].get_state().game_state())
			self.assertEqual(STATE_PLAY, user2[i].get_state().game_state())

		user1[0].move("G2", "G4")
		user1[1].move("H2", "H4")
		user2[0].move("G7", "G6")
		user2[1].move("H7", "H6")

		pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
		futures = []
		futures.append(pool.submit(user1[0].move, "A2", "A3"))
		futures.append(pool.submit(user1[1].move, "B2", "B3"))
		futures.append(pool.submit(user2[0].move, "A7", "A6"))
		futures.append(pool.submit(user2[1].move, "B7", "B6"))
		for future in futures:
			future.result()

		user1[0].move("B1", "C3")
		user2[0].move("C7", "C6")

		futures = []
		futures.append(pool.submit(user1[0].move, "C3", "D5"))
		futures.append(pool.submit(user1[1].move, "E2", "E3"))
		futures.append(pool.submit(user2[0].move, "D7", "D6"))
		futures.append(pool.submit(user2[1].move, "E7", "E6"))

		for future in futures:
			future.result()

		user1[0].move("F2", "F3")
		user2[0].move("F7", "F6")

		b = user1[0].get_state().board()
		for pos in [
		    "A3", "B3", "E3", "F3", "A6", "B6", "C6", "D6", "E6", "F6"
		]:
			self.assertEqual(PAWN, b.piece(pos).type)

		user1[0].move("D5", "C7")
		self.assertEqual(STATE_PLAY, user1[0].get_state().game_state())
		user1[0].move("C7", "E8")
		user1[0].call("ping")
		self.assertEqual(STATE_GAMEOVER, user1[0].get_state().game_state())

		futures = []
		futures.append(pool.submit(user1[0].new_game))
		futures.append(pool.submit(user1[1].new_game))
		futures.append(pool.submit(user2[0].new_game))
		futures.append(pool.submit(user2[1].new_game))
		for future in futures:
			future.result()

		for i in range(N):
			user1[i].close()
			user2[i].close()


if __name__ == '__main__':
	unittest.main()
