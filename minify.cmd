py -2 constants.py
rem node uglifyjs -o game/game.min.js game.js
rem node uglifyjs -o game/constants.min.js constants.js

cp game.js game/game.min.js
cp constants.js game/constants.min.js

