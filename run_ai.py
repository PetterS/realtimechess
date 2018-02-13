import asyncio
import json
import os
import random
import signal
import urllib.parse
import sys

import aiohttp

import board
import constants
import protocol


class AiPlayer:
	def __init__(self, loop, session, base_url):
		self.loop = loop
		self.session = session
		self.base_url = base_url
		self.name = "AiPlayer-" + os.urandom(2).hex()
		self.game = None
		self.state = constants.STATE_START
		self.ws = None

		self.poll_interval = 1.0
		self.my_color = constants.WHITE
		self.all_piece_ids = []
		for i in range(32):
			self.all_piece_ids.append("p" + str(i))

		self.my_pieces = []
		self.board = None

	async def connect(self):
		login_data = {'name': self.name}
		async with self.session.post(
		    self.base_url + 'anonymous_login', data=login_data) as resp:
			assert resp.status == 200
			print("Logged in as", self.name)
			# We should have been redirected to the game page.
			self.game = resp.url.query.get("g")
			print("Created game", "{}?g={}".format(self.base_url, self.game))

	async def play(self):
		async with self.session.ws_connect(
		    self.base_url + 'websocket?g=' + self.game) as self.ws:
			print("Websocket connected.")

			def callback():
				loop.create_task(self._poll())
				self.loop.call_later(self.poll_interval, callback)

			self.loop.call_soon(callback)

			await self._call("ready", {"ready": 1})
			print("Now ready.")

			async for msg in self.ws:
				if msg.type == aiohttp.WSMsgType.TEXT:
					data = json.loads(msg.data)
					self.state = int(data["state"])

					pieces = []
					for id in self.all_piece_ids:
						pieces.append(data[id])
					self.board = board.Board(pieces)

					self.my_pieces = []
					for a in range(8):
						for i in range(8):
							s = self.board.state[a][i]
							if s is not None and s.color == self.my_color:
								self.my_pieces.append((a, i))

					print(":", end="", flush=True)
				elif msg.type == aiohttp.WSMsgType.CLOSED:
					print("Websocket closed.")
					break
				elif msg.type == aiohttp.WSMsgType.ERROR:
					print("Websocket error.")
					break

	async def _call(self, name, params={}):
		encoded_params = urllib.parse.urlencode(params)
		url = self.base_url + name + "?g=" + self.game + "&" + encoded_params
		async with self.session.post(url) as resp:
			if resp.status == 408:
				# Retry
				return self.call(name, params)
			assert resp.status == 200
			data = await resp.text()
		return data

	async def _call_ws(self, name, params={}):
		encoded_params = urllib.parse.urlencode(params)
		url = self.base_url + name + "?g=" + self.game + "&" + encoded_params
		await self.ws.send_str(url)

	async def _poll(self):
		print(".", end='', flush=True)

		if self.state != constants.STATE_PLAY:
			return

		tasks = []
		for from_a, from_i in self.my_pieces:
			to_a = from_a + random.randint(-1, 1)
			to_i = from_i + random.randint(-1, 1)
			frm = protocol.pos(from_a, from_i)
			to = protocol.pos(to_a, to_i)
			if self.board.is_valid_move(frm, to):
				tasks.append(self._call_ws("move", {"from": frm, "to": to}))
		await asyncio.gather(*tasks)


async def run_ai(loop, url):
	parsed_url = urllib.parse.urlparse(url)
	parsed_url = urllib.parse.ParseResult(parsed_url.scheme, parsed_url.netloc,
	                                      '/', '', '', None)
	base_url = urllib.parse.urlunparse(parsed_url)
	print("Connecting to", url)

	async with aiohttp.ClientSession() as session:
		player = AiPlayer(loop, session, base_url)
		await player.connect()
		await player.play()


if __name__ == '__main__':
	if len(sys.argv) != 2:
		print("Usage:", sys.argv[0], "<URL, e.g. http://localhost:8080>")
		sys.exit(1)
	loop = asyncio.get_event_loop()
	if os.name != "nt":
		loop.add_signal_handler(signal.SIGTERM, loop.stop)

	print("AI started.")
	try:
		loop.run_until_complete(run_ai(loop, sys.argv[1]))
	except KeyboardInterrupt:
		print("KeyboardInterrupt.")
		pass

	loop.close()
	print("AI stopped.")
