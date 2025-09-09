from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import chess
import chess.pgn
import os
import pickle
import json
from datetime import datetime
import random
from collections import defaultdict
import time
import atexit
import subprocess
import sys
from threading import Thread, RLock
import uuid
from time import time as current_time

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
CORS(app)

# Global variables for game state and policies
games = {}
policies = {}
stats = {}
games_lock = RLock()
policy_lock = RLock()

# Timer thread to check for expired games
def timer_thread():
    while True:
        try:
            current_time_val = current_time()
            with games_lock:
                for game_id, game_state in list(games.items()):
                    if (game_state['game_status'] == 'active' and 
                        game_state['timers_enabled'] and
                        game_state['last_move_time'] > 0):
                        
                        # Calculate elapsed time since last update
                        elapsed = current_time_val - game_state['last_move_time']
                        if elapsed > 0:
                            # Update the current player's timer
                            current_player = 'white' if game_state['board'].turn == chess.WHITE else 'black'
                            game_state['timers'][current_player] = max(0, game_state['timers'][current_player] - elapsed)
                            game_state['last_move_time'] = current_time_val
                            
                            # Check if time has expired
                            if game_state['timers'][current_player] <= 0:
                                # Time's up - current player loses
                                game_state['game_status'] = 'finished'
                                
                                # Determine winner
                                if current_player == 'white':
                                    result = "0-1"  # Black wins
                                    outcome = "Black wins"
                                else:
                                    result = "1-0"  # White wins
                                    outcome = "White wins"
                                
                                # Update game headers
                                game_state['game'].headers["Result"] = result
                                
                                # Update stats
                                username = game_state['username']
                                if username not in stats:
                                    load_stats(username)
                                
                                if outcome == "White wins":
                                    if game_state['human_color'] == chess.WHITE:
                                        stats[username]['wins'] += 1
                                        # Human won, bot lost
                                        game_state['bot_loss_streak'] += 1
                                        if game_state['bot_loss_streak'] >= 5:
                                            game_state['learning_boost_active'] = True
                                    else:
                                        stats[username]['losses'] += 1
                                        # Bot won, reset streak
                                        game_state['bot_loss_streak'] = 0
                                        game_state['learning_boost_active'] = False
                                else:  # Black wins
                                    if game_state['human_color'] == chess.BLACK:
                                        stats[username]['wins'] += 1
                                        # Human won, bot lost
                                        game_state['bot_loss_streak'] += 1
                                        if game_state['bot_loss_streak'] >= 5:
                                            game_state['learning_boost_active'] = True
                                    else:
                                        stats[username]['losses'] += 1
                                        # Bot won, reset streak
                                        game_state['bot_loss_streak'] = 0
                                        game_state['learning_boost_active'] = False
                                
                                stats[username]['games_played'] += 1
                                
                                # Update learning policy only if user is jakhar
                                if username.lower() == "jakhar":
                                    with policy_lock:
                                        update_policy(
                                            username, 
                                            outcome, 
                                            [m['move'] for m in game_state['move_history']], 
                                            game_state['human_color'],
                                            game_state['learning_boost_active']
                                        )
                                
                                # Save game and stats
                                save_game(game_state)
                                save_stats(username)
            
            time.sleep(0.1)  # Check more frequently
        except Exception as e:
            print(f"Error in timer thread: {e}")
            time.sleep(1)

# Start the timer thread
timer_thread = Thread(target=timer_thread, daemon=True)
timer_thread.start()

# Initialize policies and stats
def initialize_data():
    # Create directories if they don't exist
    os.makedirs("games", exist_ok=True)
    os.makedirs("memory", exist_ok=True)
    os.makedirs("memory/jakhar", exist_ok=True)
    os.makedirs("games_github", exist_ok=True)
    
    # Load jakhar's policy and stats
    load_policy("jakhar")
    load_stats("jakhar")

