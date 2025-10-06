#!/usr/bin/env python3
"""Initialize shared git repository in books/ directory.

This script creates the shared git repository at books/.git if it doesn't exist.
Normally, this happens automatically when the application starts, but you can
run this script manually if needed.
"""
import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Set PYTHONPATH for imports
os.environ['PYTHONPATH'] = str(src_path)

from storage.git_manager import GitManager


def main():
    """Initialize shared git repository."""
    # Get books directory from environment or use default
    books_dir = Path(os.environ.get('BOOKS_DIR', 'books')).resolve()
    git_dir = books_dir / ".git"

    print(f"Books directory: {books_dir}")
    print(f"Git directory: {git_dir}")
    print()

    # Check if git already exists
    if git_dir.exists():
        print("✓ Git repository already exists")
        print()

        # Show status
        git = GitManager(books_dir)
        try:
            status = git.status()
            if status:
                print("Git status:")
                print(status)
            else:
                print("Working tree clean")
        except Exception as e:
            print(f"Error checking status: {e}")

        return

    # Create books directory if needed
    if not books_dir.exists():
        print(f"Creating books directory: {books_dir}")
        books_dir.mkdir(parents=True, exist_ok=True)

    # Initialize git
    print("Initializing git repository...")
    git = GitManager(books_dir)

    if git.init():
        print("✓ Git repository initialized")

        # Create initial commit
        try:
            git.commit("Initialize books repository")
            print("✓ Initial commit created")
        except Exception as e:
            print(f"Warning: Could not create initial commit: {e}")

        print()
        print("Shared git repository is ready!")
        print()
        print("All projects in books/ will share this repository.")
        print("Commits will be prefixed with project names:")
        print("  [my-novel] Generate premise: fantasy")
        print("  [sci-fi-story] Iterate chapter 3: add dialogue")
    else:
        print("✗ Failed to initialize git repository")
        sys.exit(1)


if __name__ == "__main__":
    main()
