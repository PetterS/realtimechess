#!/usr/bin/env python3

import pytest
import subprocess
import sys


def check_for_modifications(message):
	run = subprocess.run(["git", "ls-files", "-m"], stdout=subprocess.PIPE)
	if len(run.stdout) > 0:
		print("\n" + message)
		sys.exit(1)


if __name__ == "__main__":
	check_for_modifications(
	    "There are local modifications. Please stage them.")

	subprocess.run(
	    [
	        sys.executable, "-m", "yapf", "--recursive", "--in-place",
	        "--parallel", "-vv", "."
	    ],
	    check=True)
	check_for_modifications("Python formatter made modifications.")

	JS_FILES = ["game/game.js"]
	subprocess.run(
	    ["prettier", "--write", "--loglevel", "log"] + JS_FILES,
	    check=True,
	    shell=True)
	check_for_modifications("Javascript formatter made modifications.")

	subprocess.run(["eslint"] + JS_FILES, check=True, shell=True)

	pytest.main()

	print("\nPresubmit OK")
