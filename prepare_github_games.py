import os
import shutil
from datetime import datetime

def prepare_github_games():
    # Paths
    local_games = "games"
    github_games = "games_github"
    
    # Ensure target folder exists
    os.makedirs(github_games, exist_ok=True)
    
    # Get all PGN files sorted by creation time (newest first)
    all_games = []
    if os.path.exists(local_games):
        for f in os.listdir(local_games):
            if f.endswith(".pgn"):
                full_path = os.path.join(local_games, f)
                # Get creation time
                ctime = os.path.getctime(full_path)
                all_games.append((ctime, f))
    
    # Sort by creation time (newest first)
    all_games.sort(key=lambda x: x[0], reverse=True)
    
    # Keep only the last 50
    latest_games = [f[1] for f in all_games[:50]]
    
    # Clear github folder first (remove all PGN files)
    for f in os.listdir(github_games):
        if f.endswith(".pgn"):
            os.remove(os.path.join(github_games, f))
    
    # Copy last 50 games
    for f in latest_games:
        src = os.path.join(local_games, f)
        dst = os.path.join(github_games, f)
        shutil.copy2(src, dst)
    
    print(f"✅ Prepared {len(latest_games)} latest games for GitHub.")
    
    # Also prepare a summary file
    summary_path = os.path.join(github_games, "README.md")
    with open(summary_path, "w") as summary_file:
        summary_file.write("# Last 50 Games\n\n")
        summary_file.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        summary_file.write("| Date | Player | Result |\n")
        summary_file.write("|------|--------|--------|\n")
        
        for game_file in latest_games:
            # Extract info from filename
            parts = game_file.split('_')
            if len(parts) >= 3:
                date_str = parts[0]
                player = parts[1]
                # Try to parse the date
                try:
                    date_obj = datetime.strptime(date_str, "%Y%m%d")
                    formatted_date = date_obj.strftime("%Y-%m-%d")
                except:
                    formatted_date = date_str
                
                # Try to get result from file content
                result = "Unknown"
                try:
                    with open(os.path.join(github_games, game_file), 'r') as f:
                        content = f.read()
                        if "1-0" in content:
                            result = "White wins"
                        elif "0-1" in content:
                            result = "Black wins"
                        elif "1/2-1/2" in content:
                            result = "Draw"
                except:
                    pass
                
                summary_file.write(f"| {formatted_date} | {player} | {result} |\n")

if __name__ == "__main__":
    prepare_github_games()