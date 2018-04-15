import {
	BISHOP,
	BLACK,
	KING,
	KNIGHT,
	PAWN,
	QUEEN,
	ROOK,
	SLEEPING_TIME,
	STATE_GAMEOVER,
	STATE_PLAY,
	STATE_START,
	WHITE
} from "./constants.js";

jQuery.fn.rotate = function(degrees) {
	$(this).css({
		"-webkit-transform": "rotate(" + degrees + "deg)",
		"-moz-transform": "rotate(" + degrees + "deg)",
		"-ms-transform": "rotate(" + degrees + "deg)",
		transform: "rotate(" + degrees + "deg)"
	});
	return $(this);
};

function assert(condition, message) {
	if (!condition) {
		message = message || "Assertion failed";
		throw new Error(message);
	}
}

let sequenceNumber = null;
let state = {
	gameKey: "",
	me: ""
};

let websocket = null;
let pingStartTime = null;

let selectedSquareId = null;

const BLACK_ROOK = "\u265C";
const BLACK_KNIGHT = "\u265E";
const BLACK_BISHOP = "\u265D";
const BLACK_QUEEN = "\u265B";
const BLACK_KING = "\u265A";
const BLACK_PAWN = "\u265F";
const WHITE_ROOK = "\u2656";
const WHITE_KNIGHT = "\u2658";
const WHITE_BISHOP = "\u2657";
const WHITE_QUEEN = "\u2655";
const WHITE_KING = "\u2654";
const WHITE_PAWN = "\u2659";
let pieces = [
	{color: "X", value: WHITE_ROOK},
	{color: "X", value: WHITE_KNIGHT},
	{color: "X", value: WHITE_BISHOP},
	{color: "X", value: WHITE_QUEEN},
	{color: "X", value: WHITE_KING},
	{color: "X", value: WHITE_BISHOP},
	{color: "X", value: WHITE_KNIGHT},
	{color: "X", value: WHITE_ROOK},
	{color: "X", value: WHITE_PAWN},
	{color: "X", value: WHITE_PAWN},
	{color: "X", value: WHITE_PAWN},
	{color: "X", value: WHITE_PAWN},
	{color: "X", value: WHITE_PAWN},
	{color: "X", value: WHITE_PAWN},
	{color: "X", value: WHITE_PAWN},
	{color: "X", value: WHITE_PAWN},
	{color: "O", value: BLACK_ROOK},
	{color: "O", value: BLACK_KNIGHT},
	{color: "O", value: BLACK_BISHOP},
	{color: "O", value: BLACK_QUEEN},
	{color: "O", value: BLACK_KING},
	{color: "O", value: BLACK_BISHOP},
	{color: "O", value: BLACK_KNIGHT},
	{color: "O", value: BLACK_ROOK},
	{color: "O", value: BLACK_PAWN},
	{color: "O", value: BLACK_PAWN},
	{color: "O", value: BLACK_PAWN},
	{color: "O", value: BLACK_PAWN},
	{color: "O", value: BLACK_PAWN},
	{color: "O", value: BLACK_PAWN},
	{color: "O", value: BLACK_PAWN},
	{color: "O", value: BLACK_PAWN}
];

const CLICKED_PIECE_COLOR = "#FFFF44";
const HOVER_SQUARE_COLOR = "#88FF88";
const HOVER_COLLISION_SQUARE_COLOR = "#FF9999";

function updateRemovedPiece(i) {
	// Is the position of this piece the currently selected one?
	if (selectedSquareId !== null && selectedSquareId === pieces[i].pos) {
		// Remove selection.
		$("#" + selectedSquareId).removeAttr("style");
		selectedSquareId = null;
	}

	pieces[i].pos = null;
	const piece = $("#p" + i);
	piece.hide();
	// TODO: Show piece if needed later.
}

function updateStaticPiece(i, pos) {
	pieces[i].pos = pos;
	pieces[i].moving = false;
	pieces[i].sleeping = false;
	pieces[i].rotation = 0.0;

	// Set the correct position of the piece.
	const square = $("#" + pieces[i].pos);
	const offset = square.offset();
	const piece = $("#p" + i);

	// Stop all previous animations.
	piece.stop(true);

	// Allow clicking.
	piece.css("pointer-events", "auto");
	// Allow dragging of owned pieces.
	if (pieces[i].color === state.myColor && state["state"] === STATE_PLAY) {
		piece.draggable("enable");
	} else {
		piece.draggable("disable");
	}

	piece.offset(offset);
	piece.rotate(0);
}