def load_policy(username):
    policy_file = f"memory/{username}/policy.pkl"
    
    # If user is not jakhar, try to load jakhar's policy
    if username.lower() != "jakhar" and not os.path.exists(policy_file):
        policy_file = "memory/jakhar/policy.pkl"
    
    try:
        with open(policy_file, "rb") as f:
            policy_dict = pickle.load(f)
            policies[username] = defaultdict(lambda: defaultdict(int))
            for k, v in policy_dict.items():
                policies[username][k] = defaultdict(int, v)
            print(f"📂 Loaded policy for {username} with {len(policies[username])} states")
    except FileNotFoundError:
        policies[username] = defaultdict(lambda: defaultdict(int))
        print(f"📂 No existing policy found for {username}, starting fresh")

def load_stats(username):
    stats_file = f"memory/{username}/stats.json"
    
    # If user is not jakhar, try to load jakhar's stats
    if username.lower() != "jakhar" and not os.path.exists(stats_file):
        stats_file = "memory/jakhar/stats.json"
    
    try:
        with open(stats_file, "r") as f:
            stats[username] = json.load(f)
            print(f"📊 Loaded stats for {username}: {stats[username]}")
    except FileNotFoundError:
        stats[username] = {'wins': 0, 'losses': 0, 'draws': 0, 'games_played': 0}
        print(f"📊 No existing stats found for {username}, starting fresh")

def save_policy(username):
    with policy_lock:
        if username in policies:
            # Convert defaultdict to regular dict for serialization
            policy_dict = {k: dict(v) for k, v in policies[username].items()}
            
            # Save policy for the current user
            policy_file = f"memory/{username}/policy.pkl"
            with open(policy_file, "wb") as f:
                pickle.dump(policy_dict, f)

def save_stats(username):
    if username in stats:
        stats_file = f"memory/{username}/stats.json"
        with open(stats_file, "w") as f:
            json.dump(stats[username], f)

def get_normalized_fen(board):
    # Normalize FEN by removing move counters
    return ' '.join(board.fen().split()[:4])

def get_normalized_fen_from_board(board):
    return ' '.join(board.fen().split()[:4])

def get_bot_move(board, username, move_history):
    fen = get_normalized_fen(board)
    
    # Check if we have policy for this position
    if username in policies and fen in policies[username] and policies[username][fen]:
        moves, weights = zip(*policies[username][fen].items())
        # Filter to only legal moves
        legal_moves = [m for m in moves if chess.Move.from_uci(m) in board.legal_moves]
        legal_weights = [policies[username][fen][m] for m in legal_moves]
        
        if legal_moves and sum(legal_weights) > 0:
            move_uci = random.choices(legal_moves, weights=legal_weights, k=1)[0]
            return chess.Move.from_uci(move_uci)
    
    # Fallback to heuristic if no policy
    return get_heuristic_move(board, move_history)

def get_heuristic_move(board, move_history):
    legal_moves = list(board.legal_moves)
    scored_moves = []
    
    for move in legal_moves:
        score = 0
        
        # Prefer captures that gain material
        if board.is_capture(move):
            captured_piece = board.piece_at(move.to_square)
            if captured_piece:
                score += get_piece_value(captured_piece.piece_type)
        
        # Prefer checks
        board.push(move)
        if board.is_check():
            score += 1
        board.pop()
        
        # Prefer developing moves in early game
        if len(move_history) < 20:
            piece = board.piece_at(move.from_square)
            if piece and piece.piece_type == chess.PAWN:
                score -= 0.1
            elif piece and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                score += 0.2
        
        scored_moves.append((move, score))
    
    # Sort by score and pick the best move
    scored_moves.sort(key=lambda x: x[1], reverse=True)
    best_score = scored_moves[0][1]
    best_moves = [m for m, s in scored_moves if s == best_score]
    
    return random.choice(best_moves) if best_moves else random.choice(legal_moves)

def get_hint_move(board, username, move_history):
    # Get the best move according to policy and heuristics
    return get_bot_move(board, username, move_history)

def get_piece_value(piece_type):
    values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0
    }
    return values.get(piece_type, 0)

