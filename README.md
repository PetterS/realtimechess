# Real-time Chess
In **Real-time Chess** (or [**Kung-Fu Chess**](https://en.wikipedia.org/wiki/Kung-Fu_Chess), **Ninja Chess**), all pieces can be moved simultaneously, but there is a short cool-down afterwards. This is a very fun multi-player game, completely different from regular chess!

This repository contains a Python server that hosts real-time Chess games.

## Requirements
Python 3.5+ and asyncio. 

If you want to run the server behind a proxy (locally works fine), it must support websockets.

## Usage
    $ python3 realtimechess.py run
Then tell all players to go to http://<your ip>:8080/

## Testing
        $ python3 realtimechess.py debug
        $ python3 integration_tests.py
        
## Contributions
Contributions are welcome!
