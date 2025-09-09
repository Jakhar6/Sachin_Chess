#!/usr/bin/env python3
"""
Script to prepare games for GitHub repository.
This script organizes and formats game files for public sharing.
"""

import os
import json
import shutil
from datetime import datetime

def prepare_games():
    # Create the games_github directory if it doesn't exist
    os.makedirs('games_github', exist_ok=True)
    
    # Copy all PGN files from games to games_github
    if os.path.exists('games'):
        for filename in os.listdir('games'):
            if filename.endswith('.pgn'):
                src = os.path.join('games', filename)
                dest = os.path.join('games_github', filename)
                shutil.copy2(src, dest)
                print(f"Copied {filename} to games_github")
    
    # Create a README file with statistics
    create_readme()
    
    print("✅ Games prepared for GitHub")

def create_readme():
    # Try to load stats
    stats = {}
    if os.path.exists('memory/jakhar/stats.json'):
        with open('memory/jakhar/stats.json', 'r') as f:
            stats = json.load(f)
    
    # Create README content
    readme_content = f"""# Sachin Chess Games

This repository contains chess games played against Sachin, the learning chess bot.

## Statistics
- Total games: {stats.get('games_played', 0)}
- Wins: {stats.get('wins', 0)}
- Losses: {stats.get('losses', 0)}
- Draws: {stats.get('draws', 0)}

## About Sachin
Sachin is a chess bot that learns from its games. It uses a policy-based reinforcement learning approach to improve its play over time.

## Game Files
All games are stored in PGN format, which can be viewed with any chess software or online PGN viewer.

Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    # Write README file
    with open('games_github/README.md', 'w') as f:
        f.write(readme_content)

if __name__ == '__main__':
    prepare_games()