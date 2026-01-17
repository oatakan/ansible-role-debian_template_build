#!/usr/bin/env python3
"""
AI-powered PR analyzer that enriches pull requests with intelligent insights
Now uses ai_utils.py for unified AI client management and prompt templates
"""

import os
import sys
import argparse
import json
import re
from typing import Dict, List, Optional

try:
    from github import Github
    import git
    import yaml
    from ai_utils import AIClient
except ImportError as e:
    print(f"Error: Missing required package: {e}")
    sys.exit(1)


class AIPRAnalyzer:
    def __init__(self, pr_number: int):
        self.pr_number = pr_number
        self.github_token = os.environ.get('GITHUB_TOKEN')
        self.repo_name = os.environ.get('GITHUB_REPOSITORY')

        # Initialize GitHub client
        self.github = Github(self.github_token)
        self.repo = self.github.get_repo(self.repo_name)
        self.pr = self.repo.get_pull(pr_number)

        # Initialize AI client
        try:
            self.ai_client = AIClient()
            print(f"🤖 AI Client ready: {self.ai_client.active_provider}")
        except Exception as e:
            print(f"Warning: AI client initialization failed: {e}")
            self.ai_client = None

    def get_pr_diff(self) -> str:
        """Get the PR diff"""
        files = self.pr.get_files()
        diff_content = []

        for file in files:
            if file.patch:
                diff_content.append(f"File: {file.filename}")
                diff_content.append(file.patch[:2000])  # Limit size
                diff_content.append("---")

        return "\n".join(diff_content)

    def analyze_pr_with_ai(self, diff: str) -> Dict:
        """Use AI to analyze the PR"""

        if not self.ai_client or not self.ai_client.active_provider:
            print("🔄 AI not available, using basic analysis")
            return self.basic_analysis()

        # Prepare template variables
        template_variables = {
            'pr_title': self.pr.title,
            'pr_description': self.pr.body or 'No description provided',
            'changed_files': "\n".join([f.filename for f in self.pr.get_files()]),
            'diff_sample': diff[:3000]  # Limit diff size for token management
        }

        try:
            print("🔍 Analyzing PR with AI...")

            # Use the AI client with prompt template
            result = self.ai_client.call_ai('pr_analysis', template_variables)

            if result['content']:
                analysis = json.loads(result['content'])

                # Log usage if debugging is enabled
                if self.ai_client.config.get('debug', {}).get('estimate_costs', True):
                    self.ai_client.log_debug_info()

                return analysis
            else:
                print("⚠️  AI analysis failed, falling back to basic analysis")
                return self.basic_analysis()

        except Exception as e:
            print(f"⚠️  AI analysis error: {e}")
            return self.basic_analysis()

    def basic_analysis(self) -> Dict:
        """Fallback basic analysis without AI"""
        print("🔧 Using basic analysis")

        files = list(self.pr.get_files())

        # Determine change type
        change_type = 'enhancement'
        if 'fix' in self.pr.title.lower():
            change_type = 'bugfix'
        elif 'feat' in self.pr.title.lower() or 'add' in self.pr.title.lower():
            change_type = 'feature'
        elif 'break' in self.pr.title.lower() or '!' in self.pr.title:
            change_type = 'breaking'

        # Risk assessment based on files changed
        risk_level = 'low'
        critical_files = ['tasks/main.yml', 'defaults/main.yml', 'meta/main.yml']

        if any(f.filename in critical_files for f in files):
            risk_level = 'medium'
        if any(f.filename.startswith('defaults/') for f in files):
            risk_level = 'high'
        if len(files) > 10:
            risk_level = 'high'

        return {
            'summary': f"PR modifies {len(files)} files with {change_type} changes",
            'change_type': change_type,
            'risk_level': risk_level,
            'testing_recommendations': [
                'Run molecule tests with multiple OS versions',
                'Test idempotency (run role twice)',
                'Verify on target platforms',
                'Check for syntax errors with ansible-lint'
            ],
            'code_quality_notes': [
                'Manual review recommended for critical files',
                'Verify YAML syntax and formatting',
                'Check for Ansible best practices'
            ],
            'compatibility_notes': [],
            'documentation_needs': [
                'Update README if new variables added',
                'Document any breaking changes',
                'Update examples if behavior changed'
            ],
            'suggested_reviewers': ['ansible-experts', 'platform-team'],
            'estimated_review_time': '15-30'
        }

    def generate_pr_comment(self, analysis: Dict) -> str:
        """Generate a comprehensive PR comment"""

        # Risk emoji
        risk_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}.get(analysis['risk_level'], '⚪')

        comment = f"""## 🤖 AI Pull Request Analysis

### Summary
{analysis['summary']}

### Metadata
- **Change Type:** {analysis['change_type'].title()}
- **Risk Level:** {risk_emoji} {analysis['risk_level'].title()}
- **Estimated Review Time:** {analysis['estimated_review_time']} minutes

### Testing Recommendations
{chr(10).join(f'- {rec}' for rec in analysis['testing_recommendations'])}

### Code Quality Notes
{chr(10).join(f'- {note}' for note in analysis['code_quality_notes']) if analysis['code_quality_notes'] else '✅ No issues identified'}

### Compatibility Considerations
{chr(10).join(f'- {note}' for note in analysis['compatibility_notes']) if analysis['compatibility_notes'] else '✅ No compatibility concerns identified'}

### Documentation Needs
{chr(10).join(f'- {need}' for need in analysis['documentation_needs']) if analysis['documentation_needs'] else '✅ Documentation appears complete'}

---

<details>
<summary>💡 AI Assistant Commands</summary>

You can interact with the AI assistant using these commands in comments:

- `/ai review` - Request a detailed code review
- `/ai test` - Generate test scenarios
- `/ai docs` - Generate documentation updates
- `/ai changelog` - Generate changelog entry
- `/ai improve` - Suggest improvements

</details>

<sub>This analysis was performed by AI ({self.ai_client.active_provider if self.ai_client else 'basic'}) and should be verified by human reviewers.</sub>"""

        return comment

    def update_pr_description(self, analysis: Dict):
        """Enhance PR description with structured data"""

        current_body = self.pr.body or ""

        # Don't update if already has our metadata
        if "<!-- ai-metadata" in current_body:
            return

        metadata = f"""
<!-- ai-metadata
change_type: {analysis['change_type']}
risk_level: {analysis['risk_level']}
auto_generated: true
-->

## AI-Enhanced Description

{analysis['summary']}

### Changes Made
{current_body}

### Testing Checklist
{chr(10).join(f'- [ ] {rec}' for rec in analysis['testing_recommendations'])}

### Review Checklist
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] Changelog entry added (if needed)
- [ ] Breaking changes documented (if any)
- [ ] Security implications reviewed
"""

        try:
            self.pr.edit(body=metadata)
            print("✅ Updated PR description")
        except Exception as e:
            print(f"Warning: Could not update PR description: {e}")

    def add_labels(self, analysis: Dict):
        """Add appropriate labels based on analysis"""

        labels_to_add = []

        # Change type labels
        change_type_map = {
            'bugfix': 'bug',
            'feature': 'enhancement',
            'breaking': 'breaking-change',
            'chore': 'maintenance'
        }

        if analysis['change_type'] in change_type_map:
            labels_to_add.append(change_type_map[analysis['change_type']])

        # Risk labels
        if analysis['risk_level'] == 'high':
            labels_to_add.append('needs-careful-review')
        elif analysis['risk_level'] == 'medium':
            labels_to_add.append('review-required')

        # Documentation labels
        if analysis['documentation_needs']:
            labels_to_add.append('documentation')

        # Add labels if they exist in the repo
        try:
            repo_labels = {label.name for label in self.repo.get_labels()}
            added_labels = []

            for label in labels_to_add:
                if label in repo_labels:
                    self.pr.add_to_labels(label)
                    added_labels.append(label)

            if added_labels:
                print(f"✅ Added labels: {', '.join(added_labels)}")

        except Exception as e:
            print(f"Warning: Could not add labels: {e}")

    def run(self):
        """Main execution flow"""
        print(f"🔍 Analyzing PR #{self.pr_number}: {self.pr.title}")

        # Get PR diff
        diff = self.get_pr_diff()

        # Analyze with AI
        analysis = self.analyze_pr_with_ai(diff)

        print(f"📊 Analysis complete:")
        print(f"  - Change Type: {analysis['change_type']}")
        print(f"  - Risk Level: {analysis['risk_level']}")
        print(f"  - Tests Needed: {len(analysis['testing_recommendations'])}")

        # Generate and post comment
        comment = self.generate_pr_comment(analysis)
        try:
            self.pr.create_issue_comment(comment)
            print("✅ Posted analysis comment")
        except Exception as e:
            print(f"Warning: Could not post comment: {e}")

        # Update PR description
        self.update_pr_description(analysis)

        # Add labels
        self.add_labels(analysis)

        # Show usage summary if AI was used
        if self.ai_client and self.ai_client.usage_stats['requests'] > 0:
            usage = self.ai_client.get_usage_summary()
            print(f"💰 AI Usage: {usage['requests_made']} requests, "
                  f"{usage['total_tokens']} tokens, "
                  f"~${usage['estimated_cost_usd']}")

        print(f"✅ Successfully enriched PR #{self.pr_number}")


def main():
    parser = argparse.ArgumentParser(description='AI PR Analyzer')
    parser.add_argument('--pr-number', type=int, required=True, help='PR number to analyze')
    args = parser.parse_args()

    analyzer = AIPRAnalyzer(args.pr_number)
    analyzer.run()


if __name__ == '__main__':
    main()