// Game state
let gameState = {
    gameId: null,
    board: [],
    currentPlayer: 'white',
    selectedPiece: null,
    possibleMoves: [],
    moveHistory: [],
    capturedPieces: { white: [], black: [] },
    gameStatus: 'active',
    flipped: false,
    timers: { white: 600, black: 600 },
    playerName: 'Player',
    playerColor: 'white',
    timeControl: '10 min',
    stats: { games: 0, wins: 0, losses: 0, draws: 0 },
    timersEnabled: true
};

// DOM Elements
const setupScreen = document.getElementById('setup-screen');
const playerNameInput = document.getElementById('player-name');
const startGameBtn = document.getElementById('start-game');
const playerNameDisplay = document.getElementById('player-name-display');
const chessboard = document.getElementById('chessboard');

// Setup screen event listeners
document.querySelectorAll('.color-option').forEach(option => {
    option.addEventListener('click', function() {
        document.querySelectorAll('.color-option').forEach(opt => opt.classList.remove('selected'));
        this.classList.add('selected');
        gameState.playerColor = this.getAttribute('data-color');
    });
});

document.querySelectorAll('.time-option').forEach(option => {
    option.addEventListener('click', function() {
        document.querySelectorAll('.time-option').forEach(opt => opt.classList.remove('selected'));
        this.classList.add('selected');
        gameState.timeControl = this.textContent;
    });
});

startGameBtn.addEventListener('click', function() {
    const name = playerNameInput.value.trim();
    if (name) {
        gameState.playerName = name;
        playerNameDisplay.textContent = name;
        setupScreen.style.display = 'none';
        startNewGame();
    } else {
        alert('Please enter your name');
    }
});

// API Functions
async function startNewGame() {
    try {
        const response = await fetch('/api/new_game', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: gameState.playerName,
                player_color: gameState.playerColor,
                time_control: gameState.timeControl
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert('Error starting game: ' + data.error);
            return;
        }
        
        gameState.gameId = data.game_id;
        gameState.board = data.board;
        gameState.currentPlayer = data.current_player;
        gameState.timers = data.timers;
        gameState.gameStatus = data.status;
        gameState.timersEnabled = data.timers_enabled;
        
        updateBoard();
        updateGameInfo();
        updateTimers();
        
        // Load stats
        loadStats();
    } catch (error) {
        console.error('Error starting game:', error);
        alert('Error starting game. Please check if the server is running.');
    }
}

async function makeMove(fromRow, fromCol, toRow, toCol) {
    if (gameState.gameStatus !== 'active') return;
    
    const fromSquare = `${String.fromCharCode(97 + fromCol)}${8 - fromRow}`;
    const toSquare = `${String.fromCharCode(97 + toCol)}${8 - toRow}`;
    
    // Check if this is a promotion move (pawn moving to the last rank)
    const pieceCode = gameState.board[fromRow][fromCol];
    let promotion = 'q'; // Default to queen
    
    if (pieceCode && pieceCode[1] === 'p' && (toRow === 0 || toRow === 7)) {
        // Show promotion dialog
        promotion = await showPromotionDialog();
    }
    
    try {
        const response = await fetch('/api/move', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                game_id: gameState.gameId,
                from: fromSquare,
                to: toSquare,
                promotion: promotion
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert('Error making move: ' + data.error);
            return;
        }
        
        // Update game state
        gameState.board = data.board;
        gameState.currentPlayer = data.current_player;
        gameState.gameStatus = data.status;
        gameState.timers = data.timers || gameState.timers;
        
        // Update captured pieces
        if (data.captured_pieces) {
            gameState.capturedPieces = data.captured_pieces;
        }
        
        // Add to move history
        if (data.move) {
            gameState.moveHistory.push(data.move);
            updateMoveHistory();
        }
        
        updateBoard();
        updateGameInfo();
        updateCapturedPieces();
        updateTimers();
        
        // If game is over, update stats
        if (data.status === 'finished') {
            if (data.stats) {
                gameState.stats = data.stats;
            }
            updateStats();
            alert(`Game over: ${data.result}`);
        } else if (data.current_player !== gameState.playerColor) {
            // Bot's turn
            setTimeout(makeBotMove, 500);
        }
    } catch (error) {
        console.error('Error making move:', error);
    }
}

