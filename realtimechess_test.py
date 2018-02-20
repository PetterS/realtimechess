import json

from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

import constants
import realtimechess


class RealTimeChessTest(AioHTTPTestCase):
	async def get_application(self):
		return realtimechess.make_app(True)

	async def _login(self, name):
		response = await self.client.request(
		    "POST", "/anonymous_login", data={
		        "name": name
		    })
		assert response.status == 200
		game = response.url.query.get("g")
		return game

	@unittest_run_loop
	async def test_redirect_to_loginpage(self):
		response = await self.client.request("GET", "/")
		assert response.status == 200
		text = await response.text()
		self.assertIn("Choose your name", text)

	@unittest_run_loop
	async def test_websocket_ping(self):
		game = await self._login("test1")
		ws = await self.client.ws_connect("/websocket?g=" + game)
		await ws.send_str("/ping")
		data = json.loads((await ws.receive()).data)
		self.assertEqual(data["state"], constants.STATE_START)
		self.assertEqual(data["userXname"], "test1")
