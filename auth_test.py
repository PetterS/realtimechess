from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

import realtimechess


class TestAuthFailures(AioHTTPTestCase):
	async def get_application(self):
		return realtimechess.make_app(True)

	@unittest_run_loop
	async def test_authenticated_checks_logged_in(self):
		response = await self.client.post("/newgame", data={})
		assert response.status == 403

	@unittest_run_loop
	async def test_login_needs_name(self):
		response = await self.client.post("/anonymous_login", data={})
		assert response.status == 400
		assert "Need name" in await response.text()

	@unittest_run_loop
	async def test_login_invalid_name(self):
		response = await self.client.post(
		    "/anonymous_login", data={
		        "name": "as-d%!¤"
		    })
		assert response.status == 400
		assert "Invalid name" in await response.text()

	@unittest_run_loop
	async def test_valid_password_but_user_not_present(self):
		cookies = {}
		cookies["name"] = "Petter"
		cookies["password"] = self.app["user_manager"]._password("Petter")
		self.client.session.cookie_jar.update_cookies(cookies)
		response = await self.client.get("/")
		assert response.status == 200
		assert "/?g=" in str(response.url)

	@unittest_run_loop
	async def test_invalid_password(self):
		cookies = {}
		cookies["name"] = "Petter2"
		cookies["password"] = "xyz"
		self.client.session.cookie_jar.update_cookies(cookies)
		response = await self.client.get("/")
		assert response.status == 200
		# Redirected to login page.
		assert "/loginpage" in str(response.url)

	@unittest_run_loop
	async def test_user_already_exists(self):
		data = {"name": "Petter3"}
		response = await self.client.post("/anonymous_login", data=data)
		assert response.status == 200

		self.app["user_manager"].unsafe_debug = False
		self.client.session.cookie_jar.clear()
		response = await self.client.post("/anonymous_login", data=data)
		self.app["user_manager"].unsafe_debug = True
		assert response.status == 401


class TestNoDebugFailures(AioHTTPTestCase):
	async def get_application(self):
		return realtimechess.make_app(False)

	@unittest_run_loop
	async def test_setdebug_not_present(self):
		response = await self.client.post("/setdebug", data={})
		assert response.status == 404