function localTransitionToSleeping(i, endTimeStamp, pos) {
	if (pieces[i].color !== state.myColor) {
		// Not my piece; the other player will take care of this.
		return;
	}

	// Is there another piece in this square?
	for (let j = 0; j < 32; ++j) {
		let capture = false;
		if (i !== j && pos === pieces[j].pos) {
			capture = true;
		}

		const sleepingPattern = /S,(\d+\.?\d*),([A-H][1-8])/g;
		const sleepingMatch = sleepingPattern.exec(pieces[j].pos);
		if (sleepingMatch !== null) {
			const endPos = sleepingMatch[2];
			if (pos === endPos) {
				capture = true;
			}
		}
		if (capture) {
			// We need to let the server resolve this.
			console.log(
				"Piece " + i + " has moved into square occupied by " + j
			);
			sendWebSocketMessage("/ping");
		}
	}
}

function updateSleepingPiece(i, endTimeStamp, pos) {
	pieces[i].pos = pos;
	pieces[i].moving = false;
	pieces[i].sleeping = true;

	// Set the correct position of the piece.
	const square = $("#" + pos);
	const animationTarget = square.offset();
	const piece = $("#p" + i);

	// Stop all previous animations.
	piece.stop(true);

	// Allow clicking.
	piece.css("pointer-events", "auto");
	// Can not be dragged while sleeping.
	piece.draggable("disable");

	// Adjust rotation before and after setting position, to
	// avoid the rotation introducing an offset.
	piece.rotate(0);
	piece.offset(animationTarget);
	piece.rotate(pieces[i].rotation);

	const startRotation = pieces[i].rotation;
	const endRotation = 0.0;

	let duration = SLEEPING_TIME;
	if (endTimeStamp) {
		// We have gotten a time stamp from the server when
		// the sleeping phase should be done.
		duration = endTimeStamp - state["time_stamp"];
	}

	function animationComplete() {
		assert(pieces[i].sleeping);
		updateStaticPiece(i, pos);
	}
	function animationProgress(animation, progress) {
		pieces[i].rotation =
			(1.0 - progress) * startRotation + progress * endRotation;
		piece.rotate(pieces[i].rotation);
	}
	if (duration > 0) {
		piece.animate(animationTarget, {
			duration: 1000 * duration,
			done: animationComplete,
			progress: animationProgress
		});
	} else {
		animationComplete();
	}
}

function updateMovingPiece(i, endTimeStamp, endPos) {
	pieces[i].moving = true;
	pieces[i].sleeping = false;
	pieces[i].pos = endPos;

	// Set the piece moving towards the end square.
	const square = $("#" + endPos);
	const animationTarget = square.offset();
	const piece = $("#p" + i);

	// Stop all previous animations.
	piece.stop(true);

	// Can not be clicked while moving.
	piece.css("pointer-events", "none");

	// Can not be dragged while moving.
	piece.draggable("disable");

	const startRotation = pieces[i].rotation;
	const endRotation = -90.0;

	const duration = endTimeStamp - state["time_stamp"];
	function animationComplete() {
		assert(pieces[i].moving);
		localTransitionToSleeping(i, null, endPos);
		updateSleepingPiece(i, null, endPos);
	}
	function animationProgress(animation, progress) {
		pieces[i].rotation =
			(1.0 - progress) * startRotation + progress * endRotation;
		piece.rotate(pieces[i].rotation);
	}
	if (duration > 0) {
		piece.animate(animationTarget, {
			duration: 1000 * duration,
			done: animationComplete,
			progress: animationProgress
		});
	} else {
		animationComplete();
	}
}

