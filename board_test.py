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


if __name__ == '__main__':
	unittest.main()
