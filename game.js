
jQuery.fn.rotate = function(degrees) {
    $(this).css({'-webkit-transform' : 'rotate('+ degrees +'deg)',
                 '-moz-transform' : 'rotate('+ degrees +'deg)',
                 '-ms-transform' : 'rotate('+ degrees +'deg)',
                 'transform' : 'rotate('+ degrees +'deg)'});
    return $(this);
};

function assert(condition, message) {
  if (!condition) {
    message = message || "Assertion failed";
    throw new Error(message);
  }
}

var sequenceNumber = null;
var state = {
  game_key: GAME_KEY,
  me: ME
};

var pingStartTime = null;

var selectedSquareId = null;
var selectedSquareCss = null;

var BLACK_ROOK   = "\u265C";
var BLACK_KNIGHT = "\u265E";
var BLACK_BISHOP = "\u265D";
var BLACK_QUEEN  = "\u265B";
var BLACK_KING   = "\u265A";
var BLACK_PAWN   = "\u265F";
var WHITE_ROOK   = "\u2656";
var WHITE_KNIGHT = "\u2658";
var WHITE_BISHOP = "\u2657";
var WHITE_QUEEN  = "\u2655";
var WHITE_KING   = "\u2654";
var WHITE_PAWN   = "\u2659";
var pieces = [
  {color:"X", value:WHITE_ROOK},
  {color:"X", value:WHITE_KNIGHT},
  {color:"X", value:WHITE_BISHOP},
  {color:"X", value:WHITE_QUEEN},
  {color:"X", value:WHITE_KING},
  {color:"X", value:WHITE_BISHOP},
  {color:"X", value:WHITE_KNIGHT},
  {color:"X", value:WHITE_ROOK},
  {color:"X", value:WHITE_PAWN},
  {color:"X", value:WHITE_PAWN},
  {color:"X", value:WHITE_PAWN},
  {color:"X", value:WHITE_PAWN},
  {color:"X", value:WHITE_PAWN},
  {color:"X", value:WHITE_PAWN},
  {color:"X", value:WHITE_PAWN},
  {color:"X", value:WHITE_PAWN},
  {color:"O", value:BLACK_ROOK},
  {color:"O", value:BLACK_KNIGHT},
  {color:"O", value:BLACK_BISHOP},
  {color:"O", value:BLACK_QUEEN},
  {color:"O", value:BLACK_KING},
  {color:"O", value:BLACK_BISHOP},
  {color:"O", value:BLACK_KNIGHT},
  {color:"O", value:BLACK_ROOK},
  {color:"O", value:BLACK_PAWN},
  {color:"O", value:BLACK_PAWN},
  {color:"O", value:BLACK_PAWN},
  {color:"O", value:BLACK_PAWN},
  {color:"O", value:BLACK_PAWN},
  {color:"O", value:BLACK_PAWN},
  {color:"O", value:BLACK_PAWN},
  {color:"O", value:BLACK_PAWN}
];

updateRemovedPiece = function(i) {
  // Is the position of this piece the currently selected one?
  if (selectedSquareId != null && selectedSquareId == pieces[i].pos) {
    // Remove selection.
    $('#'+selectedSquareId).removeAttr('style');
    selectedSquareId = null;
  }

  pieces[i].pos = null;
  var piece = $("#p" + i);
  piece.hide();
  // TODO: Show piece if needed later.

  console.log("Piece " + i + " is removed.");
}

updateStaticPiece = function(i, pos) {
  pieces[i].pos = pos;
  pieces[i].moving = false;
  pieces[i].sleeping = false;
  pieces[i].rotation = 0.0;

  // Set the correct position of the piece.
  var square = $("#" + pieces[i].pos);
  var pos = square.offset();
  var piece = $("#p" + i);

  // Stop all previous animations.
  piece.stop(true);

  // Allow clicking.
  piece.css("pointer-events", "auto");

  piece.offset(pos);
  piece.rotate(0);
}

