#!/usr/bin/python3
import re

# The amount of time pieces have to wait before moving again.
SLEEPING_TIME = 3.0

# Speed at which pieces travel.
SQUARES_PER_SECOND = 1.0

STATE_START = 0
STATE_PLAY = 2
STATE_GAMEOVER = 3

NONE = -1
WHITE = 1
BLACK = 2

ROOK = 1
KNIGHT = 2
BISHOP = 3
QUEEN = 4
KING = 5
PAWN = 6

SECONDS_PER_STONE = 1.0
GO_WIN_RATIO = 0.5

if __name__ == "__main__":  # pragma: no cover
	# Convert to Javascript as well.

	constant_definition = re.compile(r"^(\w+) += +(.+)$")
	vars = {}
	for line in open(__file__, "r"):
		match = constant_definition.match(line)
		if match:
			vars[match.group(1)] = match.group(2)

	with open("game/constants.js", "w") as f:
		f.write("// Compiled from constants.py.\n\n")
		for key, val in sorted(vars.items()):
			f.write("var " + key + " = " + val + ";\n")