def update_policy(username, outcome, move_history, human_color, learning_boost_active=False):
    if username.lower() != "jakhar":
        return
    
    learning_params = {
        'win_reward': 1,
        'draw_reward': 0.5,
        'loss_reward': -1,
        'decay_factor': 0.9,
        'window_size': 100,
    }
    
    # Calculate dynamic rewards based on loss streak
    if learning_boost_active:
        win_reward = learning_params['win_reward'] * 3
        draw_reward = learning_params['draw_reward'] * 2
        loss_reward = learning_params['loss_reward'] * 2
        print(f"⚡ Using boosted rewards: win={win_reward}, draw={draw_reward}, loss={loss_reward}")
    else:
        win_reward = learning_params['win_reward']
        draw_reward = learning_params['draw_reward']
        loss_reward = learning_params['loss_reward']
    
    reward = 0
    
    if outcome == "White wins":
        reward = win_reward if human_color == chess.WHITE else loss_reward
    elif outcome == "Black wins":
        reward = win_reward if human_color == chess.BLACK else loss_reward
    else:  # Draw
        reward = draw_reward
    
    # Replay the game and update policy for human moves
    temp_board = chess.Board()
    policy_updates = 0
    
    for i, move in enumerate(move_history):
        if temp_board.turn == human_color:
            fen = get_normalized_fen_from_board(temp_board)
            move_uci = move.uci()
            policies[username][fen][move_uci] += reward
            policy_updates += 1
        
        temp_board.push(move)
    
    # Save updated policy
    save_policy(username)
    
    print(f"📊 Policy updated with {policy_updates} moves. Total states: {len(policies[username])}")

# Initialize data on startup
initialize_data()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/new_game', methods=['POST'])
def new_game():
    data = request.json
    username = data.get('username', 'Guest')
    player_color = data.get('player_color', 'white')
    time_control = data.get('time_control', '10 min')
    
    # Generate a unique game ID
    game_id = str(uuid.uuid4())
    
    # Set timers based on time control
    timers = {'white': 600, 'black': 600}  # Default to 10 minutes
    timers_enabled = True
    
    if time_control == '1 min':
        timers = {'white': 60, 'black': 60}
    elif time_control == '3 min':
        timers = {'white': 180, 'black': 180}
    elif time_control == '5 min':
        timers = {'white': 300, 'black': 300}
    elif time_control == '10 min':
        timers = {'white': 600, 'black': 600}
    elif time_control == '30 min':
        timers = {'white': 1800, 'black': 1800}
    else:  # No limit
        timers_enabled = False
    
    # Initialize game state
    game_state = {
        'board': chess.Board(),
        'game': chess.pgn.Game(),
        'node': None,
        'human_color': chess.WHITE if player_color == 'white' else chess.BLACK,
        'move_history': [],
        'captured_pieces': [],  # Store captured pieces with move info
        'username': username,
        'time_control': time_control,
        'timers': timers,
        'timers_enabled': timers_enabled,
        'last_move_time': current_time(),
        'game_status': 'active',
        'bot_loss_streak': 0,
        'learning_boost_active': False
    }
    
    # Set up game headers
    game_state['game'].headers["Event"] = f"{username} vs Sachin"
    game_state['game'].headers["Date"] = datetime.now().strftime("%Y.%m.%d")
    game_state['game'].headers["White"] = username if game_state['human_color'] == chess.WHITE else "Sachin"
    game_state['game'].headers["Black"] = "Sachin" if game_state['human_color'] == chess.WHITE else username
    game_state['node'] = game_state['game']
    
    # Store game state
    with games_lock:
        games[game_id] = game_state
    
    # Load user stats if not already loaded
    if username not in stats:
        load_stats(username)
    
    # Return initial game state
    return jsonify({
        'game_id': game_id,
        'board': get_board_array(game_state['board']),
        'current_player': 'white',
        'timers': game_state['timers'],
        'status': 'active',
        'timers_enabled': timers_enabled
    })

