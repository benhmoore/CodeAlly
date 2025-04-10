#!/usr/bin/env python3
"""Simple version management script.

This script updates the version in code_ally/_version.py and creates a git tag.
The version in pyproject.toml is dynamically linked to _version.py, so only one
update is needed.

Usage:
    python tools/version.py patch  # Increments 0.4.5 to 0.4.6
    python tools/version.py minor  # Increments 0.4.5 to 0.5.0
    python tools/version.py major  # Increments 0.4.5 to 1.0.0
"""

import re
import subprocess
import sys

VERSION_FILE = "code_ally/_version.py"


def get_current_version() -> str:
    """Get the current version from the version file."""
    with open(VERSION_FILE) as f:
        content = f.read()

    match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    if not match:
        raise ValueError(f"Could not find version in {VERSION_FILE}")

    return match.group(1)


def update_version(current: str, part: str) -> str:
    """Update the version based on the part to increment."""
    major, minor, patch = map(int, current.split("."))

    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(f"Unknown part: {part}. Use 'major', 'minor', or 'patch'.")

    return f"{major}.{minor}.{patch}"


def set_version(new_version: str) -> bool:
    """Update the version in the version file."""
    with open(VERSION_FILE) as f:
        content = f.read()

    content = re.sub(
        r'__version__\s*=\s*"[^"]+"',
        f'__version__ = "{new_version}"',
        content,
    )

    with open(VERSION_FILE, "w") as f:
        f.write(content)

    return True


def create_git_tag(version: str) -> bool:
    """Create a git tag for the new version."""
    tag = f"v{version}"
    try:
        # Add the version file
        subprocess.check_call(["git", "add", VERSION_FILE])

        # Commit the version change
        subprocess.check_call(["git", "commit", "-m", f"Bump version to {version}"])

        # Create the tag
        subprocess.check_call(["git", "tag", "-a", tag, "-m", f"Version {version}"])

        print(f"Created git tag {tag}")
        print("To push the tag, run: git push origin main --tags")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error creating git tag: {e}")
        return False


def main() -> int:
    """Main function."""
    if len(sys.argv) != 2 or sys.argv[1] not in ["major", "minor", "patch"]:
        print("Usage: python tools/version.py [major|minor|patch]")
        return 1

    part = sys.argv[1]

    try:
        current_version = get_current_version()
        new_version = update_version(current_version, part)

        print(f"Current version: {current_version}")
        print(f"New version: {new_version}")
        print(
            "\nNOTE: Since pyproject.toml uses dynamic versioning, "
            "only _version.py needs updating.",
        )

        confirm = input("\nContinue? [y/N] ")
        if confirm.lower() != "y":
            print("Aborting")
            return 0

        if set_version(new_version):
            print(f"Updated version to {new_version} in {VERSION_FILE}")

        if create_git_tag(new_version):
            print("Version update completed successfully")

        return 0
    except Exception as e:
        print(f"Error updating version: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