function updateGame() {
	if (!state.userO || state.userO === "") {
		$("#other-player").show();
		$("#gameInformation").show();
		$("#this-game").hide();
		$("#chess_board").hide();
		$("#isReady").hide();
		$("#ping").hide();
		$(".beforeGame").show();
		for (let i = 0; i < 32; ++i) {
			$("#p" + i).hide();
		}
		console.log("No other player.");
	} else {
		$("#other-player").hide();
		$("#gameInformation").hide();
		$("#this-game").show();
		$("#chess_board").show();
		if (state.state === STATE_START && state.myColor !== null) {
			$("#isReady").show();
		}
		$("#ping").show();
		$(".beforeGame").hide();
		for (let i = 0; i < 32; ++i) {
			$("#p" + i).show();
		}
	}

	if (state["state"] === STATE_PLAY) {
		if (state.me === state.userX) {
			$("#topMessage").text(state.userOname);
			$("#bottomMessage").text(state.userXname);
		} else {
			$("#topMessage").text(state.userOname);
			$("#bottomMessage").text(state.userXname);
		}
	}

	for (let i = 0; i < 32; ++i) {
		if (state.hasOwnProperty("p" + i) && state["p" + i] !== "") {
			const newState = state["p" + i];
			let parts = newState.split(";");
			const colorType = parts[0];
			const action = parts[1];

			parts = colorType.split(",");
			const color = parseInt(parts[0]);
			const type = parseInt(parts[1]);
			if (color === WHITE && type === PAWN) {
				pieces[i].color = "X";
				pieces[i].value = WHITE_PAWN;
			} else if (color === WHITE && type === ROOK) {
				pieces[i].color = "X";
				pieces[i].value = WHITE_ROOK;
			} else if (color === WHITE && type === KNIGHT) {
				pieces[i].color = "X";
				pieces[i].value = WHITE_KNIGHT;
			} else if (color === WHITE && type === BISHOP) {
				pieces[i].color = "X";
				pieces[i].value = WHITE_BISHOP;
			} else if (color === WHITE && type === QUEEN) {
				pieces[i].color = "X";
				pieces[i].value = WHITE_QUEEN;
			} else if (color === WHITE && type === KING) {
				pieces[i].color = "X";
				pieces[i].value = WHITE_KING;
			} else if (color === BLACK && type === PAWN) {
				pieces[i].color = "O";
				pieces[i].value = BLACK_PAWN;
			} else if (color === BLACK && type === ROOK) {
				pieces[i].color = "O";
				pieces[i].value = BLACK_ROOK;
			} else if (color === BLACK && type === KNIGHT) {
				pieces[i].color = "O";
				pieces[i].value = BLACK_KNIGHT;
			} else if (color === BLACK && type === BISHOP) {
				pieces[i].color = "O";
				pieces[i].value = BLACK_BISHOP;
			} else if (color === BLACK && type === QUEEN) {
				pieces[i].color = "O";
				pieces[i].value = BLACK_QUEEN;
			} else if (color === BLACK && type === KING) {
				pieces[i].color = "O";
				pieces[i].value = BLACK_KING;
			} else {
				errorMessage("Color and type not found.");
			}
			const piece = $("#p" + i);
			piece.text(pieces[i].value);

			const movingPattern = /M,(\d+\.?\d*),([A-H][1-8])/g;
			const sleepingPattern = /S,(\d+\.?\d*),([A-H][1-8])/g;
			const movingMatch = movingPattern.exec(action);
			if (movingMatch !== null) {
				const timeStamp = parseFloat(movingMatch[1]);
				const endPos = movingMatch[2];
				updateMovingPiece(i, timeStamp, endPos);
			} else {
				const sleepingMatch = sleepingPattern.exec(action);
				if (sleepingMatch !== null) {
					const timeStamp = parseFloat(sleepingMatch[1]);
					const pos = sleepingMatch[2];
					updateSleepingPiece(i, timeStamp, pos);
				} else {
					updateStaticPiece(i, action);
				}
			}
		} else {
			updateRemovedPiece(i);
		}
	}

	let posCount = {};
	let collision = false;
	for (let i = 0; i < 32; ++i) {
		const pos = pieces[i].pos;
		if (pos !== null) {
			posCount[pos] += 1;
			if (posCount[pos] > 1) {
				collision = true;
				break;
			}
		}
	}
	if (collision) {
		console.log(
			"There is a collision between pieces. Server needs to resolve."
		);
		sendWebSocketMessage("/ping");
	}
}

function sendMessage(path, optParam) {
	path += "?g=" + state.gameKey;
	if (optParam) {
		path += "&" + optParam;
	}
	console.log("POST", path);
	const xhr = new XMLHttpRequest();
	xhr.open("POST", path, true);
	xhr.send();
}

function sendWebSocketMessage(path, optParam) {
	if (optParam) {
		path += "?" + optParam;
	}
	console.log("WEBSOCKET", path);
	websocket.send(path);
}

function errorMessage(message) {
	console.error(message);
	sendMessage("/error", "msg=" + encodeURIComponent(message));
}

function showErrorMessage(message) {
	console.error(message);
	$("#error_message").text(message);
	$("#error_modal").show();
}

