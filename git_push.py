import subprocess
import sys
from datetime import datetime

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"Success: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}")
        return False

def git_push(commit_message=None):
    # 1. Add all changes
    if not run_command("git add ."):
        return False
    
    # 2. Create commit message
    if not commit_message:
        commit_message = f"Auto update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # 3. Commit changes
    if not run_command(f'git commit -m "{commit_message}"'):
        return False
    
    # 4. Push to remote
    if not run_command("git push"):
        return False
    
    print("Successfully pushed to GitHub!")
    return True

if __name__ == "__main__":
    # Get commit message from command line argument if provided
    commit_message = sys.argv[1] if len(sys.argv) > 1 else None
    git_push(commit_message) 