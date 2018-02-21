#!/usr/bin/python3

import os
import re
import subprocess
import sys

import selenium.webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions


class User:
	"""A user with its own instance of Chrome running."""

	def __init__(self, name: str):
		self.name = name

	def connect(self, game=None) -> str:
		"""Starts Chrome and logs in.

		Optionally joins the specified game.
		"""

		caps = DesiredCapabilities.CHROME
		caps['loggingPrefs'] = {'browser': 'ALL'}
		# Start browser
		self.driver = selenium.webdriver.Chrome(desired_capabilities=caps)

		# This will redirect to the login page.
		if game:
			self.driver.get("http://localhost:8080/?g={}".format(game))
		else:
			self.driver.get("http://localhost:8080/")
		# Submit the name in the form.
		name_field = self.driver.find_element_by_name("name")
		name_field.send_keys(self.name)
		self.driver.find_element_by_tag_name("form").submit()
		# We have been redirected to the game page. Get
		# the game ID.
		self.game = re.match(r".*/\?g=([0-9a-f]+)$",
		                     self.driver.current_url).group(1)

		self.ignore_logs()
		return self.game

	def set_ready(self) -> None:
		check_box = self.driver.find_element_by_id("isReadyCheckBox")
		WebDriverWait(self.driver, 10).until(
		    expected_conditions.visibility_of(check_box))
		check_box.click()

	def check_logs(self) -> None:
		for line in self.driver.get_log("browser"):
			print(self.name, line["message"])
			assert line["level"] == "INFO"

	def ignore_logs(self) -> None:
		self.driver.get_log("browser")

	def disconnect(self) -> None:
		self.driver.quit()

	def move(self, piece_id: str, square_id: str) -> None:
		piece = self.driver.find_element_by_id(piece_id)
		square = self.driver.find_element_by_id(square_id)
		ActionChains(self.driver).drag_and_drop(piece, square).perform()

	def wait_until_disappeared(self, id):
		WebDriverWait(self.driver, 10).until(
		    expected_conditions.invisibility_of_element_located((By.ID, id)))


def browser_test():
	"""Starts a game between two users.user1

	Plays until the first piece is captured and waits for it to disappear.
	"""
	user1 = User("Webuser1")
	game = user1.connect()
	user2 = User("Webuser2")
	user2.connect(game)
	try:
		user2.set_ready()
		user1.set_ready()

		# White pawn in front of king.
		user1.move("p12", "E4")
		# Pawn to H5.
		user2.move("p31", "H5")
		# Queen strikes H5.
		user1.move("p3", "H5")

		user1.wait_until_disappeared("p31")
		user2.wait_until_disappeared("p31")

		user1.check_logs()
		user2.check_logs()
	finally:
		user1.disconnect()
		user2.disconnect()


if __name__ == "__main__":
	# Start game server.
	server = subprocess.Popen([
	    sys.executable,
	    os.path.join(os.path.dirname(__file__), "realtimechess.py"), "debug"
	])
	try:
		browser_test()
	finally:
		server.kill()

	print("\n\nOK :-D")
