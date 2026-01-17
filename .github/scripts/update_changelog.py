#!/usr/bin/env python3
"""
Update CHANGELOG.md with new version entry
"""

import argparse
import os
from datetime import datetime
import re


def update_changelog(version: str, entry: str):
    """Update CHANGELOG.md with new version entry"""

    changelog_path = 'CHANGELOG.md'

    # Read existing changelog
    if os.path.exists(changelog_path):
        with open(changelog_path, 'r') as f:
            content = f.read()
    else:
        # Create new changelog
        content = """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
"""

    # Prepare new entry
    date = datetime.now().strftime('%Y-%m-%d')
    new_entry = f"\n## [v{version}] - {date}\n\n{entry}\n"

    # Insert after [Unreleased] section
    pattern = r'(## \[Unreleased\].*?)(?=\n## \[|$)'
    match = re.search(pattern, content, re.DOTALL)

    if match:
        # Insert new version after Unreleased
        end_pos = match.end()
        updated_content = content[:end_pos] + new_entry + content[end_pos:]
    else:
        # Append to end
        updated_content = content + new_entry

    # Update comparison links at the bottom
    if '[Unreleased]:' in updated_content:
        # Update unreleased comparison
        updated_content = re.sub(
            r'\[Unreleased\]: (.+)/compare/(.+?)\.\.\.HEAD',
            f'[Unreleased]: \\1/compare/v{version}...HEAD',
            updated_content
        )

        # Add new version comparison
        repo_url = "https://github.com/oatakan/ansible-role-debian_template_build"
        prev_version_match = re.search(r'\[v([\d.]+)\]:', updated_content)
        if prev_version_match:
            prev_version = prev_version_match.group(1)
            new_link = f"[v{version}]: {repo_url}/compare/v{prev_version}...v{version}"
        else:
            new_link = f"[v{version}]: {repo_url}/releases/tag/v{version}"

        # Add link before the last line
        lines = updated_content.strip().split('\n')
        lines.append(new_link)
        updated_content = '\n'.join(lines) + '\n'

    # Write updated changelog
    with open(changelog_path, 'w') as f:
        f.write(updated_content)

    print(f"✅ Updated CHANGELOG.md with version {version}")


def main():
    parser = argparse.ArgumentParser(description='Update CHANGELOG.md')
    parser.add_argument('--version', required=True, help='Version number (without v prefix)')
    parser.add_argument('--entry', required=True, help='Changelog entry content')
    args = parser.parse_args()

    update_changelog(args.version, args.entry)


if __name__ == '__main__':
    main()