localTransitionToSleeping = function(i, endTimeStamp, pos) {
  if (pieces[i].color !== state.myColor) {
    // Not my piece; the other player will take care of this.
    return;
  }

  // Is there another piece in this square?
  for (var j = 0; j < 32; ++j) {
    var capture = false;
    if (i != j && pos === pieces[j].pos) {
      capture = true;
    }

    var sleepingPattern = /S,(\d+\.?\d*),([A-H][1-8])/g;
    var sleepingMatch = sleepingPattern.exec(pieces[j].pos);
    if (sleepingMatch != null) {
      var endPos = sleepingMatch[2]
      if (pos === endPos) {
        capture = true;
      }
    }
    if (capture) {
      // We need to let the server resolve this.
      console.log("Piece " + i + " has moved into square occupied by " + j);
      sendMessage("/ping");
    }
  }
}

updateSleepingPiece = function(i, endTimeStamp, pos) {
  pieces[i].pos = pos;
  pieces[i].moving = false;
  pieces[i].sleeping = true;

  // Set the correct position of the piece.
  var square = $("#" + pos);
  var animationTarget = square.offset();
  var piece = $("#p" + i);

  // Stop all previous animations.
  piece.stop(true);

  // Allow clicking.
  piece.css("pointer-events", "auto");

  // Adjust rotation before and after setting position, to
  // avoid the rotation introducing an offset.
  piece.rotate(0);
  piece.offset(animationTarget);
  piece.rotate(pieces[i].rotation);

  var startRotation = pieces[i].rotation;
  var endRotation = 0.0;

  var duration = SLEEPING_TIME;
  if (endTimeStamp) {
    // We have gotten a time stamp from the server when
    // the sleeping phase should be done.
    var duration = endTimeStamp - state["time_stamp"];
  }

  var animationComplete = function() {
    assert(pieces[i].sleeping);
    updateStaticPiece(i, pos);
  };
  var animationProgress = function(animation, progress, remainingMs) {
    pieces[i].rotation = (1.0 - progress) * startRotation + progress * endRotation;
    piece.rotate(pieces[i].rotation);
  };
  if (duration > 0) {
    piece.animate(animationTarget,
        {
          "duration": 1000 * duration,
          "done": animationComplete,
          "progress": animationProgress,
        });
  } else {
    animationComplete();
  }

  console.log("Sleeping " + i + ", timeStamp:" + endTimeStamp + ", endPos:" + pos);
}

updateMovingPiece = function(i, endTimeStamp, endPos) {
  pieces[i].moving = true;
  pieces[i].sleeping = false;

  // Set the piece moving towards the end square.
  var square = $("#" + endPos);
  var animationTarget = square.offset();
  var piece = $("#p" + i);

  // Stop all previous animations.
  piece.stop(true);

  // Can not be clicked while moving.
  piece.css("pointer-events", "none");

  var startRotation = pieces[i].rotation;
  var endRotation = -90.0;

  var duration = endTimeStamp - state["time_stamp"];
  var animationComplete = function() {
    assert(pieces[i].moving);
    localTransitionToSleeping(i, null, endPos);
    updateSleepingPiece(i, null, endPos);
  };
  var animationProgress = function(animation, progress, remainingMs) {
    pieces[i].rotation = (1.0 - progress) * startRotation + progress * endRotation;
    piece.rotate(pieces[i].rotation);
  };
  if (duration > 0) {
    piece.animate(animationTarget,
        {
          "duration": 1000 * duration,
          "done": animationComplete,
          "progress": animationProgress,
        });
  } else {
    animationComplete();
  }

  console.log("Moved " + i + ", timeStamp:" + endTimeStamp + ", endPos:" + endPos);
}