@app.route('/api/move', methods=['POST'])
def make_move():
    data = request.json
    game_id = data.get('game_id')
    from_square = data.get('from')
    to_square = data.get('to')
    promotion = data.get('promotion', 'q')
    
    with games_lock:
        if game_id not in games:
            return jsonify({'error': 'Game not found'}), 404
        
        game_state = games[game_id]
        board = game_state['board']
        
        # Check if this is a promotion move
        move = None
        try:
            # First try to create the move without promotion
            move = chess.Move.from_uci(f"{from_square}{to_square}")
            
            # If it's a pawn moving to the last rank, it needs promotion
            piece = board.piece_at(move.from_square)
            if (piece and piece.piece_type == chess.PAWN and
                chess.square_rank(move.to_square) in [0, 7]):
                # Use the provided promotion piece
                move = chess.Move.from_uci(f"{from_square}{to_square}{promotion}")
        except:
            # If that fails, try with promotion
            try:
                move = chess.Move.from_uci(f"{from_square}{to_square}{promotion}")
            except:
                return jsonify({'error': 'Invalid move format'}), 400
        
        # Validate move
        if move not in board.legal_moves:
            return jsonify({'error': 'Invalid move'}), 400
        
        # Update timer for current player
        if game_state['timers_enabled']:
            current_time_val = current_time()
            elapsed = current_time_val - game_state['last_move_time']
            current_player = 'white' if board.turn == chess.WHITE else 'black'
            game_state['timers'][current_player] = max(0, game_state['timers'][current_player] - elapsed)
            game_state['last_move_time'] = current_time_val
            
            # Check if time has expired
            if game_state['timers'][current_player] <= 0:
                # Time's up - current player loses
                game_state['game_status'] = 'finished'
                
                # Determine winner
                if current_player == 'white':
                    result = "0-1"  # Black wins
                    outcome = "Black wins"
                else:
                    result = "1-0"  # White wins
                    outcome = "White wins"
                
                # Update game headers
                game_state['game'].headers["Result"] = result
                
                # Update stats
                username = game_state['username']
                if username not in stats:
                    load_stats(username)
                
                if outcome == "White wins":
                    if game_state['human_color'] == chess.WHITE:
                        stats[username]['wins'] += 1
                        # Human won, bot lost
                        game_state['bot_loss_streak'] += 1
                        if game_state['bot_loss_streak'] >= 5:
                            game_state['learning_boost_active'] = True
                    else:
                        stats[username]['losses'] += 1
                        # Bot won, reset streak
                        game_state['bot_loss_streak'] = 0
                        game_state['learning_boost_active'] = False
                else:  # Black wins
                    if game_state['human_color'] == chess.BLACK:
                        stats[username]['wins'] += 1
                        # Human won, bot lost
                        game_state['bot_loss_streak'] += 1
                        if game_state['bot_loss_streak'] >= 5:
                            game_state['learning_boost_active'] = True
                    else:
                        stats[username]['losses'] += 1
                        # Bot won, reset streak
                        game_state['bot_loss_streak'] = 0
                        game_state['learning_boost_active'] = False
                
                stats[username]['games_played'] += 1
                
                # Update learning policy only if user is jakhar
                if username.lower() == "jakhar":
                    with policy_lock:
                        update_policy(
                            username, 
                            outcome, 
                            [m['move'] for m in game_state['move_history']], 
                            game_state['human_color'],
                            game_state['learning_boost_active']
                        )
                
                # Save game and stats
                save_game(game_state)
                save_stats(username)
                
                return jsonify({
                    'game_id': game_id,
                    'status': 'finished',
                    'result': result,
                    'stats': stats[username]
                })
        
        # Check for capture
        captured_piece = None
        if board.is_capture(move):
            captured_piece = board.piece_at(move.to_square)
        
        # Make the move
        board.push(move)
        
        # Store move with capture information
        move_info = {
            'move': move,
            'captured': captured_piece.symbol() if captured_piece else None,
            'captured_color': 'white' if captured_piece and captured_piece.color == chess.WHITE else 'black' if captured_piece else None
        }
        game_state['move_history'].append(move_info)
        
        # Update PGN
        game_state['node'] = game_state['node'].add_variation(move)
        
        # Check if game is over
        if board.is_game_over():
            result = board.result()
            game_state['game_status'] = 'finished'
            
            # Update stats
            username = game_state['username']
            game_state['game'].headers["Result"] = result
            
            if result == "1-0":
                outcome = "White wins"
                if game_state['human_color'] == chess.WHITE:
                    stats[username]['wins'] += 1
                    # Human won, bot lost
                    game_state['bot_loss_streak'] += 1
                    if game_state['bot_loss_streak'] >= 5:
                        game_state['learning_boost_active'] = True
                else:
                    stats[username]['losses'] += 1
                    # Bot won, reset streak
                    game_state['bot_loss_streak'] = 0
                    game_state['learning_boost_active'] = False
            elif result == "0-1":
                outcome = "Black wins"
                if game_state['human_color'] == chess.BLACK:
                    stats[username]['wins'] += 1
                    # Human won, bot lost
                    game_state['bot_loss_streak'] += 1
                    if game_state['bot_loss_streak'] >= 5:
                        game_state['learning_boost_active'] = True
                else:
                    stats[username]['losses'] += 1
                    # Bot won, reset streak
                    game_state['bot_loss_streak'] = 0
                    game_state['learning_boost_active'] = False
            else:
                outcome = "Draw"
                stats[username]['draws'] += 1
                # Draw, reset streak
                game_state['bot_loss_streak'] = 0
                game_state['learning_boost_active'] = False
            
            stats[username]['games_played'] += 1
            
            # Update learning policy only if user is jakhar
            if username.lower() == "jakhar":
                with policy_lock:
                    update_policy(
                        username, 
                        outcome, 
                        [m['move'] for m in game_state['move_history']], 
                        game_state['human_color'],
                        game_state['learning_boost_active']
                    )
            
            # Save game and stats
            save_game(game_state)
            save_stats(username)
            
            return jsonify({
                'game_id': game_id,
                'board': get_board_array(board),
                'move': move.uci(),
                'current_player': 'white' if board.turn == chess.WHITE else 'black',
                'status': 'finished',
                'result': result,
                'captured_pieces': get_captured_pieces(game_state['move_history']),
                'stats': stats[username],
                'timers': game_state['timers']
            })
        
        # Return updated game state
        return jsonify({
            'game_id': game_id,
            'board': get_board_array(board),
            'move': move.uci(),
            'current_player': 'white' if board.turn == chess.WHITE else 'black',
            'status': 'active',
            'captured_pieces': get_captured_pieces(game_state['move_history']),
            'timers': game_state['timers']
        })

