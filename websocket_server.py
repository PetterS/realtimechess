#!/usr/bin/env python

import asyncio
import datetime
import random
import websockets


async def time(websocket, path):
	while True:
		now = datetime.datetime.utcnow().isoformat() + 'Z'
		try:
			await websocket.send(now)
		except:
			print("Could not send.")
			return
		await asyncio.sleep(random.random() * 3)


start_server = websockets.serve(time, '127.0.0.1', 5678)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