updateGame = function() {

  if (!state.userO || state.userO == '') {
    $('#other-player').show();
    $("#gameInformation").show();
    $('#this-game').hide();
    $('#chess_board').hide();
    $("#isReady").hide();
    $("#ping").hide();
    $(".beforeGame").show();
    for (var i = 0; i < 32; ++i) {
      $("#p"+i).hide();
    }
    console.log("No other player.")
  } else {
    $('#other-player').hide();
    $("#gameInformation").hide();
    $('#this-game').show();
    $('#chess_board').show();
    if (state.state == STATE_START && state.myColor != null) {
      $("#isReady").show();
    }
    $("#ping").show();
    $(".beforeGame").hide();
    for (var i = 0; i < 32; ++i) {
      $("#p"+i).show();
    }
  }

  if (state["state"] == STATE_PLAY) {
    if (state.me === state.userX) {
      $("#topMessage").text(state.userOname);
      $("#bottomMessage").text(state.userXname);
    } else {
      $("#topMessage").text(state.userOname);
      $("#bottomMessage").text(state.userXname);
    }
  }

  for (var i = 0; i < 32; ++i) {
    if (state.hasOwnProperty('p' + i) && state['p' + i] !== "") {
      new_state = state['p' + i]
      var parts = new_state.split(";")
      var colorType = parts[0]
      var action = parts[1]

      parts = colorType.split(",");
      var color = parseInt(parts[0]);
      var type = parseInt(parts[1]);
      if (color == WHITE && type == PAWN) {
        pieces[i].color = 'X';
        pieces[i].value = WHITE_PAWN;
      } else if (color == WHITE && type == ROOK) {
        pieces[i].color = 'X';
        pieces[i].value = WHITE_ROOK;
      } else if (color == WHITE && type == KNIGHT) {
        pieces[i].color = 'X';
        pieces[i].value = WHITE_KNIGHT;
      } else if (color == WHITE && type == BISHOP) {
        pieces[i].color = 'X';
        pieces[i].value = WHITE_BISHOP;
      } else if (color == WHITE && type == QUEEN) {
        pieces[i].color = 'X';
        pieces[i].value = WHITE_QUEEN;
      } else if (color == WHITE && type == KING) {
        pieces[i].color = 'X';
        pieces[i].value = WHITE_KING;
      } else if (color == BLACK && type == PAWN) {
        pieces[i].color = 'O';
        pieces[i].value = BLACK_PAWN;
      } else if (color == BLACK && type == ROOK) {
        pieces[i].color = 'O';
        pieces[i].value = BLACK_ROOK;
      } else if (color == BLACK && type == KNIGHT) {
        pieces[i].color = 'O';
        pieces[i].value = BLACK_KNIGHT;
      } else if (color == BLACK && type == BISHOP) {
        pieces[i].color = 'O';
        pieces[i].value = BLACK_BISHOP;
      } else if (color == BLACK && type == QUEEN) {
        pieces[i].color = 'O';
        pieces[i].value = BLACK_QUEEN;
      } else if (color == BLACK && type == KING) {
        pieces[i].color = 'O';
        pieces[i].value = BLACK_KING;
      } else {
        errorMessage("Color and type not found.")
      }
      var piece = $("#p" + i);
      piece.text(pieces[i].value);

      var movingPattern = /M,(\d+\.?\d*),([A-H][1-8])/g;
      var sleepingPattern = /S,(\d+\.?\d*),([A-H][1-8])/g;
      var moving_match = movingPattern.exec(action);
      if (moving_match != null) {
        var timeStamp = parseFloat(moving_match[1]);
        var endPos = moving_match[2]
        updateMovingPiece(i, timeStamp, endPos)
      } else {
        var sleepingMatch = sleepingPattern.exec(action);
        if (sleepingMatch != null) {
          var timeStamp = parseFloat(sleepingMatch[1]);
          var pos = sleepingMatch[2];
          updateSleepingPiece(i, timeStamp, pos);
        } else {
          updateStaticPiece(i, action);
        }
      }      
    } else {
      updateRemovedPiece(i);
    }
  }

  var posCount = {};
  var collision = false;
  for (var i = 0; i < 32; ++i) {
    var pos = pieces[i].pos;
    if (pos != null) {
      posCount[pos] += 1;
      if (posCount[pos] > 1) {
        collision = true;
        break;
      }
    }
  }
  if (collision) {
    console.log("There is a collision between pieces. Server needs to resolve.");
    sendMessage("/ping");
  }

  console.log("updateGame() done.");
};