@app.route('/api/bot_move', methods=['POST'])
def bot_move():
    data = request.json
    game_id = data.get('game_id')
    
    with games_lock:
        if game_id not in games:
            return jsonify({'error': 'Game not found'}), 404
        
        game_state = games[game_id]
        board = game_state['board']
        username = game_state['username']
        
        # Update timer for current player (human)
        if game_state['timers_enabled']:
            current_time_val = current_time()
            elapsed = current_time_val - game_state['last_move_time']
            current_player = 'white' if board.turn == chess.WHITE else 'black'
            game_state['timers'][current_player] = max(0, game_state['timers'][current_player] - elapsed)
            game_state['last_move_time'] = current_time_val
            
            # Check if time has expired
            if game_state['timers'][current_player] <= 0:
                # Time's up - current player loses
                game_state['game_status'] = 'finished'
                
                # Determine winner
                if current_player == 'white':
                    result = "0-1"  # Black wins
                    outcome = "Black wins"
                else:
                    result = "1-0"  # White wins
                    outcome = "White wins"
                
                # Update game headers
                game_state['game'].headers["Result"] = result
                
                # Update stats
                if outcome == "White wins":
                    if game_state['human_color'] == chess.WHITE:
                        stats[username]['wins'] += 1
                        # Human won, bot lost
                        game_state['bot_loss_streak'] += 1
                        if game_state['bot_loss_streak'] >= 5:
                            game_state['learning_boost_active'] = True
                    else:
                        stats[username]['losses'] += 1
                        # Bot won, reset streak
                        game_state['bot_loss_streak'] = 0
                        game_state['learning_boost_active'] = False
                else:  # Black wins
                    if game_state['human_color'] == chess.BLACK:
                        stats[username]['wins'] += 1
                        # Human won, bot lost
                        game_state['bot_loss_streak'] += 1
                        if game_state['bot_loss_streak'] >= 5:
                            game_state['learning_boost_active'] = True
                    else:
                        stats[username]['losses'] += 1
                        # Bot won, reset streak
                        game_state['bot_loss_streak'] = 0
                        game_state['learning_boost_active'] = False
                
                stats[username]['games_played'] += 1
                
                # Update learning policy only if user is jakhar
                if username.lower() == "jakhar":
                    with policy_lock:
                        update_policy(
                            username, 
                            outcome, 
                            [m['move'] for m in game_state['move_history']], 
                            game_state['human_color'],
                            game_state['learning_boost_active']
                        )
                
                # Save game and stats
                save_game(game_state)
                save_stats(username)
                
                return jsonify({
                    'game_id': game_id,
                    'status': 'finished',
                    'result': result,
                    'stats': stats[username]
                })
        
        # Get bot move
        move = get_bot_move(board, username, [m['move'] for m in game_state['move_history']])
        
        # Check for capture
        captured_piece = None
        if board.is_capture(move):
            captured_piece = board.piece_at(move.to_square)
        
        # Make the move
        board.push(move)
        
        # Store move with capture information
        move_info = {
            'move': move,
            'captured': captured_piece.symbol() if captured_piece else None,
            'captured_color': 'white' if captured_piece and captured_piece.color == chess.WHITE else 'black' if captured_piece else None
        }
        game_state['move_history'].append(move_info)
        
        # Update PGN
        game_state['node'] = game_state['node'].add_variation(move)
        
        # Update timer for bot move (no time deduction for bot)
        if game_state['timers_enabled']:
            game_state['last_move_time'] = current_time()
        
        # Check if game is over
        if board.is_game_over():
            result = board.result()
            game_state['game_status'] = 'finished'
            
            # Update stats
            game_state['game'].headers["Result"] = result
            
            if result == "1-0":
                outcome = "White wins"
                if game_state['human_color'] == chess.WHITE:
                    stats[username]['wins'] += 1
                    # Human won, bot lost
                    game_state['bot_loss_streak'] += 1
                    if game_state['bot_loss_streak'] >= 5:
                        game_state['learning_boost_active'] = True
                else:
                    stats[username]['losses'] += 1
                    # Bot won, reset streak
                    game_state['bot_loss_streak'] = 0
                    game_state['learning_boost_active'] = False
            elif result == "0-1":
                outcome = "Black wins"
                if game_state['human_color'] == chess.BLACK:
                    stats[username]['wins'] += 1
                    # Human won, bot lost
                    game_state['bot_loss_streak'] += 1
                    if game_state['bot_loss_streak'] >= 5:
                        game_state['learning_boost_active'] = True
                else:
                    stats[username]['losses'] += 1
                    # Bot won, reset streak
                    game_state['bot_loss_streak'] = 0
                    game_state['learning_boost_active'] = False
            else:
                outcome = "Draw"
                stats[username]['draws'] += 1
                # Draw, reset streak
                game_state['bot_loss_streak'] = 0
                game_state['learning_boost_active'] = False
            
            stats[username]['games_played'] += 1
            
            # Update learning policy only if user is jakhar
            if username.lower() == "jakhar":
                with policy_lock:
                    update_policy(
                        username, 
                        outcome, 
                        [m['move'] for m in game_state['move_history']], 
                        game_state['human_color'],
                        game_state['learning_boost_active']
                    )
            
            # Save game and stats
            save_game(game_state)
            save_stats(username)
            
            return jsonify({
                'game_id': game_id,
                'board': get_board_array(board),
                'move': move.uci(),
                'current_player': 'white' if board.turn == chess.WHITE else 'black',
                'status': 'finished',
                'result': result,
                'captured_pieces': get_captured_pieces(game_state['move_history']),
                'stats': stats[username],
                'timers': game_state['timers']
            })
        
        # Return updated game state
        return jsonify({
            'game_id': game_id,
            'board': get_board_array(board),
            'move': move.uci(),
            'current_player': 'white' if board.turn == chess.WHITE else 'black',
            'status': 'active',
            'captured_pieces': get_captured_pieces(game_state['move_history']),
            'timers': game_state['timers']
        })