async function makeBotMove() {
    try {
        const response = await fetch('/api/bot_move', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                game_id: gameState.gameId
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert('Error with bot move: ' + data.error);
            return;
        }
        
        // Update game state
        gameState.board = data.board;
        gameState.currentPlayer = data.current_player;
        gameState.gameStatus = data.status;
        gameState.timers = data.timers || gameState.timers;
        
        // Update captured pieces
        if (data.captured_pieces) {
            gameState.capturedPieces = data.captured_pieces;
        }
        
        // Add to move history
        if (data.move) {
            gameState.moveHistory.push(data.move);
            updateMoveHistory();
        }
        
        updateBoard();
        updateGameInfo();
        updateCapturedPieces();
        updateTimers();
        
        // If game is over, update stats
        if (data.status === 'finished') {
            if (data.stats) {
                gameState.stats = data.stats;
            }
            updateStats();
            alert(`Game over: ${data.result}`);
        }
    } catch (error) {
        console.error('Error with bot move:', error);
    }
}

async function undoMove() {
    try {
        const response = await fetch('/api/undo', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                game_id: gameState.gameId
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert('Error undoing move: ' + data.error);
            return;
        }
        
        // Update game state
        gameState.board = data.board;
        gameState.currentPlayer = data.current_player;
        gameState.gameStatus = data.status;
        gameState.timers = data.timers || gameState.timers;
        
        // Update captured pieces
        if (data.captured_pieces) {
            gameState.capturedPieces = data.captured_pieces;
        }
        
        // Remove last move from history
        if (gameState.moveHistory.length > 0) {
            gameState.moveHistory.pop();
            updateMoveHistory();
        }
        
        updateBoard();
        updateGameInfo();
        updateCapturedPieces();
        updateTimers();
    } catch (error) {
        console.error('Error undoing move:', error);
    }
}

async function resignGame() {
    if (!confirm('Are you sure you want to resign?')) return;
    
    try {
        const response = await fetch('/api/resign', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                game_id: gameState.gameId
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert('Error resigning: ' + data.error);
            return;
        }
        
        // Update game state
        gameState.gameStatus = 'finished';
        gameState.stats = data.stats;
        
        updateGameInfo();
        updateStats();
        alert('You resigned. Game over.');
    } catch (error) {
        console.error('Error resigning:', error);
    }
}

async function getHint() {
    try {
        const response = await fetch('/api/hint', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                game_id: gameState.gameId
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert('Error getting hint: ' + data.error);
            return;
        }
        
        // Highlight the suggested move
        highlightHint(data.from_square, data.to_square);
    } catch (error) {
        console.error('Error getting hint:', error);
    }
}

