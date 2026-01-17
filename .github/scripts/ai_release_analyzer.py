#!/usr/bin/env python3
"""
AI-powered release analyzer that determines version bumps and generates release content
Now uses configuration files and prompt templates for better maintainability
"""

import os
import sys
import json
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import subprocess

try:
    import git
    import semver
    import yaml
    from ai_utils import AIClient
except ImportError as e:
    print(f"Error: Missing required package: {e}")
    print("Install with: pip install GitPython semver pyyaml")
    sys.exit(1)


class AIReleaseAnalyzer:
    def __init__(self):
        self.repo = git.Repo('.')
        self.github_token = os.environ.get('GITHUB_TOKEN')

        # Initialize AI client with configuration
        try:
            self.ai_client = AIClient()
            print(f"🤖 AI Client ready: {self.ai_client.active_provider}")
        except Exception as e:
            print(f"Warning: AI client initialization failed: {e}")
            self.ai_client = None

    def get_latest_tag(self) -> str:
        """Get the latest version tag"""
        try:
            tags = sorted(self.repo.tags, key=lambda t: t.commit.committed_datetime)
            for tag in reversed(tags):
                if re.match(r'^v?\d+\.\d+\.\d+$', tag.name):
                    return tag.name
        except:
            pass
        return 'v0.0.0'

    def get_commits_since_tag(self, tag: str) -> List[git.Commit]:
        """Get all commits since the last tag"""
        try:
            if tag == 'v0.0.0':
                # First release, get all commits
                return list(self.repo.iter_commits('HEAD'))
            return list(self.repo.iter_commits(f'{tag}..HEAD'))
        except:
            return []

    def get_changed_files(self, commits: List[git.Commit]) -> Dict[str, List[str]]:
        """Categorize changed files"""
        changes = {
            'tasks': [],
            'vars': [],
            'defaults': [],
            'meta': [],
            'tests': [],
            'docs': [],
            'ci': [],
            'other': []
        }

        for commit in commits:
            try:
                for item in commit.diff(commit.parents[0] if commit.parents else None):
                    path = item.a_path or item.b_path
                    if not path:
                        continue

                    if path.startswith('tasks/'):
                        changes['tasks'].append(path)
                    elif path.startswith('vars/') or path.startswith('defaults/'):
                        changes['vars'].append(path)
                    elif path.startswith('meta/'):
                        changes['meta'].append(path)
                    elif path.startswith('tests/') or path.startswith('molecule/'):
                        changes['tests'].append(path)
                    elif path.endswith('.md') or path.startswith('docs/'):
                        changes['docs'].append(path)
                    elif path.startswith('.github/'):
                        changes['ci'].append(path)
                    else:
                        changes['other'].append(path)
            except Exception:
                # Skip commits that can't be processed
                continue

        # Deduplicate
        for key in changes:
            changes[key] = list(set(changes[key]))

        return changes

    def analyze_with_ai(self, commits: List[git.Commit], changed_files: Dict[str, List[str]]) -> Dict:
        """Use AI to analyze commits and determine version bump"""

        if not self.ai_client or not self.ai_client.active_provider:
            print("🔄 AI not available, using rule-based analysis")
            return self.rule_based_analysis(commits, changed_files)

        # Prepare template variables
        commit_messages = [f"- {c.summary}" for c in commits[:50]]  # Limit to 50 most recent
        commit_text = "\n".join(commit_messages)

        # Prepare file changes summary
        changes_summary = []
        for category, files in changed_files.items():
            if files:
                changes_summary.append(f"{category}: {len(files)} files changed")

        template_variables = {
            'commit_text': commit_text,
            'changes_summary': "\n".join(changes_summary),
            'task_files': "\n".join(changed_files.get('tasks', [])[:10])
        }

        try:
            print("🔍 Analyzing with AI...")

            # Use the AI client with prompt template
            result = self.ai_client.call_ai('release_analysis', template_variables)

            if result['content']:
                analysis = json.loads(result['content'])

                # Log usage if debugging is enabled
                if self.ai_client.config.get('debug', {}).get('estimate_costs', True):
                    self.ai_client.log_debug_info()

                return analysis
            else:
                print("⚠️  AI analysis failed, falling back to rule-based")
                return self.rule_based_analysis(commits, changed_files)

        except Exception as e:
            print(f"⚠️  AI analysis error: {e}")
            return self.rule_based_analysis(commits, changed_files)

    def rule_based_analysis(self, commits: List[git.Commit], changed_files: Dict[str, List[str]]) -> Dict:
        """Fallback rule-based analysis"""
        print("🔧 Using rule-based analysis")

        version_bump = 'patch'
        breaking_changes = []
        new_features = []
        bug_fixes = []

        # Check commit messages for keywords
        for commit in commits:
            msg = commit.message.lower()

            if any(word in msg for word in ['breaking', 'remove', 'drop support', '!:']):
                version_bump = 'major'
                breaking_changes.append(commit.summary)
            elif any(word in msg for word in ['feat:', 'feature', 'add support', 'new']):
                if version_bump != 'major':
                    version_bump = 'minor'
                new_features.append(commit.summary)
            elif any(word in msg for word in ['fix:', 'bug', 'repair', 'correct']):
                bug_fixes.append(commit.summary)

        # Check file changes
        if changed_files.get('vars') or changed_files.get('defaults'):
            if version_bump == 'patch':
                version_bump = 'minor'  # Assume new vars are added with defaults

        should_release = len(commits) > 0

        # Build changelog entry
        changelog_parts = []
        if breaking_changes:
            changelog_parts.append("### Breaking Changes\n" + "\n".join(f"- {c}" for c in breaking_changes[:5]))
        if new_features:
            changelog_parts.append("### Added\n" + "\n".join(f"- {c}" for c in new_features[:5]))
        if bug_fixes:
            changelog_parts.append("### Fixed\n" + "\n".join(f"- {c}" for c in bug_fixes[:5]))

        changelog_entry = "\n\n".join(
            changelog_parts) if changelog_parts else "### Changed\n- Minor updates and improvements"

        return {
            "should_release": should_release,
            "version_bump": version_bump,
            "reasoning": f"Found {len(commits)} commits with {version_bump} level changes",
            "breaking_changes": breaking_changes[:5],
            "new_features": new_features[:5],
            "bug_fixes": bug_fixes[:5],
            "changelog_entry": changelog_entry
        }

    def generate_release_notes(self, analysis: Dict, version: str) -> str:
        """Generate comprehensive release notes using AI or fallback"""

        if self.ai_client and self.ai_client.active_provider:
            try:
                template_variables = {
                    'version': version,
                    'analysis_results': json.dumps(analysis, indent=2)
                }

                result = self.ai_client.call_ai('release_notes', template_variables)

                if result['content']:
                    return result['content']

            except Exception as e:
                print(f"Warning: AI release notes generation failed: {e}")

        # Fallback template
        notes = f"""## 🎉 Release {version}

### What's New

{analysis.get('changelog_entry', 'Various improvements and bug fixes')}

### Installation

```bash
ansible-galaxy install oatakan.debian_template_build,{version}
```

### Compatibility

- Ansible >= 2.9
- RHEL/CentOS/Rocky/Alma Linux 7, 8, 9, 10

**Full Changelog**: https://github.com/oatakan/ansible-role-debian_template_build/blob/main/CHANGELOG.md
"""
        return notes

    def run(self):
        """Main analysis flow"""
        print("🚀 Starting release analysis...")

        latest_tag = self.get_latest_tag()
        commits = self.get_commits_since_tag(latest_tag)

        if not commits and os.environ.get('FORCE_RELEASE', '').lower() != 'true':
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write("should_release=false\n")
            print("ℹ️  No commits since last release")
            return

        print(f"📊 Analyzing {len(commits)} commits since {latest_tag}")

        changed_files = self.get_changed_files(commits)
        analysis = self.analyze_with_ai(commits, changed_files)

        # Calculate new version
        current_version = latest_tag.lstrip('v')
        try:
            v = semver.Version.parse(current_version)
            if analysis['version_bump'] == 'major':
                new_version = str(v.bump_major())
            elif analysis['version_bump'] == 'minor':
                new_version = str(v.bump_minor())
            else:
                new_version = str(v.bump_patch())
        except:
            new_version = '0.1.0'

        new_version_tag = f'v{new_version}'

        print(f"📋 Analysis: {analysis['version_bump']} bump → {new_version_tag}")
        print(f"💭 Reasoning: {analysis['reasoning']}")

        release_notes = self.generate_release_notes(analysis, new_version_tag)

        # Output for GitHub Actions
        github_output = os.environ.get('GITHUB_OUTPUT')
        if not github_output:
            raise RuntimeError("GITHUB_OUTPUT environment variable is not set")

        with open(github_output, 'a') as f:
            f.write(f"should_release={str(analysis['should_release']).lower()}\n")
            f.write(f"version_bump={analysis['version_bump']}\n")
            f.write(f"new_version={new_version_tag}\n")
            f.write(f"analysis_reasoning={analysis['reasoning']}\n")
            f.write(f"changelog_entry<<EOF\n{analysis['changelog_entry']}\nEOF\n")
            f.write(f"release_notes<<EOF\n{release_notes}\nEOF\n")

        # Show usage summary if AI was used
        if self.ai_client and self.ai_client.usage_stats['requests'] > 0:
            usage = self.ai_client.get_usage_summary()
            print(f"💰 AI Usage: {usage['requests_made']} requests, "
                  f"{usage['total_tokens']} tokens, "
                  f"~${usage['estimated_cost_usd']}")


if __name__ == '__main__':
    analyzer = AIReleaseAnalyzer()
    analyzer.run()