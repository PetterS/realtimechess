import math
import re
import time

from constants import *

MOVING_PATTERN = re.compile(r"M,(\d+\.?\d*),([A-H][1-8])")


def parseMovingPatternMatch(match):
	assert (match is not None)

	end_time, pos = float(match.group(1)), match.group(2)
	return end_time, pos


def createMovingPattern(end_time, pos):
	return "M," + str(end_time) + "," + pos


SLEEPING_PATTERN = re.compile(r"S,(\d+\.?\d*),([A-H][1-8])")


def parseSleepingPatternMatch(match):
	assert (match is not None)

	end_time, pos = float(match.group(1)), match.group(2)
	return end_time, pos


def createSleepingPattern(end_time, pos):
	return "S," + str(end_time) + "," + pos


def action_from_state(state):
	try:
		color_type, action = state.split(";")
	except ValueError:
		import logging
		logging.error("STATE=" + state)
	return action


def coord(s):
	if len(s) != 2:
		return None, None
	letter = ord(s[0]) - ord('A')
	number = int(s[1]) - 1
	if number < 0 or number >= 8:
		return None, None
	if letter < 0 or letter >= 8:
		return None, None
	return letter, number


def distance(from_pos, to_pos):
	fa, fi = coord(from_pos)
	ta, ti = coord(to_pos)
	return math.sqrt((fa - ta)**2 + (fi - ti)**2)


class Piece:
	def __init__(self, state):
		color_type, action = state.split(";")
		self.color, self.type = color_type.split(",")
		self.color = int(self.color)
		self.type = int(self.type)

		moving_match = MOVING_PATTERN.match(action)
		if moving_match is None:
			self.moving = False
			sleeping_match = SLEEPING_PATTERN.match(action)
			if sleeping_match is None:
				self.pos = action
				self.sleeping = False
			else:
				self.end_time, self.pos = parseSleepingPatternMatch(
				    sleeping_match)
				self.sleeping = True
		else:
			self.end_time, self.pos = parseMovingPatternMatch(moving_match)
			self.moving = True
			self.sleeping = False

		assert (not self.sleeping or not self.moving)

	def state(self):
		repr = str(self.color) + "," + str(self.type)
		repr += ";"
		if self.moving:
			repr += createMovingPattern(self.end_time, self.pos)
		elif self.sleeping:
			repr += createSleepingPattern(self.end_time, self.pos)
		else:
			repr += self.pos
		return repr

	def move(self, to_pos, current_time):
		seconds_to_move = distance(self.pos, to_pos) / SQUARES_PER_SECOND
		self.end_time = current_time + seconds_to_move
		self.pos = to_pos
		self.moving = True
		self.sleeping = False

		a, i = coord(to_pos)
		# Promotion check.
		if self.type == PAWN and ((self.color == WHITE and i == 7) or
		                          (self.color == BLACK and i == 0)):
			self.type = QUEEN

	def sleep(self):
		assert (self.moving)
		self.end_time += SLEEPING_TIME
		self.moving = False
		self.sleeping = True

	def static(self):
		self.end_time = None
		self.moving = False
		self.sleeping = False

	def __str__(self):
		s = ""
		if self.color == WHITE:
			s += "White "
		elif self.color == BLACK:
			s += "Black "
		else:
			assert (False)

		if self.type == ROOK:
			s += "rook"
		elif self.type == KNIGHT:
			s += "knight"
		elif self.type == BISHOP:
			s += "bishop"
		elif self.type == KING:
			s += "king"
		elif self.type == QUEEN:
			s += "queen"
		elif self.type == PAWN:
			s += "pawn"
		else:
			assert (False)

		return s

	def __repr__(self):
		return "<" + str(self) + ">"
