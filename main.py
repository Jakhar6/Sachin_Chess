# main.py
import chess
import chess.pgn
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import os
import pickle
import json
from datetime import datetime
import random
from collections import defaultdict
import time

class SachinChess:
    def __init__(self, root):
        self.root = root
        self.root.title("Sachin - Personal Chess Bot")
        self.root.geometry("1000x800")
        self.root.configure(bg='#2c3e50')
        
        # Get username
        self.username = self.get_username()
        
        # Initialize game state
        self.board = chess.Board()
        self.game = chess.pgn.Game()
        self.game.headers["Event"] = f"{self.username} vs Sachin"
        self.node = self.game
        self.human_color = chess.WHITE
        self.bot_thinking = False
        self.game_history = []
        self.move_history = []
        self.selected_square = None
        self.last_move_squares = []
        
        # Stats
        self.stats = {'wins': 0, 'losses': 0, 'draws': 0, 'games_played': 0}
        
        # Learning policy
        self.policy = defaultdict(lambda: defaultdict(int))
        self.learning_params = {
            'win_reward': 1,
            'draw_reward': 0.5,
            'loss_reward': -1,
            'decay_factor': 0.9,
            'window_size': 100,
        }
        
        # Create directories if they don't exist
        os.makedirs("games", exist_ok=True)
        os.makedirs("memory", exist_ok=True)
        os.makedirs(f"memory/{self.username}", exist_ok=True)
        
        # Setup UI first
        self.setup_ui()
        
        # Then load previous data
        self.load_policy()
        self.load_stats()
        
        # Start a new game
        self.new_game()

    def get_username(self):
        # Prompt for username
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        username = simpledialog.askstring("Username", "Enter your username:", parent=root)
        root.destroy()
        
        return username if username else "Guest"

    def setup_ui(self):
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#2c3e50')
        style.configure('TLabel', background='#2c3e50', foreground='#ecf0f1')
        style.configure('TButton', background='#3498db', foreground='black')
        style.map('TButton', background=[('active', '#2980b9')])
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        
        # Main frames
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        ttk.Label(title_frame, text=f"Sachin - Personal Chess Bot", style='Title.TLabel').grid(row=0, column=0)
        ttk.Label(title_frame, text=f"Player: {self.username}").grid(row=1, column=0)
        
        # Board frame
        board_frame = ttk.Frame(main_frame)
        board_frame.grid(row=1, column=0, padx=10, pady=10)
        
        # Control frame
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=1, column=1, padx=10, pady=10, sticky=tk.N)
        
        # Create board with larger size
        self.canvas = tk.Canvas(board_frame, width=640, height=640, bg='#34495e', highlightthickness=0)
        self.canvas.grid(row=0, column=0)
        self.canvas.bind("<Button-1>", self.on_square_click)
        
        # Draw empty board
        self.draw_board()
        
        # Control buttons
        button_options = {'pady': 8, 'sticky': tk.EW, 'ipady': 5}
        ttk.Button(control_frame, text="New Game", command=self.new_game).grid(row=0, column=0, **button_options)
        ttk.Button(control_frame, text="Resign", command=self.resign).grid(row=1, column=0, **button_options)
        ttk.Button(control_frame, text="Offer Draw", command=self.offer_draw).grid(row=2, column=0, **button_options)
        
        # Only show settings and game history for jakhar
        if self.username.lower() == "jakhar":
            ttk.Button(control_frame, text="Settings", command=self.show_settings).grid(row=3, column=0, **button_options)
            ttk.Button(control_frame, text="Game History", command=self.show_game_history).grid(row=4, column=0, **button_options)
        
        ttk.Button(control_frame, text="Save Game", command=self.save_game).grid(row=5, column=0, **button_options)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(control_frame, text="Stats")
        stats_frame.grid(row=6, column=0, pady=10, sticky=tk.EW)
        
        self.stats_label = ttk.Label(stats_frame, text="Games: 0\nWins: 0\nLosses: 0\nDraws: 0", font=('Arial', 10))
        self.stats_label.grid(row=0, column=0, pady=5)
        
        # Move list
        move_frame = ttk.LabelFrame(control_frame, text="Moves")
        move_frame.grid(row=7, column=0, pady=10, sticky=tk.EW)
        
        self.move_list = tk.Listbox(move_frame, height=15, width=25, bg='#ecf0f1', font=('Courier', 10))
        scrollbar = ttk.Scrollbar(move_frame, orient=tk.VERTICAL, command=self.move_list.yview)
        self.move_list.configure(yscrollcommand=scrollbar.set)
        self.move_list.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Welcome to Sachin Chess!")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, background='#34495e', foreground='#ecf0f1')
        status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=0)
        main_frame.rowconfigure(1, weight=1)
        move_frame.columnconfigure(0, weight=1)
        move_frame.rowconfigure(0, weight=1)

    def draw_board(self):
        self.canvas.delete("all")
        square_size = 80  # Increased from 60 to 80
        
        # Draw squares
        for row in range(8):
            for col in range(8):
                x1, y1 = col * square_size, (7 - row) * square_size
                x2, y2 = x1 + square_size, y1 + square_size
                
                # Use more visually appealing colors
                color = "#f0d9b5" if (row + col) % 2 == 0 else "#b58863"
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="", width=0)
                
                # Draw coordinate labels
                if col == 0:
                    self.canvas.create_text(x1 + 10, y1 + 10, text=str(8 - row), font=("Arial", 10), fill="#2c3e50")
                if row == 7:
                    self.canvas.create_text(x2 - 10, y2 - 10, text=chr(97 + col), font=("Arial", 10), fill="#2c3e50")
                
                # Draw pieces with better visibility
                square = chess.square(col, row)
                piece = self.board.piece_at(square)
                
                if piece:
                    piece_symbol = self.get_piece_symbol(piece)
                    # Use different colors and styles for white and black pieces
                    if piece.color == chess.WHITE:
                        # White pieces with dark outline for contrast
                        text_color = "#FFFFFF"  # White
                        outline_color = "#2c3e50"  # Dark blue for outline
                    else:
                        # Black pieces with white outline for contrast
                        text_color = "#000000"  # Black
                        outline_color = "#FFFFFF"  # White for outline
                    
                    bg_color = "#f0d9b5" if (row + col) % 2 == 0 else "#b58863"
                    
                    # Draw a subtle background for better piece visibility
                    self.canvas.create_rectangle(x1+5, y1+5, x2-5, y2-5, fill=bg_color, outline="")
                    
                    # Draw outline for better visibility
                    for dx, dy in [(1, 1), (1, -1), (-1, 1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1)]:
                        self.canvas.create_text(
                            x1 + square_size // 2 + dx, 
                            y1 + square_size // 2 + dy, 
                            text=piece_symbol, 
                            font=("Arial", 36, "bold"),
                            fill=outline_color
                        )
                    
                    # Draw the main piece
                    self.canvas.create_text(
                        x1 + square_size // 2, 
                        y1 + square_size // 2, 
                        text=piece_symbol, 
                        font=("Arial", 36, "bold"),
                        fill=text_color
                    )
        
        # Highlight last move with a more visible color
        for square in self.last_move_squares:
            col, row = chess.square_file(square), chess.square_rank(square)
            x1, y1 = col * square_size, (7 - row) * square_size
            x2, y2 = x1 + square_size, y1 + square_size
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#e74c3c", width=3)
        
        # Highlight selected square
        if self.selected_square is not None:
            col, row = chess.square_file(self.selected_square), chess.square_rank(self.selected_square)
            x1, y1 = col * square_size, (7 - row) * square_size
            x2, y2 = x1 + square_size, y1 + square_size
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#3498db", width=4, dash=(4, 4))

    def get_piece_symbol(self, piece):
        # Use Unicode chess symbols for better visibility
        symbols = {
            chess.PAWN: "♙" if piece.color == chess.WHITE else "♟",
            chess.KNIGHT: "♘" if piece.color == chess.WHITE else "♞",
            chess.BISHOP: "♗" if piece.color == chess.WHITE else "♝",
            chess.ROOK: "♖" if piece.color == chess.WHITE else "♜",
            chess.QUEEN: "♕" if piece.color == chess.WHITE else "♛",
            chess.KING: "♔" if piece.color == chess.WHITE else "♚"
        }
        return symbols[piece.piece_type]

    def on_square_click(self, event):
        if self.bot_thinking or self.board.is_game_over():
            return
            
        col = event.x // 80  # Adjusted for larger square size
        row = 7 - (event.y // 80)  # Adjusted for larger square size
        square = chess.square(col, row)
        
        # If a square is already selected, try to move
        if self.selected_square is not None:
            move = chess.Move(self.selected_square, square)
            
            # Check for promotion
            if (self.board.piece_type_at(self.selected_square) == chess.PAWN and 
                chess.square_rank(square) in [0, 7]):
                # Ask for promotion piece
                promotion_piece = self.get_promotion_piece()
                if promotion_piece:
                    move = chess.Move(self.selected_square, square, promotion=promotion_piece)
            
            if move in self.board.legal_moves:
                self.make_move(move)
                self.selected_square = None
            else:
                self.selected_square = square
        else:
            # Select a piece if it's the player's turn
            piece = self.board.piece_at(square)
            if piece and piece.color == self.human_color:
                self.selected_square = square
        
        self.draw_board()

    def get_promotion_piece(self):
        # Simple promotion dialog
        result = messagebox.askquestion("Promotion", "Promote to Queen?", 
                                       detail="Click 'Yes' for Queen, 'No' for other options")
        if result == 'yes':
            return chess.QUEEN
        else:
            # For simplicity, we'll just use Queen
            # In a more complete implementation, you'd offer a choice
            return chess.QUEEN

    def make_move(self, move):
        self.board.push(move)
        self.last_move_squares = [move.from_square, move.to_square]
        
        # Update PGN
        self.node = self.node.add_variation(move)
        
        # Update move list
        move_num = (len(self.move_history) // 2) + 1
        if self.human_color == chess.WHITE:
            if len(self.move_history) % 2 == 0:
                move_text = f"{move_num}. {move.uci()}"
            else:
                move_text = f"{move_num}... {move.uci()}"
        else:
            if len(self.move_history) % 2 == 1:
                move_text = f"{move_num}. {move.uci()}"
            else:
                move_text = f"{move_num}... {move.uci()}"
                
        self.move_list.insert(tk.END, move_text)
        self.move_list.see(tk.END)
        self.move_history.append(move)
        
        # Check if game is over
        if self.board.is_game_over():
            self.handle_game_over()
        else:
            # Bot's turn if it's not human's turn
            if self.board.turn != self.human_color:
                self.bot_move()

    def bot_move(self):
        self.bot_thinking = True
        self.status_var.set("Sachin is thinking...")
        self.root.update()
        
        # Get bot move
        move = self.get_bot_move()
        
        # Add a small delay for realism
        time.sleep(0.5)
        
        self.make_move(move)
        self.bot_thinking = False
        self.status_var.set("Your turn")

    def get_bot_move(self):
        fen = self.get_normalized_fen()
        
        # Check if we have policy for this position
        if fen in self.policy and self.policy[fen]:
            moves, weights = zip(*self.policy[fen].items())
            # Filter to only legal moves
            legal_moves = [m for m in moves if chess.Move.from_uci(m) in self.board.legal_moves]
            legal_weights = [self.policy[fen][m] for m in legal_moves]
            
            if legal_moves and sum(legal_weights) > 0:
                move_uci = random.choices(legal_moves, weights=legal_weights, k=1)[0]
                return chess.Move.from_uci(move_uci)
        
        # Fallback to heuristic if no policy
        return self.get_heuristic_move()

    def get_heuristic_move(self):
        legal_moves = list(self.board.legal_moves)
        scored_moves = []
        
        for move in legal_moves:
            score = 0
            
            # Prefer captures that gain material
            if self.board.is_capture(move):
                captured_piece = self.board.piece_at(move.to_square)
                if captured_piece:
                    score += self.get_piece_value(captured_piece.piece_type)
            
            # Prefer checks
            self.board.push(move)
            if self.board.is_check():
                score += 1
            self.board.pop()
            
            # Prefer developing moves in early game
            if len(self.move_history) < 20:
                piece = self.board.piece_at(move.from_square)
                if piece and piece.piece_type == chess.PAWN:
                    score -= 0.1  # Slightly discourage early pawn moves
                elif piece and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                    score += 0.2  # Encourage developing minor pieces
            
            scored_moves.append((move, score))
        
        # Sort by score and pick the best move
        scored_moves.sort(key=lambda x: x[1], reverse=True)
        best_score = scored_moves[0][1]
        best_moves = [m for m, s in scored_moves if s == best_score]
        
        return random.choice(best_moves) if best_moves else random.choice(legal_moves)

    def get_piece_value(self, piece_type):
        values = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 0
        }
        return values.get(piece_type, 0)

    def get_normalized_fen(self):
        # Normalize FEN by removing move counters
        return ' '.join(self.board.fen().split()[:4])

    def handle_game_over(self):
        result = self.board.result()
        self.status_var.set(f"Game over: {result}")
        
        # Update stats
        self.stats['games_played'] += 1
        
        if result == "1-0":
            outcome = "White wins"
            if self.human_color == chess.WHITE:
                self.stats['wins'] += 1
            else:
                self.stats['losses'] += 1
        elif result == "0-1":
            outcome = "Black wins"
            if self.human_color == chess.BLACK:
                self.stats['wins'] += 1
            else:
                self.stats['losses'] += 1
        else:
            outcome = "Draw"
            self.stats['draws'] += 1
        
        # Update learning policy only if user is jakhar
        if self.username.lower() == "jakhar":
            self.update_policy(outcome)
        
        # Always save game for jakhar, for others only save if not a guest
        if self.username.lower() == "jakhar" or self.username != "Guest":
            self.save_game()
        
        # Show result
        messagebox.showinfo("Game Over", f"Game ended: {outcome}")
        
        # Update stats display
        self.update_stats_display()

    def update_policy(self, outcome):
        reward = 0
        
        if outcome == "White wins":
            reward = self.learning_params['win_reward'] if self.human_color == chess.WHITE else self.learning_params['loss_reward']
        elif outcome == "Black wins":
            reward = self.learning_params['win_reward'] if self.human_color == chess.BLACK else self.learning_params['loss_reward']
        else:  # Draw
            reward = self.learning_params['draw_reward']
        
        # Replay the game and update policy for human moves
        temp_board = chess.Board()
        for i, move in enumerate(self.move_history):
            if temp_board.turn == self.human_color:
                fen = self.get_normalized_fen_from_board(temp_board)
                move_uci = move.uci()
                self.policy[fen][move_uci] += reward
            
            temp_board.push(move)
        
        # Save updated policy
        self.save_policy()

    def get_normalized_fen_from_board(self, board):
        return ' '.join(board.fen().split()[:4])

    def new_game(self):
        # Reset board
        self.board = chess.Board()
        self.game = chess.pgn.Game()
        self.game.headers["Event"] = f"{self.username} vs Sachin"
        self.node = self.game
        self.move_history = []
        self.last_move_squares = []
        self.selected_square = None
        
        # Ask for color preference
        color = messagebox.askquestion("Color Selection", "Do you want to play as White?")
        self.human_color = chess.WHITE if color == 'yes' else chess.BLACK
        
        # Set up game headers
        self.game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
        self.game.headers["White"] = self.username if self.human_color == chess.WHITE else "Sachin"
        self.game.headers["Black"] = "Sachin" if self.human_color == chess.WHITE else self.username
        
        # Clear move list
        self.move_list.delete(0, tk.END)
        
        # Draw board
        self.draw_board()
        
        # Bot starts if human is black
        if self.human_color == chess.BLACK:
            self.status_var.set("Sachin is thinking...")
            self.root.after(500, self.bot_move)
        else:
            self.status_var.set("Your turn")

    def resign(self):
        if messagebox.askyesno("Resign", "Are you sure you want to resign?"):
            outcome = "Black wins" if self.human_color == chess.WHITE else "White wins"
            self.handle_game_over()

    def offer_draw(self):
        # Simple implementation - just accept all draw offers
        if messagebox.askyesno("Draw Offer", "Sachin accepts the draw offer. Agree to draw?"):
            self.board.set_board_fen(self.board.board_fen())  # Force game to continue
            self.handle_game_over()

    def show_settings(self):
        # Only allow settings for jakhar
        if self.username.lower() != "jakhar":
            messagebox.showinfo("Settings", "Settings are only available for user 'jakhar'")
            return
            
        # Create settings dialog
        settings = tk.Toplevel(self.root)
        settings.title("Learning Settings")
        settings.geometry("300x250")
        settings.configure(bg='#2c3e50')
        
        ttk.Label(settings, text="Win Reward:").grid(row=0, column=0, padx=5, pady=5)
        win_reward = ttk.Entry(settings)
        win_reward.insert(0, str(self.learning_params['win_reward']))
        win_reward.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(settings, text="Draw Reward:").grid(row=1, column=0, padx=5, pady=5)
        draw_reward = ttk.Entry(settings)
        draw_reward.insert(0, str(self.learning_params['draw_reward']))
        draw_reward.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(settings, text="Loss Reward:").grid(row=2, column=0, padx=5, pady=5)
        loss_reward = ttk.Entry(settings)
        loss_reward.insert(0, str(self.learning_params['loss_reward']))
        loss_reward.grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(settings, text="Decay Factor:").grid(row=3, column=0, padx=5, pady=5)
        decay_factor = ttk.Entry(settings)
        decay_factor.insert(0, str(self.learning_params['decay_factor']))
        decay_factor.grid(row=3, column=1, padx=5, pady=5)
        
        ttk.Label(settings, text="Window Size:").grid(row=4, column=0, padx=5, pady=5)
        window_size = ttk.Entry(settings)
        window_size.insert(0, str(self.learning_params['window_size']))
        window_size.grid(row=4, column=1, padx=5, pady=5)
        
        def save_settings():
            try:
                self.learning_params['win_reward'] = float(win_reward.get())
                self.learning_params['draw_reward'] = float(draw_reward.get())
                self.learning_params['loss_reward'] = float(loss_reward.get())
                self.learning_params['decay_factor'] = float(decay_factor.get())
                self.learning_params['window_size'] = int(window_size.get())
                settings.destroy()
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numbers")
        
        ttk.Button(settings, text="Save", command=save_settings).grid(row=5, column=0, columnspan=2, pady=10)

    def show_game_history(self):
        # Only allow game history for jakhar
        if self.username.lower() != "jakhar":
            messagebox.showinfo("Game History", "Game history is only available for user 'jakhar'")
            return
            
        # Create game history dialog
        history = tk.Toplevel(self.root)
        history.title("Game History")
        history.geometry("800x600")
        history.configure(bg='#2c3e50')
        
        # Create a frame for the list of games
        list_frame = ttk.Frame(history)
        list_frame.grid(row=0, column=0, padx=10, pady=10, sticky=(tk.N, tk.S, tk.E, tk.W))
        
        # Create a listbox with scrollbar
        games_list = tk.Listbox(list_frame, width=50, height=20, bg='#ecf0f1', font=('Arial', 10))
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=games_list.yview)
        games_list.configure(yscrollcommand=scrollbar.set)
        games_list.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Create a text widget to display selected game
        text_frame = ttk.Frame(history)
        text_frame.grid(row=0, column=1, padx=10, pady=10, sticky=(tk.N, tk.S, tk.E, tk.W))
        
        game_text = scrolledtext.ScrolledText(text_frame, width=50, height=20, bg='#ecf0f1', font=('Courier', 10))
        game_text.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        
        # Populate the list with game files
        game_files = []
        if os.path.exists("games"):
            for file in os.listdir("games"):
                if file.endswith(".pgn"):
                    game_files.append(file)
        
        for file in sorted(game_files, reverse=True):
            games_list.insert(tk.END, file)
        
        def show_selected_game(event):
            selection = games_list.curselection()
            if selection:
                filename = games_list.get(selection[0])
                with open(f"games/{filename}", "r") as f:
                    content = f.read()
                    game_text.delete(1.0, tk.END)
                    game_text.insert(tk.END, content)
        
        games_list.bind('<<ListboxSelect>>', show_selected_game)
        
        # Configure grid weights
        history.columnconfigure(0, weight=1)
        history.columnconfigure(1, weight=1)
        history.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

    def save_game(self):
        # Set result in PGN
        result = self.board.result()
        self.game.headers["Result"] = result
        
        # Save PGN file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"games/{timestamp}_{self.username}_vs_sachin.pgn"
        
        with open(filename, "w") as f:
            exporter = chess.pgn.FileExporter(f)
            self.game.accept(exporter)
        
        # Add to game history
        self.game_history.append(filename)
        
        # Save stats
        self.save_stats()
        
        # Show confirmation
        self.status_var.set(f"Game saved as {filename}")

    def save_policy(self):
        # Convert defaultdict to regular dict for serialization
        policy_dict = {k: dict(v) for k, v in self.policy.items()}
        
        # Save policy for the current user
        policy_file = f"memory/{self.username}/policy.pkl"
        with open(policy_file, "wb") as f:
            pickle.dump(policy_dict, f)

    def load_policy(self):
        # Try to load policy for the current user
        policy_file = f"memory/{self.username}/policy.pkl"
        
        # If user is not jakhar, try to load jakhar's policy
        if self.username.lower() != "jakhar" and not os.path.exists(policy_file):
            policy_file = "memory/jakhar/policy.pkl"
        
        try:
            with open(policy_file, "rb") as f:
                policy_dict = pickle.load(f)
                self.policy = defaultdict(lambda: defaultdict(int))
                for k, v in policy_dict.items():
                    self.policy[k] = defaultdict(int, v)
        except FileNotFoundError:
            self.policy = defaultdict(lambda: defaultdict(int))

    def save_stats(self):
        # Save stats for the current user
        stats_file = f"memory/{self.username}/stats.json"
        with open(stats_file, "w") as f:
            json.dump(self.stats, f)

    def load_stats(self):
        # Try to load stats for the current user
        stats_file = f"memory/{self.username}/stats.json"
        
        # If user is not jakhar, try to load jakhar's stats
        if self.username.lower() != "jakhar" and not os.path.exists(stats_file):
            stats_file = "memory/jakhar/stats.json"
        
        try:
            with open(stats_file, "r") as f:
                self.stats = json.load(f)
                self.update_stats_display()
        except FileNotFoundError:
            self.stats = {'wins': 0, 'losses': 0, 'draws': 0, 'games_played': 0}

    def update_stats_display(self):
        stats_text = f"Games: {self.stats['games_played']}\nWins: {self.stats['wins']}\nLosses: {self.stats['losses']}\nDraws: {self.stats['draws']}"
        self.stats_label.config(text=stats_text)

if __name__ == "__main__":
    root = tk.Tk()
    app = SachinChess(root)
    root.mainloop()