function onMessage(m) {
	console.log("Parsing JSON: " + m.data);
	const newState = JSON.parse(m.data);

	if (newState["key"] !== state.gameKey) {
		return;
	}

	// Check sequence numbers.
	const newSequenceNumber = parseInt(newState["seq"]);
	if (newSequenceNumber > 1) {
		if (
			sequenceNumber !== null &&
			sequenceNumber !== 0 &&
			sequenceNumber + 1 !== newSequenceNumber &&
			sequenceNumber !== newSequenceNumber
		) {
			errorMessage(
				"Recieved sequence number " +
					newSequenceNumber +
					", but previous was " +
					sequenceNumber +
					"."
			);
		}

		if (sequenceNumber !== null && newSequenceNumber < sequenceNumber) {
			// This message is older than what we have already parsed.
			console.log("onMessage() old message. Will not process it.");
			// This is a good time to request a new update from the server.
			sendWebSocketMessage("/ping");
			return;
		}
	}

	sequenceNumber = newSequenceNumber;

	for (let property in newState) {
		if (newState.hasOwnProperty(property)) {
			const val = newState[property];
			if (val !== null) {
				state[property] = val;
			}
		}
	}

	if (state.me === state.userX) {
		state.myColor = "X";
	} else if (state.me === state.userO) {
		state.myColor = "O";
	} else {
		state.myColor = null;
	}

	if (state.myColor === null && state.userO && state.userO !== "") {
		$("#headline").text(
			"Observing " + state.userXname + " vs. " + state.userOname
		);
		$("#isReady").hide();
		$("#newGameButton").hide();
	} else if (state["state"] === STATE_START) {
		if (state["userO"] !== "") {
			if ($("#isReadyCheckBox").is(":checked")) {
				$("#headline").text("Waiting for other player…");
			} else {
				$("#headline").text("Click when ready!");
			}
		}
		$("#newGameButton").hide();
	} else if (state["state"] === STATE_PLAY) {
		$("#isReady").hide();
		$("#headline").text("Playing!");
		$("#newGameButton").hide();
	} else if (state["state"] === STATE_GAMEOVER) {
		let winnerName = "";
		if (state.winner === WHITE) {
			winnerName = state.userXname;
		} else if (state.winner === BLACK) {
			winnerName = state.userOname;
		}

		$("#isReadyCheckBox").prop("checked", false);
		$("#headline").text("Game Over! " + winnerName + " wins!");
		$("#newGameButton").show();
	}

	// Set the correct data types in the game state.
	state["time_stamp"] = parseFloat(state["time_stamp"]);

	if (newState["ping_tag"] === state.me) {
		const timeStamp = Date.now() / 1000;
		const ping = timeStamp - pingStartTime;
		$("#pingresult").text(ping.toFixed(3) + " s.");
		pingStartTime = null;
	}

	updateGame();
}

function openChannel() {
	let socketProtocol = "wss:";
	if (location.protocol === "http:") {
		socketProtocol = "ws:";
	}
	const ws = new WebSocket(
		socketProtocol + "//" + location.host + "/websocket?&g=" + state.gameKey
	);
	ws.onopen = event => {
		console.log("WebSocket open.", event);
		sendMessage("/opened");
		websocket = ws;
	};
	ws.onclose = () => {
		showErrorMessage("Lost connection to the server. Please refresh page.");
	};
	ws.onmessage = onMessage;
}

function flipBoard() {
	function swapIds(id1, id2) {
		$("#" + id1).attr("id", "tmpUnusedId");
		$("#" + id2).attr("id", id1);
		$("#tmpUnusedId").attr("id", id2);
	}
	for (let c = "A".charCodeAt(0); c <= "H".charCodeAt(0); ++c) {
		const col = String.fromCharCode(c);
		for (let row = 1; row <= 4; ++row) {
			const id1 = col + row;
			const id2 = col + (8 - row + 1);
			swapIds(id1, id2);
		}
	}
	swapIds("bottomMessage", "topMessage");
}

function clickSquare(id, clickedPieceIndex) {
	if (state["state"] !== STATE_PLAY) {
		return;
	}

	if (selectedSquareId) {
		if (
			clickedPieceIndex === null ||
			pieces[clickedPieceIndex].color !== state.myColor
		) {
			$("#" + selectedSquareId).removeAttr("style");
			if (selectedSquareId !== id) {
				// sendMessage("/move", "from=" + selectedSquareId + "&to=" + id);
				sendWebSocketMessage(
					"/move",
					"from=" + selectedSquareId + "&to=" + id
				);
			}
			selectedSquareId = null;
		}

		if (
			clickedPieceIndex !== null &&
			pieces[clickedPieceIndex].color === state.myColor
		) {
			$("#" + selectedSquareId).removeAttr("style");
			selectedSquareId = id;
			$("#" + selectedSquareId).css("background", CLICKED_PIECE_COLOR);
		}
	} else if (clickedPieceIndex !== null) {
		if (pieces[clickedPieceIndex].color === state.myColor) {
			selectedSquareId = id;
			$("#" + selectedSquareId).css("background", CLICKED_PIECE_COLOR);
		}
	}
}