myPiece = function() {
  return state.userX == state.me ? 'X' : 'O';
}

sendMessage = function(path, opt_param) {
  path += '?g=' + state.game_key;
  if (opt_param) {
    path += '&' + opt_param;
  }
  var xhr = new XMLHttpRequest();
  xhr.open('POST', path, true);
  xhr.send();
};

errorMessage = function(message) {
  console.log(message);
  sendMessage("/error", "msg=" + encodeURIComponent(message));
}

onMessage = function(m) {
  console.log("Parsing JSON: " + m.data)
  newState = JSON.parse(m.data);

  if (newState["key"] !== GAME_KEY) {
    return;
  }

  // Check sequence numbers.
  var newSequenceNumber = parseInt(newState["seq"]);
  if (newSequenceNumber > 1) {
    if (sequenceNumber != null
        && sequenceNumber != 0
        && sequenceNumber + 1 != newSequenceNumber
        && sequenceNumber != newSequenceNumber) {
      errorMessage("Recieved sequence number " + newSequenceNumber
                   + ", but previous was " + sequenceNumber + ".");
    }

    if (sequenceNumber != null && newSequenceNumber < sequenceNumber) {
      // This message is older than what we have already parsed.
      console.log("onMessage() old message. Will not process it.");
      // This is a good time to request a new update from the server.
      sendMessage("/ping");
      return;
    }
  }

  sequenceNumber = newSequenceNumber

  for (var property in newState) {
    if (newState.hasOwnProperty(property)) {
      var val = newState[property];
      if (val != null) {
        state[property] = val;
      }
    }
  }

  if (state.me === state.userX) {
    state.myColor = 'X';
  } else if (state.me === state.userO) {
    state.myColor = 'O';
  } else {
    state.myColor = null;
  }

  if (state.myColor == null && state.userO && state.userO !== '') {
      $("#headline").text("Observing " + state.userXname + " vs. " + state.userOname);
      $('#isReady').hide();
      $("#newGameButton").hide();
  } else if (state["state"] == STATE_START) {

    if (state["userO"] !== "") {
      if ($('#isReadyCheckBox').is(':checked')) {
        $("#headline").text("Waiting for other player…");
      } else {
        $("#headline").text("Click when ready!");
      }
    }
    $("#newGameButton").hide();
  } else if (state["state"] == STATE_PLAY) {
    $('#isReady').hide();
    $("#headline").text("Playing!");
    $("#newGameButton").hide();
  } else if (state["state"] == STATE_GAMEOVER) {
    winnerName = ""
    if (state.winner == WHITE) {
      winnerName = state.userXname
    } else if (state.winner == BLACK) {
      winnerName = state.userOname
    }

    $("#isReadyCheckBox").prop('checked', false);
    $("#headline").text("Game Over! " + winnerName + " wins!");
    $("#newGameButton").show();
  }

  // Set the correct data types in the game state.
  state["time_stamp"] = parseFloat(state["time_stamp"]);

  if (newState["ping_tag"] == ME) {
    timeStamp = Date.now() / 1000;
    ping = timeStamp - pingStartTime;
    $("#pingresult").text(ping.toFixed(3) + " s.");
    pingStartTime = null;
  }

  updateGame();
  console.log("onMessage() done.")
}

openChannel = function() {
  var token = TOKEN;
  var ws = new WebSocket("ws://" + location.host + "/websocket?&g=" + state.game_key);
  ws.onopen = function (event) {
    console.log("WebSocket open.", event);
    sendMessage('/opened');
  };
  ws.onmessage = onMessage;
}

