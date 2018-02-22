import asyncio
import datetime
import json
import logging
import random
import time
import os

import board
from constants import *
from protocol import Piece
from util import HttpCodeException, log_error


class Game():
	"""All the data we store for a game.

	The logic for computing valid moves etc. is handled by the Board class.
	This makes the Game class easy to serialize, if needed. In a previous
	version on App Engine, the Game was stored in a database.
	"""

	def __init__(self, key):
		self.key = key

		# Which users are allowed to play this game.
		self.userX = None
		self.userO = None
		# Users allowed to watch the game.
		self.observers = []

		# When this game was last updated.
		self.creation_time = datetime.datetime.now()

		# Used for debugging to have moves happen instantly and with no sleeping.
		self.debug_no_time = False

		# Whether the game results have been written for the users.
		self.results_are_written = False

		self.seq = 0
		self.state = STATE_START

		self.userX_ready = False
		self.userO_ready = False

		self.p0 = str(WHITE) + "," + str(ROOK) + ";" + "A1"
		self.p1 = str(WHITE) + "," + str(KNIGHT) + ";" + "B1"
		self.p2 = str(WHITE) + "," + str(BISHOP) + ";" + "C1"
		self.p3 = str(WHITE) + "," + str(QUEEN) + ";" + "D1"
		self.p4 = str(WHITE) + "," + str(KING) + ";" + "E1"
		self.p5 = str(WHITE) + "," + str(BISHOP) + ";" + "F1"
		self.p6 = str(WHITE) + "," + str(KNIGHT) + ";" + "G1"
		self.p7 = str(WHITE) + "," + str(ROOK) + ";" + "H1"
		self.p8 = str(WHITE) + "," + str(PAWN) + ";" + "A2"
		self.p9 = str(WHITE) + "," + str(PAWN) + ";" + "B2"
		self.p10 = str(WHITE) + "," + str(PAWN) + ";" + "C2"
		self.p11 = str(WHITE) + "," + str(PAWN) + ";" + "D2"
		self.p12 = str(WHITE) + "," + str(PAWN) + ";" + "E2"
		self.p13 = str(WHITE) + "," + str(PAWN) + ";" + "F2"
		self.p14 = str(WHITE) + "," + str(PAWN) + ";" + "G2"
		self.p15 = str(WHITE) + "," + str(PAWN) + ";" + "H2"
		self.p16 = str(BLACK) + "," + str(ROOK) + ";" + "A8"
		self.p17 = str(BLACK) + "," + str(KNIGHT) + ";" + "B8"
		self.p18 = str(BLACK) + "," + str(BISHOP) + ";" + "C8"
		self.p19 = str(BLACK) + "," + str(QUEEN) + ";" + "D8"
		self.p20 = str(BLACK) + "," + str(KING) + ";" + "E8"
		self.p21 = str(BLACK) + "," + str(BISHOP) + ";" + "F8"
		self.p22 = str(BLACK) + "," + str(KNIGHT) + ";" + "G8"
		self.p23 = str(BLACK) + "," + str(ROOK) + ";" + "H8"
		self.p24 = str(BLACK) + "," + str(PAWN) + ";" + "A7"
		self.p25 = str(BLACK) + "," + str(PAWN) + ";" + "B7"
		self.p26 = str(BLACK) + "," + str(PAWN) + ";" + "C7"
		self.p27 = str(BLACK) + "," + str(PAWN) + ";" + "D7"
		self.p28 = str(BLACK) + "," + str(PAWN) + ";" + "E7"
		self.p29 = str(BLACK) + "," + str(PAWN) + ";" + "F7"
		self.p30 = str(BLACK) + "," + str(PAWN) + ";" + "G7"
		self.p31 = str(BLACK) + "," + str(PAWN) + ";" + "H7"

		self.all_piece_ids = [
		    attr for attr in dir(self)
		    if not callable(attr) and re.match("p\\d\\d?", attr)
		]
		self.update()

	def get_game_message(self):
		game_update = {
		    'key': self.key,
		    'userX': self.userX.id,
		    'userXname': self.userX.name,
		    'userXReady': self.userX_ready,
		    'userO': '' if not self.userO else self.userO.id,
		    'userOname': '' if not self.userO else self.userO.name,
		    'userOReady': self.userO_ready,
		    'seq': self.seq,
		    'state': self.state,
		    'time_stamp': time.time()
		}

		if self.winner is not None:
			game_update["winner"] = self.winner

		for piece in self.all_piece_ids:
			game_update[piece] = getattr(self, piece)

		return json.dumps(game_update)

	def move(self, user, from_pos, to_pos):
		logging.info("Request to move from " + from_pos + " to " + to_pos)

		if self.state == STATE_START:
			log_error(self,
			          "Game is in STATE_START. State=" + str(self.state) + ".")
			raise HttpCodeException(403)
		elif self.state != STATE_PLAY:
			logging.warning(
			    "Game is not in STATE_PLAY. State=" + str(self.state) + ".")
			raise HttpCodeException(403)

		if user.id == self.userX.id:
			is_white = True
		elif user.id == self.userO.id:
			is_white = False
		else:
			log_error(self, "User not part of the game tried to move piece.")
			raise HttpCodeException(403)

		pieces = []
		for price_id in self.all_piece_ids:
			pieces.append(getattr(self, price_id))
		b = board.Board(pieces)

		if not b.is_valid_position(from_pos):
			log_error(self, str(from_pos) + " is not a valid position.")
			raise HttpCodeException(400)

		if not b.is_valid_position(to_pos):
			log_error(self, str(to_pos) + " is not a valid position.")
			raise HttpCodeException(400)

		if not b.has_piece(from_pos):
			logging.warning(str(from_pos) + " has no piece.")
			raise HttpCodeException(404)

		if b.is_white(from_pos) != is_white:
			# This happens when a user just barely misses a dodge.
			logging.warning("User tried to move the other player's piece: " +
			                str(b.piece(from_pos)) + ".")
			raise HttpCodeException(403)

		if not b.is_valid_move(from_pos, to_pos):
			logging.warning("Not valid to move " + b.piece_name(from_pos) +
			                " from " + from_pos + " to " + to_pos)
			# We don't return an error here because this happens all the time when the
			# users click in the game.
			return False

		has_moved = False
		for piece_id in self.all_piece_ids:
			state = getattr(self, piece_id)
			if len(state) == 0:
				continue

			piece = Piece(state)
			if not piece.moving and piece.pos == from_pos:
				piece.move(to_pos, time.time())
				setattr(self, piece_id, piece.state())
				has_moved = True
				logging.info("Moved " + str(piece) + " from " + from_pos +
				             " to " + piece.pos)
				break

		assert has_moved

		self.put()
		return True

	def put(self):
		if self.state == STATE_PLAY or self.state == STATE_GAMEOVER:
			self.seq += 1

	def randomize(self):
		if self.state != STATE_START:
			log_error(self, "Can only randomize in STATE_START.")
			raise HttpCodeException(403)

		for i in range(8):
			j = random.randint(i, 7)
			if i != j:
				p1 = Piece(getattr(self, "p" + str(i)))
				p2 = Piece(getattr(self, "p" + str(j)))
				p1.pos, p2.pos = p2.pos, p1.pos
				setattr(self, "p" + str(i), p1.state())
				setattr(self, "p" + str(j), p2.state())

				p1 = Piece(getattr(self, "p" + str(16 + i)))
				p2 = Piece(getattr(self, "p" + str(16 + j)))
				p1.pos, p2.pos = p2.pos, p1.pos
				setattr(self, "p" + str(16 + i), p1.state())
				setattr(self, "p" + str(16 + j), p2.state())

		self.put()

	async def send_update(self):
		message = self.get_game_message()
		tasks = []
		for ws in self.observers:
			if not ws.closed:
				tasks.append(ws.send_str(message))
		await asyncio.gather(*tasks)

	async def set_ready(self, user_id, ready):
		logging.info("set_ready(): user_id      =" + user_id)
		logging.info("set_ready(): userX.user.id=" + self.userX.id)
		if self.userO is not None:
			logging.info("set_ready(): userO.user.id=" + self.userO.id)

		if user_id == self.userX.id:
			self.userX_ready = True if int(ready) else False
		elif self.userO.id and user_id == self.userO.id:
			self.userO_ready = True if int(ready) else False
		else:
			raise HttpCodeException(403)

		if self.userO_ready and self.userX_ready:
			self.state = STATE_PLAY
			await self.send_update()
			logging.info("Both players ready. Starting.")

		self.put()

	def update(self):
		self.captured_positions_during_init = set()

		# Update pieces two times to be able to move from moving → sleeping
		# and then sleeping → normal.
		current_time = time.time()
		if self.debug_no_time:
			# Advance time a lot to make all updates happen.
			current_time += 365 * 24 * 60 * 60
		self._finish_all_moves(current_time)
		self._update_pieces(current_time)
		self._update_pieces(current_time)

		# Check to see if the kings are still around.
		self.winner = None
		if self.state != STATE_GAMEOVER:
			whiteKing = self.p4
			blackKing = self.p20

			if whiteKing == "":
				self.state = STATE_GAMEOVER
				self.winner = BLACK
			elif blackKing == "":
				self.state = STATE_GAMEOVER
				self.winner = WHITE

	def _finish_move(self, piece_id, piece, current_time):

		captured = False
		for piece_id2 in self.all_piece_ids:
			if piece_id2 != piece_id:
				state = getattr(self, piece_id2)
				if len(state) == 0:
					continue
				piece2 = Piece(state)

				if piece.pos == piece2.pos:
					if piece.color == piece2.color:
						log_error(self,
						          str(piece) + " and " + str(piece2) +
						          " occupy the same square.")
						raise HttpCodeException(500)

					# Pieces occupy the same square. If the other piece is not
					# moving, it is captured.

					if not piece2.moving:
						# The other piece is not moving. This case is easy.
						assert not captured
						self._capture(piece_id2, piece2)
						captured = True

					# Otherwise, we look to see if the other piece already has arrived.
					elif piece2.end_time <= current_time:
						assert not captured
						captured = True
						# The piece arriving first is captured.
						if piece.end_time < piece2.end_time:
							self._capture(piece_id, piece)
						else:
							self._capture(piece_id2, piece2)

	def _capture(self, piece_id, piece):
		logging.info(str(piece) + " at " + piece.pos + " is captured.")
		self.captured_positions_during_init.add(piece.pos)
		setattr(self, piece_id, "")

	def _finish_all_moves(self, current_time):
		"""Performs all captures, but does not do any transitions to sleeping."""
		for piece_id in self.all_piece_ids:
			state = getattr(self, piece_id)
			if len(state) == 0:
				continue
			piece = Piece(state)
			if piece.moving:
				if piece.end_time <= current_time:
					self._finish_move(piece_id, piece, current_time)

	def _update_pieces(self, current_time):
		"""Performs piece state transitions."""
		for piece_id in self.all_piece_ids:
			state = getattr(self, piece_id)
			if len(state) == 0:
				continue
			piece = Piece(state)

			if piece.moving:
				if piece.end_time <= current_time:
					piece.sleep()
					setattr(self, piece_id, piece.state())
			elif piece.sleeping:
				if piece.end_time <= current_time:
					piece.static()
					setattr(self, piece_id, piece.state())


