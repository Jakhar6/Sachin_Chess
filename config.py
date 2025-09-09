# Configuration settings for the chess app

# Server configuration
HOST = '0.0.0.0'
PORT = 5000
DEBUG = True

# File paths
GAMES_DIR = 'games'
MEMORY_DIR = 'memory'
GITHUB_GAMES_DIR = 'games_github'

# Learning parameters
LEARNING_PARAMS = {
    'win_reward': 1,
    'draw_reward': 0.5,
    'loss_reward': -1,
    'decay_factor': 0.9,
    'window_size': 100,
}

# Time control options
TIME_CONTROLS = [
    '1 min',
    '3 min',
    '5 min',
    '10 min',
    '30 min',
    'No limit'
]