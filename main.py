import logging
import yaml
from datetime import datetime
from git import Repo, InvalidGitRepositoryError, NoSuchPathError, GitCommandError
from pathlib import Path
from time import sleep
from random import randint

# Configuration
REPO_ROOT = Path(__file__).resolve().parent
FILE_TO_COMMIT_NAME = REPO_ROOT / 'update_me.yaml'
LOG_FILE = REPO_ROOT / 'git_commit.log'
SLEEP_INTERVAL = 86400  # 24 hours in seconds
MAX_UPDATES_PER_CYCLE = 10
MAX_RETRIES = 3
RETRY_DELAY = 5

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def update_file_to_commit():
    """Update the YAML file with the number of times it has been committed and the last update timestamp."""
    try:
        with open(FILE_TO_COMMIT_NAME, 'r') as file:
            current_data = yaml.safe_load(file)
            if current_data is None:
                update_times = 1
            else:
                update_times = int(current_data.get('UPDATE_TIMES', 0)) + 1
            last_update = datetime.now().strftime("%A %B %d %Y at %I:%M:%S %p")
    except FileNotFoundError:
        logger.warning(f"YAML file not found, creating new one at {FILE_TO_COMMIT_NAME}")
        update_times = 1
        last_update = datetime.now().strftime("%A %B %d %Y at %I:%M:%S %p")
    except (KeyError, TypeError, ValueError) as e:
        logger.error(f"Error reading YAML file: {e}")
        return None
    
    try:
        updated_data = {
            'UPDATE_TIMES': update_times,
            'LAST_UPDATE': last_update
        }
        with open(FILE_TO_COMMIT_NAME, 'w') as file:
            yaml.dump(updated_data, file, default_flow_style=False, sort_keys=True)
        logger.info(f"Updated YAML: {update_times} commits total")
        return updated_data
    except Exception as e:
        logger.error(f"Failed to write YAML file: {e}")
        return None


def commit_repository(yaml_data):
    """Commit the updated YAML file to the Git repository with error handling."""
    if not yaml_data:
        logger.warning("No data to commit")
        return False
    
    try:
        repo = Repo(REPO_ROOT)
    except (InvalidGitRepositoryError, NoSuchPathError) as e:
        logger.error(f"Git repository not found at {REPO_ROOT}: {e}")
        return False
    
    try:
        repo.index.add([str(FILE_TO_COMMIT_NAME)])
        commit_message = f'Updated {yaml_data["UPDATE_TIMES"]} times. Last update was on {yaml_data["LAST_UPDATE"]}.'
        commit_obj = repo.index.commit(commit_message)
        logger.info(f"Created commit {commit_obj.hexsha[:7]}")
        
        return push_with_retry(repo, max_retries=MAX_RETRIES)
    except GitCommandError as e:
        logger.error(f"Git command failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during commit: {e}", exc_info=True)
        return False


def push_with_retry(repo, max_retries=MAX_RETRIES):
    """Push to remote with retry logic for transient failures."""
    for attempt in range(1, max_retries + 1):
        try:
            origin = repo.remote('origin')
            origin.push()
            logger.info("Push to origin succeeded")
            return True
        except GitCommandError as e:
            if attempt < max_retries:
                logger.warning(f"Push failed (attempt {attempt}/{max_retries}): {e}. Retrying in {RETRY_DELAY}s...")
                sleep(RETRY_DELAY)
            else:
                logger.error(f"Push failed after {max_retries} attempts: {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error during push: {e}")
            return False
    return False


def run_update_cycle():
    """Execute a single update cycle with multiple random commits."""
    num_updates = randint(1, MAX_UPDATES_PER_CYCLE)
    logger.info(f"Starting cycle with {num_updates} random updates")
    
    success_count = 0
    for i in range(1, num_updates + 1):
        logger.info(f"Update {i}/{num_updates}")
        updated_data = update_file_to_commit()
        if commit_repository(updated_data):
            success_count += 1
        else:
            logger.warning(f"Update {i} failed")
    
    logger.info(f"Cycle completed: {success_count}/{num_updates} updates successful")
    return success_count == num_updates


if __name__ == '__main__':
    logger.info("Git auto-commit daemon started")
    try:
        while True:
            logger.info(f"Sleeping for {SLEEP_INTERVAL}s (24 hours)...")
            sleep(SLEEP_INTERVAL)
            run_update_cycle()
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")
    except Exception as e:
        logger.critical(f"Critical error: {e}", exc_info=True)
