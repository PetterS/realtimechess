import unittest

import board
import constants


class TestBoard(unittest.TestCase):
	def test_single_static_piece(self):
		b = board.Board(["2,5;B5"])

		p = b.state[1][4]
		self.assertEqual(p.color, constants.BLACK)
		self.assertEqual(p.pos, "B5")
		self.assertEqual(p.type, constants.KING)
		self.assertFalse(b.moving[constants.BLACK][1][4])

	def test_single_sleeping_piece(self):
		b = board.Board(["1,6;S,1518694394.674937,B4"])

		p = b.state[1][3]
		self.assertEqual(p.color, constants.WHITE)
		self.assertEqual(p.pos, "B4")
		self.assertEqual(p.type, constants.PAWN)
		self.assertLess(abs(1518694394.674937 - p.end_time), 1e-6)
		self.assertFalse(b.moving[constants.WHITE][1][3])

	def test_single_moving_piece(self):
		b = board.Board(["1,6;M,1518694394.674937,B4"])
		self.assertIs(b.state[1][4], None)
		self.assertTrue(b.moving[constants.WHITE][1][3])


class TestIsValidMove(unittest.TestCase):
	def test_ok(self):
		b = board.Board(["2,5;B5"])
		self.assertTrue(b.is_valid_move("B5", "B6"))

	def test_invalid_pos(self):
		b = board.Board(["2,5;B5"])
		self.assertFalse(b.is_valid_move("B5", "B6s"))
		self.assertFalse(b.is_valid_move("B55", "B6"))
		self.assertFalse(b.is_valid_move("Z5", "B6"))

	def test_same_pos(self):
		b = board.Board(["2,5;B5"])
		self.assertFalse(b.is_valid_move("B5", "B5"))

	def test_no_piece(self):
		b = board.Board(["2,5;B5"])
		self.assertFalse(b.is_valid_move("A1", "A2"))

	def test_sleeping(self):
		b = board.Board(["2,5;S,1518694394.674937,B5"])
		self.assertFalse(b.is_valid_move("B5", "B6"))

	def test_moving(self):
		b = board.Board(["2,5;M,1518694394.674937,B5"])
		self.assertFalse(b.is_valid_move("B5", "B6"))

	def test_rook_ok(self):
		b = board.Board(["2,1;B5"])
		self.assertTrue(b.is_valid_move("B5", "B8"))

	def test_rook_diagonal(self):
		b = board.Board(["2,1;B5"])
		self.assertFalse(b.is_valid_move("B5", "C6"))

	def test_rook_block(self):
		b = board.Board(["2,1;B5", "2,1;B7"])
		self.assertFalse(b.is_valid_move("B5", "B8"))

	def test_bishop_ok(self):
		b = board.Board(["2,3;B5"])
		self.assertTrue(b.is_valid_move("B5", "D7"))

	def test_bishop_straight(self):
		b = board.Board(["2,3;B5"])
		self.assertFalse(b.is_valid_move("B5", "B7"))

	def test_bishop_block(self):
		b = board.Board(["2,3;B5", "2,1;C6"])
		self.assertFalse(b.is_valid_move("B5", "D7"))

	def test_queen_ok_diagonal(self):
		b = board.Board(["2,4;B5"])
		self.assertTrue(b.is_valid_move("B5", "D7"))

	def test_queen_ok_straight(self):
		b = board.Board(["2,4;B5"])
		self.assertTrue(b.is_valid_move("B5", "B7"))

	def test_queen_irregular(self):
		b = board.Board(["2,4;B5"])
		self.assertFalse(b.is_valid_move("B5", "C7"))

	def test_queen_block(self):
		b = board.Board(["2,4;B5", "2,1;C6"])
		self.assertFalse(b.is_valid_move("B5", "D7"))

	def test_king_ok(self):
		b = board.Board(["2,5;D5"])
		self.assertTrue(b.is_valid_move("D5", "D6"))
		self.assertTrue(b.is_valid_move("D5", "D4"))
		self.assertTrue(b.is_valid_move("D5", "C4"))
		self.assertTrue(b.is_valid_move("D5", "E6"))

	def test_king_too_far(self):
		b = board.Board(["2,5;D5"])
		self.assertFalse(b.is_valid_move("D5", "D7"))

	def test_knight_ok(self):
		b = board.Board(["2,2;D5"])
		self.assertTrue(b.is_valid_move("D5", "C7"))
		self.assertTrue(b.is_valid_move("D5", "E7"))
		self.assertTrue(b.is_valid_move("D5", "F4"))
		self.assertTrue(b.is_valid_move("D5", "F6"))

	def test_knight_invalid(self):
		b = board.Board(["2,2;D5"])
		self.assertFalse(b.is_valid_move("D5", "D7"))

	def test_white_pawn_move_start(self):
		b = board.Board(["1,6;D2"])
		self.assertTrue(b.is_valid_move("D2", "D3"))
		self.assertTrue(b.is_valid_move("D2", "D4"))

		self.assertFalse(b.is_valid_move("D2", "D1"))
		self.assertFalse(b.is_valid_move("D2", "E3"))

	def test_black_pawn_move_start(self):
		b = board.Board(["2,6;D7"])
		self.assertTrue(b.is_valid_move("D7", "D6"))
		self.assertTrue(b.is_valid_move("D7", "D5"))

		self.assertFalse(b.is_valid_move("D7", "D8"))
		self.assertFalse(b.is_valid_move("D7", "E6"))

	def test_white_pawn_capture(self):
		b = board.Board(["1,6;D2", "1,6;E3"])
		self.assertFalse(b.is_valid_move("D2", "E3"))

	def test_black_pawn_capture(self):
		b = board.Board(["2,6;D7", "2,6;E6"])
		self.assertFalse(b.is_valid_move("D7", "E6"))

	def test_invalid_type(self):
		b = board.Board(["2,12;D5"])
		self.assertFalse(b.is_valid_move("D5", "D6"))


if __name__ == '__main__':
	unittest.main()