@app.route('/api/hint', methods=['POST'])
def get_hint():
    data = request.json
    game_id = data.get('game_id')
    
    with games_lock:
        if game_id not in games:
            return jsonify({'error': 'Game not found'}), 404
        
        game_state = games[game_id]
        board = game_state['board']
        username = game_state['username']
        
        # Get hint move
        move = get_hint_move(board, username, [m['move'] for m in game_state['move_history']])
        
        return jsonify({
            'game_id': game_id,
            'hint': move.uci(),
            'from_square': chess.square_name(move.from_square),
            'to_square': chess.square_name(move.to_square)
        })

@app.route('/api/undo', methods=['POST'])
def undo_move():
    data = request.json
    game_id = data.get('game_id')
    
    with games_lock:
        if game_id not in games:
            return jsonify({'error': 'Game not found'}), 404
        
        game_state = games[game_id]
        board = game_state['board']
        
        if len(game_state['move_history']) == 0:
            return jsonify({'error': 'No moves to undo'}), 400
        
        # Get the last move info
        last_move_info = game_state['move_history'].pop()
        last_move = last_move_info['move']
        
        # Undo the move
        board.pop()
        
        # Update PGN (this is simplified - in a real implementation, you'd need to rebuild the PGN)
        game_state['node'] = game_state['game']
        for move_info in game_state['move_history']:
            game_state['node'] = game_state['node'].add_variation(move_info['move'])
        
        # Update game status
        game_state['game_status'] = 'active'
        
        # Update timer for the player whose turn it is now
        if game_state['timers_enabled']:
            game_state['last_move_time'] = current_time()
        
        # Return updated game state
        return jsonify({
            'game_id': game_id,
            'board': get_board_array(board),
            'current_player': 'white' if board.turn == chess.WHITE else 'black',
            'status': 'active',
            'captured_pieces': get_captured_pieces(game_state['move_history']),
            'timers': game_state['timers']
        })

