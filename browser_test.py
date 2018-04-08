#!/usr/bin/python3

import asyncio
import functools
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


class AsyncBrowser:
	"""Runs Chrome and provides async methods for concurrency."""

	def __init__(self):
		self.loop = asyncio.get_event_loop()
		self.driver = None

	def __del__(self):
		self.stop()

	async def start(self):
		"""Starts Chrome."""
		caps = DesiredCapabilities.CHROME
		caps['loggingPrefs'] = {'browser': 'ALL'}
		self.driver = await self._call(
		    selenium.webdriver.Chrome, desired_capabilities=caps)

	def stop(self) -> None:
		if self.driver is not None:
			self.driver.quit()
			self.driver = None

	async def get(self, *args, **kwargs):
		return await self._call(self.driver.get, *args, **kwargs)

	async def _call(self, func, *args, **kwargs):
		"""Calls the function asynchronously in a thread pool."""
		call = functools.partial(func, *args, **kwargs)
		return await self.loop.run_in_executor(None, call)


class User(AsyncBrowser):
	"""A user with its own instance of Chrome running."""

	def __init__(self, name: str):
		super().__init__()
		self.name = name

	async def login(self):
		"""Creates an account for the user user."""
		await self.get("http://localhost:8080/")

		# Submit the name in the form.
		name_field = self.driver.find_element_by_name("name")
		name_field.send_keys(self.name)
		form = self.driver.find_element_by_tag_name("form")
		await self._call(form.submit)

		# We have been redirected to the game page. Get
		# the game ID.
		self.game = re.match(r".*/\?g=([0-9a-f]+)$",
		                     self.driver.current_url).group(1)
		return self.game

	async def join(self, game):
		"""Joins the specified game."""
		await self.get("http://localhost:8080/?g={}".format(game))

	def set_ready(self) -> None:
		check_box = self.driver.find_element_by_id("isReadyCheckBox")
		WebDriverWait(self.driver, 10).until(
		    expected_conditions.visibility_of(check_box))
		check_box.click()

	def check_logs(self) -> None:
		for line in self.driver.get_log("browser"):
			print(self.name, line["level"], line["message"])
			assert line["level"] == "INFO"

	def ignore_logs(self) -> None:
		self.driver.get_log("browser")

	def move(self, piece_id: str, square_id: str) -> None:
		piece = self.driver.find_element_by_id(piece_id)
		square = self.driver.find_element_by_id(square_id)
		ActionChains(self.driver).drag_and_drop(piece, square).perform()

	def wait_until_disappeared(self, id):
		WebDriverWait(self.driver, 10).until(
		    expected_conditions.invisibility_of_element_located((By.ID, id)))


async def browser_test():
	"""Starts a game between two users.user1

	Plays until the first piece is captured and waits for it to disappear.
	"""
	user1 = User("Webuser1")
	user2 = User("Webuser2")
	await asyncio.gather(user1.start(), user2.start())

	try:
		game, _ = await asyncio.gather(user1.login(), user2.login())
		await user2.join(game)

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
		user1.stop()
		user2.stop()


if __name__ == "__main__":
	# Start game server.
	server = subprocess.Popen([
	    sys.executable,
	    os.path.join(os.path.dirname(__file__), "realtimechess.py"), "debug"
	])
	try:
		asyncio.get_event_loop().run_until_complete(browser_test())
	finally:
		server.kill()

	print("\n\nOK :-D")