class RecentGamesList:
	def __init__(self, joinable_games, observable_games, returnable_games):
		self.joinable_games = joinable_games
		self.observable_games = observable_games
		self.returnable_games = returnable_games

	def html(self, games, exclude=None):
		text = ""
		for key, name in games:
			if key != exclude:
				text += """<a href="/?g=%s">%s</a><br />\n""" % (key, name)
		return text

	def joinable_html(self, exclude=None):
		return self.html(self.joinable_games, exclude)

	def observable_html(self, exclude=None):
		return self.html(self.observable_games, exclude)

	def returnable_html(self, exclude=None):
		return self.html(self.returnable_games, exclude)


class GameManager:
	def __init__(self):
		self._games = {}

	def new(self, user, key=None):
		# Use this in Python 3.6+
		# key = secrets.token_hex(128)
		if not key:
			key = os.urandom(8).hex()
		game = Game(key)
		game.userX = user

		self._games[key] = game
		return game, key

	def get(self, key):
		game = self._games.get(key, None)
		if not game:
			return None
		game.update()
		return game

	def get_recent(self, user, exclude_key=None):
		too_old_games = []
		for key, game in self._games.items():
			if (game.creation_time <=
			    datetime.datetime.now() - datetime.timedelta(minutes=60)):
				too_old_games.append(key)
		for key in too_old_games:
			del self._games[key]

		all_games = list(self._games.values())
		all_games.sort(key=lambda g: g.creation_time, reverse=True)

		joinable_games = []
		observable_games = []
		returnable_games = []

		for game in all_games[:20]:
			if (game.creation_time <=
			    datetime.datetime.now() - datetime.timedelta(minutes=2)):
				continue
			key = game.key

			if game.userO:
				name = (game.userX.name + " vs. " + game.userO.name)
			else:
				name = game.userX.name

			if game.userX.id == user.id or (game.userO is not None
			                                and game.userO.id == user.id):
				# Do not offer to rejoin a game the player has been part of without
				# anyone else.
				if game.userO:
					returnable_games.append((key, name))
			elif not game.userO:
				# This is a game created by someone else which no one
				# has joined yet.
				joinable_games.append((key, name))
			else:
				# This is a game with two other players.
				observable_games.append((key, name))

			logging.info("Found game " + name + " (" + key + ") created at " +
			             str(game.creation_time) + ".")
		return RecentGamesList(joinable_games, observable_games,
		                       returnable_games)