@app.route('/api/resign', methods=['POST'])
def resign():
    data = request.json
    game_id = data.get('game_id')
    
    with games_lock:
        if game_id not in games:
            return jsonify({'error': 'Game not found'}), 404
        
        game_state = games[game_id]
        username = game_state['username']
        
        # Set result based on who is resigning
        if game_state['human_color'] == chess.WHITE:
            result = "0-1"  # Black wins
            outcome = "Black wins"
        else:
            result = "1-0"  # White wins
            outcome = "White wins"
        
        game_state['game_status'] = 'finished'
        game_state['game'].headers["Result"] = result
        
        # Update stats
        if game_state['human_color'] == chess.WHITE:
            stats[username]['losses'] += 1
        else:
            stats[username]['wins'] += 1
        
        stats[username]['games_played'] += 1
        
        # Update learning policy only if user is jakhar
        if username.lower() == "jakhar":
            with policy_lock:
                update_policy(
                    username, 
                    outcome, 
                    [m['move'] for m in game_state['move_history']], 
                    game_state['human_color'],
                    game_state['learning_boost_active']
                )
        
        # Save game and stats
        save_game(game_state)
        save_stats(username)
        
        return jsonify({
            'game_id': game_id,
            'status': 'finished',
            'result': result,
            'stats': stats[username]
        })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    username = request.args.get('username', 'Guest')
    
    if username not in stats:
        load_stats(username)
    
    return jsonify({
        'username': username,
        'stats': stats.get(username, {'wins': 0, 'losses': 0, 'draws': 0, 'games_played': 0})
    })

