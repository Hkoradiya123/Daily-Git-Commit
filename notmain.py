import logging
from datetime import datetime, timezone
from git import InvalidGitRepositoryError, NoSuchPathError, GitCommandError, Repo
from pathlib import Path
from time import sleep

# Configuration
REPO_ROOT = Path(__file__).resolve().parent
FILE_TO_COMMIT = REPO_ROOT / "update_me.yaml"
LOG_FILE = REPO_ROOT / "git_commit.log"
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

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


def write_current_time():
    """Write the current UTC time to the file."""
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        FILE_TO_COMMIT.write_text(f"LAST_UPDATE: {ts}\n")
        logger.info(f"Updated {FILE_TO_COMMIT} with timestamp {ts}")
        return ts
    except Exception as e:
        logger.error(f"Failed to write timestamp: {e}")
        return None


def commit_repo(ts):
    """Commit and push the timestamp update with retry logic."""
    if not ts:
        logger.warning("No timestamp provided, skipping commit.")
        return False
    
    try:
        repo = Repo(REPO_ROOT)
    except (InvalidGitRepositoryError, NoSuchPathError) as e:
        logger.error(f"No git repo found at {REPO_ROOT}: {e}")
        return False
    
    try:
        # Stage and commit
        repo.index.add([str(FILE_TO_COMMIT)])
        commit_obj = repo.index.commit(f"Auto commit at {ts}")
        logger.info(f"Created commit {commit_obj.hexsha[:7]}")
        
        # Push with retry logic
        return push_with_retry(repo, max_retries=MAX_RETRIES)
    
    except GitCommandError as e:
        logger.error(f"Git command failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during commit: {e}")
        return False


def push_with_retry(repo, max_retries=MAX_RETRIES):
    """Push to remote with retry logic for transient failures."""
    for attempt in range(1, max_retries + 1):
        try:
            repo.remote("origin").push()
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


def run_once():
    """Execute one commit cycle."""
    logger.info("Starting commit cycle...")
    timestamp = write_current_time()
    success = commit_repo(timestamp)
    logger.info(f"Commit cycle completed. Status: {'SUCCESS' if success else 'FAILED'}")
    return success


if __name__ == "__main__":
    try:
        run_once()
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.critical(f"Critical error: {e}", exc_info=True)