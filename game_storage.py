import datetime
import json
import logging
import time
import os

import board
from constants import *
from protocol import Piece
from util import HttpCodeException, log_error

games = {}


def new(user, key=None):
	# Use this in Python 3.6+
	# key = secrets.token_hex(128)
	if not key:
		key = os.urandom(8).hex()
	game = Game(key)
	game.userX_id = user.id
	game.userX = user

	games[key] = game
	return game, key


def get(key):
	game = games.get(key, None)
	if not game:
		return None
	game.update()
	return game


class Game():
	"""All the data we store for a game"""

	def set_default(self, var, value):
		if var not in dir(self) or getattr(self, var) is None:
			setattr(self, var, value)

	def get_pieces(self):
		return self.all_piece_ids

	def finish_move(self, piece_id, piece, current_time):

		captured = False
		for piece_id2 in self.get_pieces():
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
						assert (not captured)
						self.capture(piece_id2, piece2)
						captured = True

					# Otherwise, we look to see if the other piece already has arrived.
					elif piece2.end_time <= current_time:
						assert (not captured)
						captured = True
						# The piece arriving first is captured.
						if piece.end_time < piece2.end_time:
							self.capture(piece_id, piece)
						else:
							self.capture(piece_id2, piece2)

	def capture(self, piece_id, piece):
		logging.info(str(piece) + " at " + piece.pos + " is captured.")
		self.captured_positions_during_init.add(piece.pos)
		if piece.type == KING:
			self.game_ended_during_init = True
		setattr(self, piece_id, "")

	def finish_all_moves(self, current_time):
		"""Performs all captures, but does not do any transitions to sleeping."""
		for piece_id in self.get_pieces():
			state = getattr(self, piece_id)
			if len(state) == 0:
				continue
			piece = Piece(state)
			if piece.moving:
				if piece.end_time <= current_time:
					self.finish_move(piece_id, piece, current_time)

	def update_pieces(self, current_time):
		"""Performs piece state transitions."""
		for piece_id in self.get_pieces():
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

	def put(self):
		if self.state == STATE_PLAY or self.state == STATE_GAMEOVER:
			self.seq += 1

	def __init__(self, key):
		self.key = key

		# These are only for deriving the name of the users.
		self.userX = None
		self.userO = None

		# Which users are allowed to play this game.
		self.userX_id = ""
		self.userO_id = ""
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

	def update(self):
		self.captured_positions_during_init = set()
		self.game_ended_during_init = False

		# Update pieces two times to be able to move from moving → sleeping
		# and then sleeping → normal.
		current_time = time.time()
		if self.debug_no_time:
			# Advance time a lot to make all updates happen.
			current_time += 365 * 24 * 60 * 60
		self.finish_all_moves(current_time)
		self.update_pieces(current_time)
		self.update_pieces(current_time)

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


class GameUpdater:
	game = None

	def __init__(self, game):
		self.game = game

	def get_game_dict(self, ping_tag=None):
		gameUpdate = {
		    'key': self.game.key,
		    'userX': self.game.userX_id,
		    'userXname': self.game.userX.name,
		    'userXReady': self.game.userX_ready,
		    'userO': '' if not self.game.userO_id else self.game.userO_id,
		    'userOname': '' if not self.game.userO else self.game.userO.name,
		    'userOReady': self.game.userO_ready,
		    'seq': self.game.seq,
		    'state': self.game.state,
		    'time_stamp': time.time()
		}

		if self.game.winner is not None:
			gameUpdate["winner"] = self.game.winner

		for piece in self.game.get_pieces():
			gameUpdate[piece] = getattr(self.game, piece)

		if ping_tag is not None:
			gameUpdate["ping_tag"] = ping_tag

		return gameUpdate

	def get_game_message(self, ping_tag=None):
		return json.dumps(self.get_game_dict(ping_tag))

	def send_update(self, ping_tag=None):
		message = self.get_game_message(ping_tag)
		for ws in self.game.observers:
			ws.send_str(message)

	def move(self, user, from_pos, to_pos):
		logging.info("Request to move from " + from_pos + " to " + to_pos)

		if self.game.state == STATE_START:
			log_error(
			    self.game,
			    "Game is in STATE_START. State=" + str(self.game.state) + ".")
			raise HttpCodeException(403)
		elif self.game.state != STATE_PLAY:
			logging.warning("Game is not in STATE_PLAY. State=" +
			                str(self.game.state) + ".")
			raise HttpCodeException(403)

		if user.id == self.game.userX_id:
			is_white = True
		elif user.id == self.game.userO_id:
			is_white = False
		else:
			log_error(self.game,
			          "User not part of the game tried to move piece.")
			raise HttpCodeException(403)

		pieces = []
		for i in range(32):
			pieces.append(getattr(self.game, "p" + str(i)))
		b = board.Board(pieces)

		if not b.is_valid_position(from_pos):
			log_error(self.game, str(from_pos) + " is not a valid position.")
			raise HttpCodeException(400)

		if not b.is_valid_position(to_pos):
			log_error(self.game, str(to_pos) + " is not a valid position.")
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
			logging.warning("Not valid token move " + b.piece_name(from_pos) +
			                " from " + from_pos + " to " + to_pos)
			# We don't return an error here because this happens all the time when the
			# users click in the game.
			return False

		pieces = [
		    attr for attr in dir(self.game)
		    if not callable(attr) and re.match("p\\d\\d?", attr)
		]
		has_moved = False
		for piece_id in pieces:
			state = getattr(self.game, piece_id)
			if len(state) == 0:
				continue

			piece = Piece(state)
			if not piece.moving and piece.pos == from_pos:
				piece.move(to_pos, time.time())
				setattr(self.game, piece_id, piece.state())
				has_moved = True
				logging.info("Moved " + str(piece) + " from " + from_pos +
				             " to " + piece.pos)
				break

		assert (has_moved)

		self.game.put()
		return True

	def randomize(self):
		if self.game.state != STATE_START:
			log_error(self.game, "Can only randomize in STATE_START.")
			raise HttpCodeException(403)

		for i in range(8):
			j = random.randint(i, 7)
			if i != j:
				p1 = Piece(getattr(self.game, "p" + str(i)))
				p2 = Piece(getattr(self.game, "p" + str(j)))
				p1.pos, p2.pos = p2.pos, p1.pos
				setattr(self.game, "p" + str(i), p1.state())
				setattr(self.game, "p" + str(j), p2.state())

				p1 = Piece(getattr(self.game, "p" + str(16 + i)))
				p2 = Piece(getattr(self.game, "p" + str(16 + j)))
				p1.pos, p2.pos = p2.pos, p1.pos
				setattr(self.game, "p" + str(16 + i), p1.state())
				setattr(self.game, "p" + str(16 + j), p2.state())

		self.game.put()

	def set_ready(self, user_id, ready):
		logging.info("set_ready(): user_id      =" + user_id)
		logging.info("set_ready(): userX.user_id=" + self.game.userX_id)
		if self.game.userO is not None:
			logging.info("set_ready(): userO.user_id=" + self.game.userO_id)

		if user_id == self.game.userX_id:
			self.game.userX_ready = True if int(ready) else False
		elif self.game.userO_id and user_id == self.game.userO_id:
			self.game.userO_ready = True if int(ready) else False
		else:
			logging.warning("set_ready() from a player not in the game.")
			return

		if self.game.userO_ready and self.game.userX_ready:
			self.game.state = STATE_PLAY
			self.send_update()
			logging.info("Both players ready. Starting.")

		self.game.put()
