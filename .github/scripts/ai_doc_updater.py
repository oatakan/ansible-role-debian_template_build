#!/usr/bin/env python3
"""
AI-powered documentation updater
Now uses ai_utils.py for unified AI client management and prompt templates
"""

import os
import sys
import argparse
import re
from datetime import datetime
from typing import Dict, List
import subprocess

try:
    import yaml
    from ai_utils import AIClient
except ImportError as e:
    print(f"Error: Missing required package: {e}")
    sys.exit(1)


class AIDocUpdater:
    def __init__(self, version: str):
        self.version = version

        # Initialize AI client
        try:
            self.ai_client = AIClient()
            print(f"🤖 AI Client ready: {self.ai_client.active_provider}")
        except Exception as e:
            print(f"Warning: AI client initialization failed: {e}")
            self.ai_client = None

    def get_recent_changes(self) -> Dict:
        """Get recent changes from git"""
        try:
            # Get commits since last tag - handle case where no tags exist
            try:
                last_tag = subprocess.check_output(
                    ['git', 'describe', '--tags', '--abbrev=0'],
                    text=True,
                    stderr=subprocess.DEVNULL
                ).strip()
            except subprocess.CalledProcessError:
                # No tags exist yet
                last_tag = None

            if last_tag:
                commits = subprocess.check_output(
                    ['git', 'log', f'{last_tag}..HEAD', '--oneline'],
                    text=True
                ).strip().split('\n')

                # Get changed files
                changed_files = subprocess.check_output(
                    ['git', 'diff', '--name-only', f'{last_tag}..HEAD'],
                    text=True
                ).strip().split('\n')
            else:
                # Get all commits if no tags exist
                commits = subprocess.check_output(
                    ['git', 'log', '--oneline'],
                    text=True
                ).strip().split('\n')

                # Get all tracked files
                changed_files = subprocess.check_output(
                    ['git', 'ls-files'],
                    text=True
                ).strip().split('\n')

            # Filter out empty entries
            commits = [c for c in commits if c.strip()]
            changed_files = [f for f in changed_files if f.strip()]

            return {
                'commits': commits,
                'changed_files': changed_files,
                'last_tag': last_tag
            }
        except Exception as e:
            print(f"Warning: Could not get git changes: {e}")
            return {'commits': [], 'changed_files': [], 'last_tag': None}

    def analyze_variable_changes(self) -> Dict[str, List[str]]:
        """Analyze changes to variables"""
        changes = {'added': [], 'modified': [], 'removed': []}

        # Check defaults/main.yml
        defaults_file = 'defaults/main.yml'
        if os.path.exists(defaults_file):
            try:
                # Get current variables
                with open(defaults_file, 'r') as f:
                    current_vars = yaml.safe_load(f) or {}

                # Try to get previous version
                try:
                    last_tag = subprocess.check_output(
                        ['git', 'describe', '--tags', '--abbrev=0'],
                        text=True,
                        stderr=subprocess.DEVNULL
                    ).strip()

                    old_content = subprocess.check_output(
                        ['git', 'show', f'{last_tag}:{defaults_file}'],
                        text=True,
                        stderr=subprocess.DEVNULL
                    )
                    old_vars = yaml.safe_load(old_content) or {}

                    # Compare
                    for var in current_vars:
                        if var not in old_vars:
                            changes['added'].append(var)
                        elif current_vars[var] != old_vars[var]:
                            changes['modified'].append(var)

                    for var in old_vars:
                        if var not in current_vars:
                            changes['removed'].append(var)
                except subprocess.CalledProcessError:
                    # If can't get old version (no tags), all are new
                    changes['added'] = list(current_vars.keys())
                    print(f"📝 First release detected - marking {len(changes['added'])} variables as new")

            except Exception as e:
                print(f"Warning: Could not analyze variable changes: {e}")

        return changes

    def update_readme_with_ai(self, var_changes: Dict[str, List[str]]) -> bool:
        """Update README.md with AI assistance"""

        if not self.ai_client or not self.ai_client.active_provider:
            print("🔄 AI not available for documentation updates")
            return False

        if not any(var_changes.values()):
            print("ℹ️  No variable changes to document")
            return False

        readme_path = 'README.md'
        if not os.path.exists(readme_path):
            print("⚠️  README.md not found")
            return False

        with open(readme_path, 'r') as f:
            readme_content = f.read()

        # Load current variables
        defaults_file = 'defaults/main.yml'
        current_vars = {}
        if os.path.exists(defaults_file):
            try:
                with open(defaults_file, 'r') as f:
                    current_vars = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: Could not load variables: {e}")
                return False

        # Extract current variables section
        start_marker = '## Role Variables'
        end_marker = '## Dependencies'

        if start_marker in readme_content:
            start_idx = readme_content.find(start_marker)
            if end_marker in readme_content:
                end_idx = readme_content.find(end_marker)
                current_section = readme_content[start_idx:end_idx]
            else:
                # Look for next ## section
                remaining = readme_content[start_idx:]
                next_section = re.search(r'\n## ', remaining[3:])  # Skip the current ##
                if next_section:
                    current_section = remaining[:next_section.start() + 3]
                else:
                    current_section = remaining
        else:
            current_section = "No variables section found"

        # Prepare template variables
        new_var_list = []
        for var in var_changes['added']:
            value = current_vars.get(var, '...')
            new_var_list.append(f"{var}: {value}")

        template_variables = {
            'new_variables': "\n".join(new_var_list) if new_var_list else "None",
            'modified_variables': "\n".join(var_changes['modified']) if var_changes['modified'] else "None",
            'removed_variables': "\n".join(var_changes['removed']) if var_changes['removed'] else "None",
            'current_variables_section': current_section,
            'version': self.version
        }

        try:
            print("🔍 Updating documentation with AI...")

            result = self.ai_client.call_ai('documentation_update', template_variables)

            if result['content']:
                updated_section = result['content']

                # Replace the variables section
                if start_marker in readme_content:
                    start_idx = readme_content.find(start_marker)
                    if end_marker in readme_content:
                        end_idx = readme_content.find(end_marker)
                        new_readme = readme_content[:start_idx] + updated_section + '\n\n' + readme_content[end_idx:]
                    else:
                        # Replace until next ## section or end of file
                        remaining = readme_content[start_idx:]
                        next_section = re.search(r'\n## ', remaining[3:])
                        if next_section:
                            end_idx = start_idx + next_section.start() + 3
                            new_readme = readme_content[:start_idx] + updated_section + '\n\n' + readme_content[
                                                                                                 end_idx:]
                        else:
                            new_readme = readme_content[:start_idx] + updated_section

                    with open(readme_path, 'w') as f:
                        f.write(new_readme)

                    # Log usage if debugging is enabled
                    if self.ai_client.config.get('debug', {}).get('estimate_costs', True):
                        self.ai_client.log_debug_info()

                    return True
                else:
                    print("⚠️  Could not find Role Variables section to update")
                    return False
            else:
                print("⚠️  AI did not return updated content")
                return False

        except Exception as e:
            print(f"⚠️  AI documentation update failed: {e}")
            return False

    def add_version_badge(self):
        """Update version badge in README"""
        readme_path = 'README.md'
        if not os.path.exists(readme_path):
            print("⚠️  README.md not found for badge update")
            return

        try:
            with open(readme_path, 'r') as f:
                content = f.read()

            # Update or add version badge
            version_badge = f"[![Galaxy Version](https://img.shields.io/badge/galaxy-v{self.version}-blue.svg)](https://galaxy.ansible.com/oatakan/debian_template_build)"

            # Replace existing version badge
            if 'img.shields.io/badge/galaxy-v' in content:
                content = re.sub(
                    r'\[!\[Galaxy Version\]\(https://img\.shields\.io/badge/galaxy-v[\d.]+-blue\.svg\)\]\([^)]+\)',
                    version_badge,
                    content
                )
                print(f"✅ Updated existing version badge to v{self.version}")
            else:
                # Add after first line (title) if not found
                lines = content.split('\n')
                if len(lines) > 1:
                    lines.insert(2, '')
                    lines.insert(3, version_badge)
                    content = '\n'.join(lines)
                    print(f"✅ Added new version badge v{self.version}")

            with open(readme_path, 'w') as f:
                f.write(content)

        except Exception as e:
            print(f"Warning: Could not update version badge: {e}")

    def update_copyright_year(self):
        """Update copyright year if needed"""
        current_year = str(datetime.now().year)
        updated_files = []

        for file_path in ['LICENSE', 'README.md']:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()

                    # Only update if current year is not already present and Copyright exists
                    if current_year not in content and 'Copyright' in content:
                        # Update copyright year
                        updated_content = re.sub(
                            r'Copyright \(c\) \d{4}',
                            f'Copyright (c) {current_year}',
                            content
                        )

                        if updated_content != content:
                            with open(file_path, 'w') as f:
                                f.write(updated_content)
                            updated_files.append(file_path)

                except Exception as e:
                    print(f"Warning: Could not update copyright in {file_path}: {e}")

        if updated_files:
            print(f"✅ Updated copyright year to {current_year} in: {', '.join(updated_files)}")

    def run(self):
        """Main execution"""
        print(f"📚 Updating documentation for version {self.version}")

        # Get recent changes for context
        changes = self.get_recent_changes()
        print(f"ℹ️  Found {len(changes['commits'])} commits since {changes['last_tag'] or 'beginning'}")

        # Analyze variable changes
        var_changes = self.analyze_variable_changes()

        total_var_changes = sum(len(changes) for changes in var_changes.values())
        if total_var_changes > 0:
            print(f"📊 Variable changes: +{len(var_changes['added'])} added, "
                  f"~{len(var_changes['modified'])} modified, "
                  f"-{len(var_changes['removed'])} removed")

        # Update README with AI
        if total_var_changes > 0:
            print("🔍 Updating README with variable changes...")
            if self.update_readme_with_ai(var_changes):
                print("✅ Updated README.md variable section")
            else:
                print("⚠️  Could not update variables section automatically")
        else:
            print("ℹ️  No variable changes detected, skipping README update")

        # Always update version badge
        self.add_version_badge()

        # Update copyright year
        self.update_copyright_year()

        # Show usage summary if AI was used
        if self.ai_client and self.ai_client.usage_stats['requests'] > 0:
            usage = self.ai_client.get_usage_summary()
            print(f"💰 AI Usage: {usage['requests_made']} requests, "
                  f"{usage['total_tokens']} tokens, "
                  f"~${usage['estimated_cost_usd']}")

        print(f"📚 Documentation update complete for v{self.version}")


def main():
    parser = argparse.ArgumentParser(description='AI Documentation Updater')
    parser.add_argument('--version', required=True, help='Version number')
    args = parser.parse_args()

    updater = AIDocUpdater(args.version)
    updater.run()


if __name__ == '__main__':
    main()