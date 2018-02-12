#!/usr/bin/python3
import threading

from integration_tests import User


def run_games_indefinitely():
	user1 = User("integration-user1")
	user2 = User("integration-user2")
	while True:
		user1.new_game()
		user2.join_game(user1)
		user1.call("ready", {"ready": 1})
		user2.call("ready", {"ready": 1})

		user1.disable_time()

		user1.move("B1", "C3")
		user1.move("C3", "D5")
		user1.move("D5", "C7")
		user1.move("C7", "E8")
		user1.call("ping")

		user2.call("newgame")
		user2.call("ready", {"ready": 1})
		user1.call("ready", {"ready": 1})

		user1.disable_time()
		user1.move("E2", "E4")
		user1.move("E4", "E5")
		user1.move("E5", "E6")
		user1.move("E6", "F7")
		user1.move("F7", "E8")
		user1.call("ping")

		user1.call("newgame")
		user1.call("ready", {"ready": 1})
		user2.call("ready", {"ready": 1})
		user1.disable_time()
		user2.move("E7", "E5")
		user2.move("D8", "H4")
		user2.move("H4", "F2")
		user2.move("F2", "E1")
		user2.call("ping")


if __name__ == "__main__":
	num_games = 10
	threads = []
	for i in range(num_games):
		t = threading.Thread(target=run_games_indefinitely)
		t.start()
		threads.append(t)

	threads[0].join()