async function loadStats() {
    try {
        const response = await fetch(`/api/stats?username=${encodeURIComponent(gameState.playerName)}`);
        const data = await response.json();
        
        if (data.error) {
            console.error('Error loading stats:', data.error);
            return;
        }
        
        gameState.stats = data.stats;
        updateStats();
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function syncTimers() {
    try {
        const response = await fetch(`/api/timers?game_id=${gameState.gameId}`);
        const data = await response.json();
        
        if (data.error) {
            console.error('Error syncing timers:', data.error);
            return;
        }
        
        // Update timers
        gameState.timers = data.timers;
        updateTimers();
        
        // Check if game status changed
        if (data.status === 'finished') {
            gameState.gameStatus = 'finished';
            updateGameInfo();
            alert('Time out! Game over.');
        }
    } catch (error) {
        console.error('Error syncing timers:', error);
    }
}

// UI Update Functions
function renderBoard() {
    chessboard.innerHTML = '';
    
    for (let row = 0; row < 8; row++) {
        for (let col = 0; col < 8; col++) {
            const square = document.createElement('div');
            const isLight = (row + col) % 2 === 0;
            
            square.className = `square ${isLight ? 'light' : 'dark'}`;
            square.dataset.row = row;
            square.dataset.col = col;
            
            // Add labels for chess notation
            if ((gameState.flipped ? row === 0 : row === 7)) {
                const fileLabel = document.createElement('span');
                fileLabel.className = 'square-label file-label';
                fileLabel.textContent = String.fromCharCode(97 + (gameState.flipped ? 7 - col : col));
                square.appendChild(fileLabel);
            }
            
            if ((gameState.flipped ? col === 7 : col === 0)) {
                const rankLabel = document.createElement('span');
                rankLabel.className = 'square-label rank-label';
                rankLabel.textContent = gameState.flipped ? 1 + row : 8 - row;
                square.appendChild(rankLabel);
            }
            
            // Add piece if exists
            const piece = gameState.board[row][col];
            if (piece) {
                const pieceElement = document.createElement('div');
                pieceElement.className = 'piece';
                pieceElement.textContent = getUnicodePiece(piece);
                square.appendChild(pieceElement);
            }
            
            // Add click event
            square.addEventListener('click', () => handleSquareClick(row, col));
            
            chessboard.appendChild(square);
        }
    }
    
    highlightSelectedPiece();
    highlightPossibleMoves();
}

function getUnicodePiece(pieceCode) {
    const pieces = {
        'wp': '♙', 'wr': '♖', 'wn': '♘', 'wb': '♗', 'wq': '♕', 'wk': '♔',
        'bp': '♟', 'br': '♜', 'bn': '♞', 'bb': '♝', 'bq': '♛', 'bk': '♚'
    };
    return pieces[pieceCode] || '';
}

function handleSquareClick(row, col) {
    if (gameState.gameStatus !== 'active') return;
    
    // If a piece is already selected
    if (gameState.selectedPiece) {
        const [selectedRow, selectedCol] = gameState.selectedPiece;
        
        // Make the move
        makeMove(selectedRow, selectedCol, row, col);
        
        // Deselect the piece
        gameState.selectedPiece = null;
        gameState.possibleMoves = [];
        return;
    }
    
    // If no piece is selected yet
    const pieceCode = gameState.board[row][col];
    if (pieceCode && isPieceCurrentPlayer(pieceCode)) {
        gameState.selectedPiece = [row, col];
        gameState.possibleMoves = calculatePossibleMoves(row, col);
        updateBoard();
    }
}

function isPieceCurrentPlayer(pieceCode) {
    return (pieceCode[0] === 'w' && gameState.currentPlayer === 'white') ||
           (pieceCode[0] === 'b' && gameState.currentPlayer === 'black');
}

function calculatePossibleMoves(row, col) {
    // This is a simplified version - the real logic is on the server
    // For UI purposes only, to show possible moves
    const pieceCode = gameState.board[row][col];
    const moves = [];
    
    if (pieceCode[1] === 'p') { // Pawn
        const direction = pieceCode[0] === 'w' ? -1 : 1;
        
        // Move forward one square
        if (isInBounds(row + direction, col) && !gameState.board[row + direction][col]) {
            moves.push([row + direction, col]);
        }
        
        // Capture diagonally
        for (let offset of [-1, 1]) {
            if (isInBounds(row + direction, col + offset)) {
                const targetPiece = gameState.board[row + direction][col + offset];
                if (targetPiece && targetPiece[0] !== pieceCode[0]) {
                    moves.push([row + direction, col + offset]);
                }
            }
        }
    }
    
    return moves;
}

function isInBounds(row, col) {
    return row >= 0 && row < 8 && col >= 0 && col < 8;
}

function highlightSelectedPiece() {
    if (!gameState.selectedPiece) return;
    
    const [row, col] = gameState.selectedPiece;
    const index = row * 8 + col;
    const square = document.querySelectorAll('.square')[index];
    square.classList.add('selected');
}

function highlightPossibleMoves() {
    gameState.possibleMoves.forEach(([row, col]) => {
        const index = row * 8 + col;
        const square = document.querySelectorAll('.square')[index];
        square.classList.add('possible-move');
    });
}

function highlightHint(fromSquare, toSquare) {
    // Clear any existing hints
    clearHints();
    
    // Convert square notation to row and column
    const fileFrom = fromSquare.charCodeAt(0) - 97;
    const rankFrom = 8 - parseInt(fromSquare.charAt(1));
    const fileTo = toSquare.charCodeAt(0) - 97;
    const rankTo = 8 - parseInt(toSquare.charAt(1));
    
    // Adjust for flipped board
    const fromRow = gameState.flipped ? 7 - rankFrom : rankFrom;
    const fromCol = gameState.flipped ? 7 - fileFrom : fileFrom;
    const toRow = gameState.flipped ? 7 - rankTo : rankTo;
    const toCol = gameState.flipped ? 7 - fileTo : fileTo;
    
    // Highlight from square
    const fromIndex = fromRow * 8 + fromCol;
    const fromSquareElement = document.querySelectorAll('.square')[fromIndex];
    fromSquareElement.classList.add('hint-from');
    
    // Highlight to square
    const toIndex = toRow * 8 + toCol;
    const toSquareElement = document.querySelectorAll('.square')[toIndex];
    toSquareElement.classList.add('hint-to');
    
    // Set timeout to clear hints after 5 seconds
    setTimeout(clearHints, 5000);
}

function clearHints() {
    document.querySelectorAll('.square').forEach(square => {
        square.classList.remove('hint-from');
        square.classList.remove('hint-to');
    });
}

async function showPromotionDialog() {
    return new Promise((resolve) => {
        // Create promotion dialog
        const dialog = document.createElement('div');
        dialog.className = 'promotion-dialog';
        
        // Add title
        const title = document.createElement('div');
        title.textContent = 'Choose promotion piece';
        title.style.fontWeight = 'bold';
        title.style.marginBottom = '10px';
        dialog.appendChild(title);
        
        // Add piece options
        const pieces = [
            { symbol: '♕', value: 'q', name: 'Queen' },
            { symbol: '♖', value: 'r', name: 'Rook' },
            { symbol: '♗', value: 'b', name: 'Bishop' },
            { symbol: '♘', value: 'n', name: 'Knight' }
        ];
        
        pieces.forEach(piece => {
            const button = document.createElement('button');
            button.className = 'promotion-option';
            button.innerHTML = `${piece.symbol} ${piece.name}`;
            
            button.addEventListener('click', () => {
                document.body.removeChild(dialog);
                resolve(piece.value);
            });
            
            dialog.appendChild(button);
        });
        
        // Add to document
        document.body.appendChild(dialog);
    });
}

function updateBoard() {
    renderBoard();
}

function updateGameInfo() {
    const statusElement = document.getElementById('game-status');
    const moveCountElement = document.getElementById('move-count');
    
    moveCountElement.textContent = Math.ceil(gameState.moveHistory.length / 2);
    
    switch (gameState.gameStatus) {
        case 'active':
            statusElement.textContent = `${gameState.currentPlayer === 'white' ? 'White' : 'Black'} to move`;
            break;
        case 'finished':
            statusElement.textContent = 'Game over';
            break;
        default:
            statusElement.textContent = gameState.gameStatus;
    }
    
    // Update active player indicator
    document.querySelectorAll('.player-info').forEach(el => {
        el.classList.remove('active-player');
    });
    
    if (gameState.currentPlayer === 'white') {
        document.querySelector('.player-info:nth-child(3)').classList.add('active-player');
    } else {
        document.querySelector('.player-info:nth-child(1)').classList.add('active-player');
    }
}

function updateMoveHistory() {
    const moveListElement = document.getElementById('move-list');
    moveListElement.innerHTML = '';
    
    gameState.moveHistory.forEach((move, index) => {
        if (index % 2 === 0) {
            const moveElement = document.createElement('div');
            moveElement.innerHTML = `<span class="move-number">${Math.floor(index/2) + 1}.</span> ${move}`;
            moveListElement.appendChild(moveElement);
        } else {
            const moveElement = document.createElement('div');
            moveElement.textContent = move;
            moveListElement.appendChild(moveElement);
        }
    });
    
    // Scroll to bottom
    moveListElement.scrollTop = moveListElement.scrollHeight;
}

function updateCapturedPieces() {
    const capturedWhiteElement = document.getElementById('captured-white');
    const capturedBlackElement = document.getElementById('captured-black');
    
    capturedWhiteElement.innerHTML = '';
    capturedBlackElement.innerHTML = '';
    
    if (gameState.capturedPieces.white) {
        gameState.capturedPieces.white.forEach(piece => {
            const pieceElement = document.createElement('span');
            pieceElement.className = 'captured-piece';
            pieceElement.textContent = getUnicodePiece(`w${piece.toLowerCase()}`);
            capturedWhiteElement.appendChild(pieceElement);
        });
    }
    
    if (gameState.capturedPieces.black) {
        gameState.capturedPieces.black.forEach(piece => {
            const pieceElement = document.createElement('span');
            pieceElement.className = 'captured-piece';
            pieceElement.textContent = getUnicodePiece(`b${piece.toLowerCase()}`);
            capturedBlackElement.appendChild(pieceElement);
        });
    }
}

function updateStats() {
    document.getElementById('games-played').textContent = gameState.stats.games || 0;
    document.getElementById('wins').textContent = gameState.stats.wins || 0;
    document.getElementById('losses').textContent = gameState.stats.losses || 0;
    document.getElementById('draws').textContent = gameState.stats.draws || 0;
}

function updateTimers() {
    const whiteMinutes = Math.floor(gameState.timers.white / 60);
    const whiteSeconds = gameState.timers.white % 60;
    const blackMinutes = Math.floor(gameState.timers.black / 60);
    const blackSeconds = gameState.timers.black % 60;
    
    document.getElementById('white-timer').textContent = 
        `${whiteMinutes}:${whiteSeconds < 10 ? '0' : ''}${whiteSeconds}`;
    document.getElementById('black-timer').textContent = 
        `${blackMinutes}:${blackSeconds < 10 ? '0' : ''}${blackSeconds}`;
}

// Event listeners for buttons
document.getElementById('new-game').addEventListener('click', function() {
    setupScreen.style.display = 'flex';
});

document.getElementById('resign').addEventListener('click', resignGame);

document.getElementById('flip-board').addEventListener('click', function() {
    gameState.flipped = !gameState.flipped;
    updateBoard();
});

document.getElementById('hint').addEventListener('click', getHint);

document.getElementById('undo').addEventListener('click', undoMove);

// Timer synchronization
setInterval(syncTimers, 1000);