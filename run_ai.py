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
		self.last_update_timestamp = 0
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

					self.pieces = []
					pieces_str = []
					for id in self.all_piece_ids:
						pieces_str.append(data[id])
						if data[id]:
							self.pieces.append(protocol.Piece(data[id]))
					self.board = board.Board(pieces_str)

					self.last_update_timestamp = float(data["time_stamp"])
					something_happens_at = 1e100
					self.my_pieces = []
					for piece in self.pieces:
						if piece is not None and piece.color == self.my_color:
							self.my_pieces.append(piece)
							if piece.moving or piece.sleeping:
								something_happens_at = min(
								    something_happens_at, piece.end_time)
					if something_happens_at < 1e100:
						asyncio.ensure_future(
						    self._call_ws_at(something_happens_at + 0.05, "ping"),
						    loop=self.loop)

					print(":", end="", flush=True)
				elif msg.type == aiohttp.WSMsgType.CLOSED:
					print("Websocket closed.")
					break
				elif msg.type == aiohttp.WSMsgType.ERROR:
					print("Websocket error.")
					break

	async def _call_ws_at(self, timestamp, name, params={}):
		delay = timestamp - self.last_update_timestamp
		await asyncio.sleep(delay)
		if timestamp > self.last_update_timestamp:
			await self._call_ws(name, params)

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
		all_moves = self.board.get_possible_moves(self.my_color)
		for frm, all_to in all_moves:
			to = random.choice(all_to)
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
