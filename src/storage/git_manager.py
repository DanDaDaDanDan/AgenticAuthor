"""Git integration for version control."""
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime


class GitManager:
    """Manage git operations for a project."""

    def __init__(self, project_path: Path):
        """
        Initialize git manager.

        Args:
            project_path: Path to project directory
        """
        self.project_path = Path(project_path).resolve()

    def init(self) -> bool:
        """
        Initialize a new git repository.

        Returns:
            True if successful
        """
        try:
            self._run_git("init")

            # Set default user if not configured
            try:
                self._run_git("config", "user.name")
            except subprocess.CalledProcessError:
                self._run_git("config", "user.name", "AgenticAuthor")
                self._run_git("config", "user.email", "agentic@localhost")

            # Create initial gitignore
            gitignore = self.project_path / ".gitignore"
            if not gitignore.exists():
                gitignore.write_text(
                    "# AgenticAuthor\n"
                    "*.pyc\n"
                    "__pycache__/\n"
                    ".env\n"
                    ".cache/\n"
                    "exports/*.tmp\n"
                )

            return True
        except subprocess.CalledProcessError:
            return False

    def status(self) -> str:
        """
        Get git status.

        Returns:
            Git status output
        """
        try:
            return self._run_git("status", "--short")
        except subprocess.CalledProcessError as e:
            return f"Error: {e.stderr}"

    def add(self, files: Optional[List[str]] = None) -> bool:
        """
        Add files to staging.

        Args:
            files: List of files to add (None for all)

        Returns:
            True if successful
        """
        try:
            if files:
                self._run_git("add", *files)
            else:
                self._run_git("add", ".")
            return True
        except subprocess.CalledProcessError:
            return False

    def commit(self, message: str, files: Optional[List[str]] = None) -> bool:
        """
        Create a commit.

        Args:
            message: Commit message
            files: Optional list of files to commit

        Returns:
            True if successful
        """
        try:
            # Add files if specified
            if files:
                self.add(files)
            else:
                self.add()

            # Check if there are changes to commit
            status = self.status()
            if not status:
                return True  # Nothing to commit

            # Create commit
            self._run_git("commit", "-m", message)
            return True
        except subprocess.CalledProcessError:
            return False

    def diff(self, cached: bool = False, file: Optional[str] = None) -> str:
        """
        Get git diff.

        Args:
            cached: Show staged changes
            file: Specific file to diff

        Returns:
            Diff output
        """
        try:
            args = ["diff"]
            if cached:
                args.append("--cached")
            if file:
                args.append(file)
            return self._run_git(*args)
        except subprocess.CalledProcessError:
            return ""

    def log(self, limit: int = 10, oneline: bool = True) -> str:
        """
        Get git log.

        Args:
            limit: Number of commits to show
            oneline: Use oneline format

        Returns:
            Log output
        """
        try:
            args = ["log", f"-{limit}"]
            if oneline:
                args.append("--oneline")
            return self._run_git(*args)
        except subprocess.CalledProcessError:
            return ""

    def current_sha(self) -> Optional[str]:
        """
        Get current commit SHA.

        Returns:
            SHA or None
        """
        try:
            sha = self._run_git("rev-parse", "HEAD").strip()
            return sha[:7]  # Short SHA
        except subprocess.CalledProcessError:
            return None

    def rollback(self, steps: int = 1) -> bool:
        """
        Rollback commits.

        Args:
            steps: Number of commits to rollback

        Returns:
            True if successful
        """
        try:
            self._run_git("reset", "--hard", f"HEAD~{steps}")
            return True
        except subprocess.CalledProcessError:
            return False

    def checkout(self, branch: str) -> bool:
        """
        Checkout a branch.

        Args:
            branch: Branch name

        Returns:
            True if successful
        """
        try:
            self._run_git("checkout", branch)
            return True
        except subprocess.CalledProcessError:
            return False

    def create_branch(self, name: str) -> bool:
        """
        Create and checkout a new branch.

        Args:
            name: Branch name

        Returns:
            True if successful
        """
        try:
            self._run_git("checkout", "-b", name)
            return True
        except subprocess.CalledProcessError:
            return False

    def list_branches(self) -> List[str]:
        """
        List all branches.

        Returns:
            List of branch names
        """
        try:
            output = self._run_git("branch")
            branches = []
            for line in output.splitlines():
                branch = line.strip()
                if branch.startswith("*"):
                    branch = branch[2:]
                branches.append(branch)
            return branches
        except subprocess.CalledProcessError:
            return []

    def current_branch(self) -> Optional[str]:
        """
        Get current branch name.

        Returns:
            Branch name or None
        """
        try:
            return self._run_git("rev-parse", "--abbrev-ref", "HEAD").strip()
        except subprocess.CalledProcessError:
            return None

    def auto_commit(self, action: str, details: Optional[str] = None) -> bool:
        """
        Create an automatic commit with descriptive message.

        Args:
            action: Action performed (e.g., "Generate premise")
            details: Optional additional details

        Returns:
            True if successful
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"{action}"
        if details:
            message += f": {details}"
        message += f" [{timestamp}]"

        return self.commit(message)

    def get_file_at_revision(self, file_path: str, revision: str = "HEAD") -> Optional[str]:
        """
        Get file content at a specific revision.

        Args:
            file_path: Relative path to file
            revision: Git revision (SHA, branch, tag, etc.)

        Returns:
            File content or None
        """
        try:
            return self._run_git("show", f"{revision}:{file_path}")
        except subprocess.CalledProcessError:
            return None

    def run_command(self, command: str) -> str:
        """
        Run arbitrary git command.

        Args:
            command: Git command string

        Returns:
            Command output
        """
        try:
            parts = command.split()
            return self._run_git(*parts)
        except subprocess.CalledProcessError as e:
            return f"Error: {e.stderr}"

    def _run_git(self, *args) -> str:
        """
        Run a git command.

        Args:
            *args: Git command arguments

        Returns:
            Command output

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        result = subprocess.run(
            ["git"] + list(args),
            cwd=self.project_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout

    def has_changes(self) -> bool:
        """
        Check if there are uncommitted changes.

        Returns:
            True if there are changes
        """
        return bool(self.status())

    def stash(self, message: Optional[str] = None) -> bool:
        """
        Stash current changes.

        Args:
            message: Optional stash message

        Returns:
            True if successful
        """
        try:
            args = ["stash", "push"]
            if message:
                args.extend(["-m", message])
            self._run_git(*args)
            return True
        except subprocess.CalledProcessError:
            return False

    def stash_pop(self) -> bool:
        """
        Pop the latest stash.

        Returns:
            True if successful
        """
        try:
            self._run_git("stash", "pop")
            return True
        except subprocess.CalledProcessError:
            return False