@app.route('/api/timers', methods=['GET'])
def get_timers():
    game_id = request.args.get('game_id')
    
    with games_lock:
        if game_id not in games:
            return jsonify({'error': 'Game not found'}), 404
        
        game_state = games[game_id]
        
        # Update timers based on elapsed time
        if game_state['timers_enabled'] and game_state['game_status'] == 'active':
            current_time_val = current_time()
            elapsed = current_time_val - game_state['last_move_time']
            current_player = 'white' if game_state['board'].turn == chess.WHITE else 'black'
            game_state['timers'][current_player] = max(0, game_state['timers'][current_player] - elapsed)
            game_state['last_move_time'] = current_time_val
            
            # Check if time has expired
            if game_state['timers'][current_player] <= 0:
                # Time's up - current player loses
                game_state['game_status'] = 'finished'
                
                # Determine winner
                if current_player == 'white':
                    result = "0-1"  # Black wins
                    outcome = "Black wins"
                else:
                    result = "1-0"  # White wins
                    outcome = "White wins"
                
                # Update game headers
                game_state['game'].headers["Result"] = result
                
                # Update stats
                username = game_state['username']
                if outcome == "White wins":
                    if game_state['human_color'] == chess.WHITE:
                        stats[username]['wins'] += 1
                        # Human won, bot lost
                        game_state['bot_loss_streak'] += 1
                        if game_state['bot_loss_streak'] >= 5:
                            game_state['learning_boost_active'] = True
                    else:
                        stats[username]['losses'] += 1
                        # Bot won, reset streak
                        game_state['bot_loss_streak'] = 0
                        game_state['learning_boost_active'] = False
                else:  # Black wins
                    if game_state['human_color'] == chess.BLACK:
                        stats[username]['wins'] += 1
                        # Human won, bot lost
                        game_state['bot_loss_streak'] += 1
                        if game_state['bot_loss_streak'] >= 5:
                            game_state['learning_boost_active'] = True
                    else:
                        stats[username]['losses'] += 1
                        # Bot won, reset streak
                        game_state['bot_loss_streak'] = 0
                        game_state['learning_boost_active'] = False
                
                stats[username]['games_played'] += 1
                
                # Update learning policy only if user is jakhar
                if username.lower() == "jakhar":
                    with policy_lock:
                        update_policy(
                            username, 
                            outcome, 
                            [m['move'] for m in game_state['move_history']], 
                            game_state['human_color'],
                            game_state['learning_boost_active']
                        )
                
                # Save game and stats
                save_game(game_state)
                save_stats(username)
        
        return jsonify({
            'game_id': game_id,
            'timers': game_state['timers'],
            'status': game_state['game_status']
        })

def get_board_array(board):
    # Convert the chess board to a 2D array representation
    board_array = []
    for rank in range(7, -1, -1):
        row = []
        for file in range(8):
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            if piece:
                color = 'w' if piece.color == chess.WHITE else 'b'
                piece_type = piece.symbol().lower()
                row.append(f"{color}{piece_type}")
            else:
                row.append('')
        board_array.append(row)
    return board_array

def get_captured_pieces(move_history):
    # Calculate captured pieces from move history
    captured_white = []
    captured_black = []
    
    for move_info in move_history:
        if move_info['captured']:
            if move_info['captured_color'] == 'white':
                captured_white.append(move_info['captured'])
            else:
                captured_black.append(move_info['captured'])
    
    return {
        'white': captured_white,
        'black': captured_black
    }

def save_game(game_state):
    # Set result in PGN
    result = game_state['board'].result() if game_state['game_status'] == 'finished' else '*'
    game_state['game'].headers["Result"] = result
    
    # Save PGN file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    username = game_state['username']
    filename = f"games/{timestamp}_{username}_vs_sachin.pgn"
    
    with open(filename, "w") as f:
        exporter = chess.pgn.FileExporter(f)
        game_state['game'].accept(exporter)
    
    # Show confirmation
    print(f"Game saved as {filename}")

if __name__ == '__main__':
    app.run(debug=True)