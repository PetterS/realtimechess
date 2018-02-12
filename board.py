from constants import *
from protocol import Piece, coord


class Board:
	def __init__(self, pieces):
		self.state = []
		self.moving = {}
		self.moving[WHITE] = []
		self.moving[BLACK] = []
		for i in range(8):
			self.state.append([None] * 8)
			self.moving[WHITE].append([False] * 8)
			self.moving[BLACK].append([False] * 8)

		for pi in range(len(pieces)):
			if pieces[pi] == "":
				continue
			piece = Piece(pieces[pi])
			a, i = coord(piece.pos)
			if piece.moving:
				assert (not self.moving[piece.color][a][i])
				self.moving[piece.color][a][i] = True
			else:
				assert (self.state[a][i] is None)
				self.state[a][i] = piece

	def is_valid_position(self, pos):
		a, i = coord(pos)
		return a is not None

	def has_piece(self, pos):
		a, i = coord(pos)
		return self.state[a][i] is not None

	def piece(self, pos):
		a, i = coord(pos)
		return self.state[a][i]

	def piece_name(self, pos):
		a, i = coord(pos)
		return str(self.state[a][i])

	def is_white(self, pos):
		a, i = coord(pos)
		return self.state[a][i].color == WHITE

	def clear_path(self, fa, fi, ta, ti):
		da = ta - fa
		di = ti - fi
		if da != 0:
			da = int(da / abs(da))
		if di != 0:
			di = int(di / abs(di))

		i = fi
		a = fa
		while True:
			i += di
			a += da
			if a == ta and i == ti:
				break
			if not self.empty_or_moving(a, i):
				return False

		return True

	def empty(self, a, i):
		"""Square is empty and no piece is on its way there."""
		state = self.state[a][i]
		return state is None

	def opposing_standing(self, a, i, own_color):
		"""Square has an enemy standing in the square."""
		state = self.state[a][i]
		if state is None:
			return False
		return state.color != own_color and not state.moving

	def empty_or_opposing(self, a, i, own_color):
		"""Square is empty or occupied by the opposing color or
       a piece of the opposing color is on its way there."""
		state = self.state[a][i]
		if state is None:
			return True
		return state.color != own_color

	def empty_or_moving(self, a, i):
		"""Square is empty or have pieces moving there. No piece
       is standing there."""
		state = self.state[a][i]
		if state is None:
			return True
		return state.moving

	def is_valid_move(self, from_pos, to_pos):
		fa, fi = coord(from_pos)
		ta, ti = coord(to_pos)
		if fa is None or ta is None:
			return False
		if fa == ta and fi == ti:
			return False

		piece = self.state[fa][fi]
		if not piece:
			return False
		if piece.moving:
			return False
		if piece.sleeping:
			return False

		# Is a piece of the same color moving here?
		if self.moving[piece.color][ta][ti]:
			return False

		if piece.type == PAWN:
			d = 1
			if piece.color == BLACK:
				d = -1

			if fa == ta and ti - fi == d and self.empty(ta, ti):
				return True

			if fa == ta and self.empty(fa, fi + d) and self.empty(ta, ti):
				if piece.color == WHITE and fi == 1 and ti == 3:
					return True
				if piece.color == BLACK and fi == 6 and ti == 4:
					return True

			# Capture
			if abs(fa - ta) == 1 and ti - fi == d and self.opposing_standing(
			    ta, ti, piece.color):
				return True

			return False

		elif piece.type == ROOK:
			if fa != ta and fi != ti:
				return False
			if not self.clear_path(fa, fi, ta, ti):
				return False
			return self.empty_or_opposing(ta, ti, piece.color)

		elif piece.type == BISHOP:
			if abs(fa - ta) != abs(fi - ti):
				return False
			if not self.clear_path(fa, fi, ta, ti):
				return False
			return self.empty_or_opposing(ta, ti, piece.color)

		elif piece.type == QUEEN:
			if fa != ta and fi != ti and abs(fa - ta) != abs(fi - ti):
				return False
			if not self.clear_path(fa, fi, ta, ti):
				return False
			return self.empty_or_opposing(ta, ti, piece.color)

		elif piece.type == KING:
			if abs(fa - ta) > 1 or abs(fi - ti) > 1:
				return False
			return self.empty_or_opposing(ta, ti, piece.color)

		elif piece.type == KNIGHT:
			da = abs(fa - ta)
			di = abs(fi - ti)
			if (da != 1 and da != 2) or (di != 1 and di != 2) or (
			    da == 1 and di != 2) or (da == 2 and di != 1):
				return False
			return self.empty_or_opposing(ta, ti, piece.color)

		else:
			return False
