import sys
import os
import re
import subprocess
from loguru import logger

def bump_version(new_version):
    """
    Systematically updates version across the codebase and creates a Git tag.
    Usage: python scripts/release.py 0.6.0
    """
    if not re.match(r"^\d+\.\d+\.\d+$", new_version):
        logger.error(f"Invalid version format: {new_version}. Use X.Y.Z (SemVer).")
        return

    # 1. Update pyproject.toml
    pyproject_path = "pyproject.toml"
    if os.path.exists(pyproject_path):
        with open(pyproject_path, 'r') as f:
            content = f.read()
        new_content = re.sub(r'version = "\d+\.\d+\.\d+"', f'version = "{new_version}"', content)
        with open(pyproject_path, 'w') as f:
            f.write(new_content)
        logger.info(f"Updated {pyproject_path} to {new_version}")

    # 2. Update README.md
    readme_path = "README.md"
    if os.path.exists(readme_path):
        with open(readme_path, 'r') as f:
            content = f.read()
        new_content = re.sub(r'\*\*Version:\*\* \d+\.\d+\.\d+', f'**Version:** {new_version}', content)
        with open(readme_path, 'w') as f:
            f.write(new_content)
        logger.info(f"Updated {readme_path} to {new_version}")

    # 3. Git Operations
    try:
        # Commit version bump
        subprocess.run(["git", "add", pyproject_path, readme_path], check=True)
        subprocess.run(["git", "commit", "-m", f"chore: bump version to {new_version}"], check=True)
        
        # Create tag
        tag_name = f"v{new_version}"
        subprocess.run(["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"], check=True)
        logger.success(f"Successfully bumped to {new_version} and created tag {tag_name}")
        
        logger.info(f"Run 'git push origin main --tags' to publish the release.")
    except Exception as e:
        logger.error(f"Git operation failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Missing version argument. Usage: python scripts/release.py X.Y.Z")
        sys.exit(1)
    
    bump_version(sys.argv[1])