function tdOnclick() {
	clickSquare($(this).attr("id"), null);
}

function pieceOnclick() {
	const index = parseInt(
		$(this)
			.attr("id")
			.substring(1)
	);
	const tdId = pieces[index].pos;

	// To be able to click own pieces, they must be ready.
	if (
		pieces[index].color === state.myColor &&
		!pieces[index].moving &&
		!pieces[index].sleeping
	) {
		clickSquare(tdId, index);
	} else if (pieces[index].color !== state.myColor) {
		clickSquare(tdId, index);
	}
}

export function startGame(gameKey, initialMessage, me) {
	state = {
		gameKey: gameKey,
		me: me
	};

	// All pieces can be dragged, but only within the board.
	$(".piece").draggable({containment: "#chess_board", scroll: false});
	// Configure all table cells as droppable with suitable
	// style changes.
	$("td").droppable({
		drop: function(event, ui) {
			$(this).removeAttr("style");

			const draggedPieceId = ui.draggable.attr("id");
			const toPos = $(this).attr("id");
			const index = parseInt(draggedPieceId.substring(1));
			const fromPos = pieces[index].pos;

			const piece = $("#p" + index);
			const square = $("#" + fromPos);
			piece.offset(square.offset());
			if (fromPos !== toPos) {
				sendWebSocketMessage(
					"/move",
					"from=" + fromPos + "&to=" + toPos
				);
			}
		},
		out: function() {
			$(this).removeAttr("style");
		},
		over: function() {
			const pos = $(this).attr("id");
			// Is there another piece in this square?
			for (let piece of pieces) {
				if (piece.pos === pos && piece.color === state.myColor) {
					$(this).css("background", HOVER_COLLISION_SQUARE_COLOR);
					return;
				}
			}
			$(this).css("background", HOVER_SQUARE_COLOR);
		}
	});
	// In order to avoid pieces ending up between two squares in Chrome.
	$("#chess_board").droppable({
		drop: function(event, ui) {
			const draggedPieceId = ui.draggable.attr("id");
			const index = parseInt(draggedPieceId.substring(1));
			const fromPos = pieces[index].pos;
			const square = $("#" + fromPos);
			const piece = $("#p" + index);
			piece.offset(square.offset());
		}
	});

	console.log("Initializing", initialMessage);
	openChannel();

	// Check if we are playing black.
	const initialJson = JSON.parse(initialMessage);
	if (initialJson.userO === state.me) {
		flipBoard();
	}

	// Process the first message.
	onMessage({data: initialMessage});

	for (let i = 0; i < 32; ++i) {
		const piece = $("#p" + i);
		piece.text(pieces[i].value);
	}

	$("td").click(tdOnclick);
	$(".piece").click(pieceOnclick);

	$("td").on({touchstart: tdOnclick});
	$(".piece").on({touchstart: pieceOnclick});

	$("#pingbutton").click(() => {
		pingStartTime = Date.now() / 1000;
		sendWebSocketMessage("/ping", "tag=" + me);
	});

	$(document).keypress(event => {
		if (event.which === 112 /* p */) {
			pingStartTime = Date.now() / 1000;
			sendWebSocketMessage("/ping", "tag=" + me);
		}
	});

	$("#isReadyCheckBox").click(() => {
		if ($("#isReadyCheckBox").is(":checked")) {
			sendMessage("/ready", "ready=1");
			$("#headline").text("Waiting for other player…");
		} else {
			sendMessage("/ready", "ready=0");
			$("#headline").text("Click when ready!");
		}
	});

	$("#newGameButton").click(() => {
		sequenceNumber = null;
		sendMessage("/newgame");
	});

	$("#randomizePiecesButton").click(() => {
		sequenceNumber = null;
		sendMessage("/randomize");
	});

	$(".close").click(() => {
		$("#error_modal").hide();
	});

	console.log("Document ready.");
}

$(window).resize(() => {
	updateGame();
});

window.onerror = (msg, url, line, col, error) => {
	const extra = !error ? "" : error;
	const errorString =
		"JavaScript: " + msg + " " + url + ", line: " + line + ". " + extra;
	errorMessage(errorString);
	return false;
};