flipBoard = function() {

  var swapIds = function(id1, id2) {
    $("#" + id1).attr("id", "tmpUnusedId");
    $("#" + id2).attr("id", id1);
    $("#tmpUnusedId").attr("id", id2);
  }

  for (var c = 'A'.charCodeAt(0); c <= 'H'.charCodeAt(0); ++c) {
    var col = String.fromCharCode(c);
    for (var row = 1; row <= 4; ++row) {
      id1 = col + row;
      id2 = col + (8 - row + 1);
      swapIds(id1, id2);
    }
  }

  swapIds("bottomMessage", "topMessage");
}

click_square = function(id, clickedPieceIndex) {

  if (state["state"] != STATE_PLAY) {
    return;
  }

  if (selectedSquareId) {
    if (clickedPieceIndex == null
        || pieces[clickedPieceIndex].color !== state.myColor) {
      $('#'+selectedSquareId).removeAttr('style');
      sendMessage("/move", "from=" + selectedSquareId + "&to=" + id);
      selectedSquareId = null;
    }

    if (clickedPieceIndex != null
        && pieces[clickedPieceIndex].color === state.myColor) {
      $('#'+selectedSquareId).removeAttr('style');
      selectedSquareId = id;
      $('#'+selectedSquareId).css('background', '#FF9999');
    }

  } else if (clickedPieceIndex != null) {
    if (pieces[clickedPieceIndex].color === state.myColor) {
      selectedSquareId = id;
      $('#'+selectedSquareId).css('background', '#FF9999');
    }
  }
  console.log("click_square(" + id + ") done.");
}

td_onclick = function() {
  click_square($(this).attr('id'), null);
}

piece_onclick = function() {
  var index = parseInt($(this).attr('id').substring(1));
  var td_id = pieces[index].pos;

  // To be able to click own pieces, they must be ready.
  if (pieces[index].color === state.myColor
      && !pieces[index].moving
      && !pieces[index].sleeping) {
    click_square(td_id, index);
  } else if (pieces[index].color !== state.myColor) {
    click_square(td_id, index);
  }
}

$(window).load(function() {
  console.log("Initializing", INITIAL_MESSAGE)
  openChannel();

  // Check if we are playing black.
  var initialJson = JSON.parse(INITIAL_MESSAGE);
  if (initialJson.userO === state.me) {
    flipBoard();
  }

  // Process the first message.
  onMessage({data: INITIAL_MESSAGE});
  
  for (var i = 0; i < 32; ++i) {
    var piece = $("#p" + i);
    piece.text(pieces[i].value)
  }

  $('td').click(td_onclick);
  $('.piece').click(piece_onclick);

  $('td').on({ 'touchstart' : td_onclick });
  $('.piece').on({ 'touchstart' : piece_onclick });

  $('#pingbutton').click(function() {
    pingStartTime = Date.now() / 1000;
    sendMessage("/ping", "tag="+ME);
  });

  $(document).keypress(function(event){
    if (event.which == 112 /* p */) {
      pingStartTime = Date.now() / 1000;
      sendMessage("/ping", "tag="+ME);
    }
  });

  $('#isReadyCheckBox').click(function() {
    if ($('#isReadyCheckBox').is(':checked')) {
      sendMessage("/ready", "ready=1");
      $("#headline").text("Waiting for other player…");
    } else {
      sendMessage("/ready", "ready=0");
      $("#headline").text("Click when ready!");
    }
  });

  $('#newGameButton').click(function() {
    sequenceNumber = null;
    sendMessage("/newgame");
  });

  $('#randomizePiecesButton').click(function() {
    sequenceNumber = null;
    sendMessage("/randomize");
  });

  console.log("Document ready.")
});

$(window).resize(function() {
  updateGame();
});

window.onerror = function(msg, url, line, col, error) {
  var extra = !error ? "" : error;
  var errorString = "JavaScript: " + msg + " " + url + ", line: " + line + ". " + extra;
  errorMessage(errorString);
  return false;
};
