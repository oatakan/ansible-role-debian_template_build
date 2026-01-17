#!/usr/bin/env python3
"""
AI PR Assistant - responds to commands in PR comments
Now uses ai_utils.py for unified AI client management and prompt templates
"""

import os
import sys
import argparse
import re
import json
from typing import Optional, Dict

try:
    from github import Github
    from ai_utils import AIClient
except ImportError as e:
    print(f"Error: Missing required package: {e}")
    sys.exit(1)


class AIPRAssistant:
    def __init__(self, pr_number: int, comment: str):
        self.pr_number = pr_number
        self.comment = comment
        self.github_token = os.environ.get('GITHUB_TOKEN')
        self.repo_name = os.environ.get('GITHUB_REPOSITORY')

        # Initialize clients
        self.github = Github(self.github_token)
        self.repo = self.github.get_repo(self.repo_name)
        self.pr = self.repo.get_pull(pr_number)

        # Initialize AI client
        try:
            self.ai_client = AIClient()
            print(f"🤖 AI Assistant ready: {self.ai_client.active_provider}")
        except Exception as e:
            print(f"Warning: AI client initialization failed: {e}")
            self.ai_client = None

    def parse_command(self) -> Optional[str]:
        """Extract command from comment"""
        match = re.search(r'/ai\s+(\w+)', self.comment)
        return match.group(1) if match else None

    def get_pr_context(self) -> Dict[str, str]:
        """Get PR context for AI analysis"""
        files = list(self.pr.get_files())

        # Categorize files
        file_categories = {
            'tasks': [],
            'vars': [],
            'tests': [],
            'docs': [],
            'ci': []
        }

        for file in files:
            if file.filename.startswith('tasks/'):
                file_categories['tasks'].append(file.filename)
            elif file.filename.startswith(('vars/', 'defaults/')):
                file_categories['vars'].append(file.filename)
            elif file.filename.startswith(('tests/', 'molecule/')):
                file_categories['tests'].append(file.filename)
            elif file.filename.endswith('.md') or file.filename.startswith('docs/'):
                file_categories['docs'].append(file.filename)
            elif file.filename.startswith('.github/'):
                file_categories['ci'].append(file.filename)

        return {
            'pr_title': self.pr.title,
            'pr_description': self.pr.body or 'No description provided',
            'files_changed': len(files),
            'additions': self.pr.additions,
            'deletions': self.pr.deletions,
            'changed_files': "\n".join(f"- {f.filename}" for f in files[:20]),
            'file_categories': json.dumps(file_categories, indent=2),
            'pr_context': f"""
PR #{self.pr_number}: {self.pr.title}
Files changed: {len(files)}
Changes: +{self.pr.additions} -{self.pr.deletions}

Modified files:
{chr(10).join(f"- {f.filename}" for f in files[:20])}
""".strip()
        }

    def handle_review_command(self):
        """Detailed code review"""
        print("🔍 Generating detailed code review...")

        if not self.ai_client or not self.ai_client.active_provider:
            self._post_fallback_message("review")
            return

        # Get detailed diff for up to 5 files
        files = list(self.pr.get_files())
        detailed_review = []

        for file in files[:5]:  # Limit to 5 files to manage token usage
            if file.patch:
                review = self.review_file_with_ai(file)
                if review:
                    detailed_review.append(review)

        if detailed_review:
            comment = f"""## 🔍 Detailed Code Review

{chr(10).join(detailed_review)}

### Overall Assessment
Based on the changes, this PR has been analyzed for best practices, security, and maintainability.

### Next Steps
- Address any high-priority issues mentioned above
- Run the suggested tests
- Update documentation if needed

---
<sub>AI-powered review using {self.ai_client.active_provider} • Use `/ai help` for more commands</sub>"""
        else:
            comment = """## 🔍 Code Review

No significant issues detected in the code review. The changes appear to follow good practices.

### Recommendations
- Ensure all tests pass
- Verify documentation is up to date
- Test on multiple platforms if applicable

---
<sub>AI-powered review • Use `/ai help` for more commands</sub>"""

        self.pr.create_issue_comment(comment)
        print("✅ Posted detailed code review")

    def review_file_with_ai(self, file) -> Optional[str]:
        """Review individual file with AI"""
        if not self.ai_client or not self.ai_client.active_provider:
            return None

        template_variables = {
            'filename': file.filename,
            'file_status': file.status,
            'additions': str(file.additions),
            'deletions': str(file.deletions),
            'file_diff': file.patch[:1500] if file.patch else 'No diff available'
        }

        try:
            result = self.ai_client.call_ai('code_review', template_variables)

            if result['content']:
                return f"### 📄 {file.filename}\n{result['content']}\n"
            else:
                return f"### 📄 {file.filename}\nFile reviewed - no specific issues identified.\n"

        except Exception as e:
            print(f"Warning: AI review failed for {file.filename}: {e}")
            return f"### 📄 {file.filename}\nCould not complete AI review for this file.\n"

    def handle_test_command(self):
        """Generate test scenarios"""
        print("🧪 Generating test scenarios...")

        context = self.get_pr_context()

        if self.ai_client and self.ai_client.active_provider:
            try:
                result = self.ai_client.call_ai('test_scenarios', context)

                if result['content']:
                    comment = f"""## 🧪 AI-Generated Test Scenarios

{result['content']}

---
<sub>Test scenarios generated by {self.ai_client.active_provider} • Use `/ai help` for more commands</sub>"""
                else:
                    comment = self._generate_fallback_tests(context)
            except Exception as e:
                print(f"Warning: AI test generation failed: {e}")
                comment = self._generate_fallback_tests(context)
        else:
            comment = self._generate_fallback_tests(context)

        self.pr.create_issue_comment(comment)
        print("✅ Posted test scenarios")

    def _generate_fallback_tests(self, context: Dict[str, str]) -> str:
        """Generate basic test scenarios without AI"""
        return f"""## 🧪 Suggested Test Scenarios

Based on the changes in this PR, here are recommended test scenarios:

### Unit Tests
1. **Basic functionality test**
   ```bash
   molecule test
   ```

2. **Multi-platform test**
   ```bash
   for distro in rockylinux:8 rockylinux:9 almalinux:9; do
     MOLECULE_DISTRO=$distro molecule test
   done
   ```

### Integration Tests
1. **Clean system test** - Test on a fresh VM
2. **Upgrade test** - Test upgrading from previous version  
3. **Idempotency test** - Run role multiple times

### Manual Testing Checklist
- [ ] Test with minimal config
- [ ] Test with all features enabled
- [ ] Test error handling
- [ ] Verify documentation matches behavior

### Platform-specific Tests
- [ ] RHEL 8
- [ ] RHEL 9  
- [ ] Rocky Linux 9
- [ ] Container environments

---
<sub>Basic test plan • Use `/ai help` for more commands</sub>"""

    def handle_changelog_command(self):
        """Generate changelog entry"""
        print("📝 Generating changelog entry...")

        context = self.get_pr_context()

        if self.ai_client and self.ai_client.active_provider:
            try:
                result = self.ai_client.call_ai('changelog_generation', context)

                if result['content']:
                    comment = f"""## 📝 Suggested Changelog Entry

{result['content']}

### How to Add This to CHANGELOG.md
1. Copy the appropriate section above
2. Add it under the `[Unreleased]` section in CHANGELOG.md
3. Include PR reference: `(#{self.pr_number})`

---
<sub>Changelog generated by {self.ai_client.active_provider} • Use `/ai help` for more commands</sub>"""
                else:
                    comment = self._generate_fallback_changelog()
            except Exception as e:
                print(f"Warning: AI changelog generation failed: {e}")
                comment = self._generate_fallback_changelog()
        else:
            comment = self._generate_fallback_changelog()

        self.pr.create_issue_comment(comment)
        print("✅ Posted changelog entry")

    def _generate_fallback_changelog(self) -> str:
        """Generate basic changelog entry without AI"""
        # Simple categorization based on PR title
        if 'fix' in self.pr.title.lower():
            category = 'Fixed'
            entry = f"- {self.pr.title}"
        elif any(word in self.pr.title.lower() for word in ['feat', 'add', 'new']):
            category = 'Added'
            entry = f"- {self.pr.title}"
        else:
            category = 'Changed'
            entry = f"- {self.pr.title}"

        return f"""## 📝 Suggested Changelog Entry

```markdown
### {category}
{entry}
```

To add this to CHANGELOG.md:
1. Copy the entry above
2. Add it under the `[Unreleased]` section
3. Include PR reference: `(#{self.pr_number})`

---
<sub>Basic changelog suggestion • Use `/ai help` for more commands</sub>"""

    def handle_docs_command(self):
        """Generate documentation updates"""
        print("📚 Analyzing documentation needs...")

        context = self.get_pr_context()
        files = list(self.pr.get_files())

        # Analyze what might need documentation
        variable_changes = []
        new_features = []
        breaking_changes = []

        for file in files:
            if file.filename.startswith('defaults/'):
                variable_changes.append(f"Changes in {file.filename}")
            elif file.filename.startswith('tasks/') and file.status == 'added':
                new_features.append(f"New task file: {file.filename}")

        context.update({
            'variable_changes': "\n".join(variable_changes) if variable_changes else "No variable changes detected",
            'new_features': "\n".join(new_features) if new_features else "No new features detected",
            'breaking_changes': "None detected"  # Could be enhanced with AI analysis
        })

        if self.ai_client and self.ai_client.active_provider:
            try:
                result = self.ai_client.call_ai('documentation_analysis', context)

                if result['content']:
                    comment = f"""## 📚 Documentation Analysis

{result['content']}

---
<sub>Documentation analysis by {self.ai_client.active_provider} • Use `/ai help` for more commands</sub>"""
                else:
                    comment = self._generate_fallback_docs(files)
            except Exception as e:
                print(f"Warning: AI documentation analysis failed: {e}")
                comment = self._generate_fallback_docs(files)
        else:
            comment = self._generate_fallback_docs(files)

        self.pr.create_issue_comment(comment)
        print("✅ Posted documentation analysis")

    def _generate_fallback_docs(self, files) -> str:
        """Generate basic documentation analysis without AI"""
        needs_docs = []

        for file in files:
            if file.filename.startswith('defaults/'):
                needs_docs.append(f"- Update README Role Variables for `{file.filename}`")
            elif file.filename.startswith('tasks/') and file.status == 'added':
                needs_docs.append(f"- Document new functionality in `{file.filename}`")

        return f"""## 📚 Documentation Updates Needed

Based on the changes, consider updating:

### README.md
{chr(10).join(needs_docs) if needs_docs else '- No obvious documentation updates needed'}

### Documentation Checklist
- [ ] Role Variables section (if variables changed)
- [ ] Requirements section (if dependencies changed)
- [ ] Example Playbook (if usage changed)
- [ ] Compatibility matrix (if platform support changed)

---
<sub>Basic documentation analysis • Use `/ai help` for more commands</sub>"""

    def handle_improve_command(self):
        """Suggest improvements"""
        print("💡 Generating improvement suggestions...")

        context = self.get_pr_context()
        context[
            'change_summary'] = f"PR changes {context['files_changed']} files with +{context['additions']}/-{context['deletions']} lines"

        if self.ai_client and self.ai_client.active_provider:
            try:
                result = self.ai_client.call_ai('improvement_suggestions', context)

                if result['content']:
                    comment = f"""## 💡 AI-Generated Improvement Suggestions

{result['content']}

---
<sub>Suggestions generated by {self.ai_client.active_provider} • Use `/ai help` for more commands</sub>"""
                else:
                    comment = self._generate_fallback_improvements()
            except Exception as e:
                print(f"Warning: AI improvement generation failed: {e}")
                comment = self._generate_fallback_improvements()
        else:
            comment = self._generate_fallback_improvements()

        self.pr.create_issue_comment(comment)
        print("✅ Posted improvement suggestions")

    def _generate_fallback_improvements(self) -> str:
        """Generate basic improvements without AI"""
        return f"""## 💡 Improvement Suggestions

Based on this PR, here are some general suggestions:

### Code Quality
- Consider adding molecule scenarios for new features
- Add ansible-lint exceptions with explanations if needed
- Consider extracting repeated tasks into separate files

### Testing
- Add specific test cases for the changes
- Consider adding integration tests with real VMs
- Document manual testing procedures

### Performance
- Consider using `block` for related tasks
- Review task conditions for efficiency
- Consider caching expensive operations

### Maintenance
- Update copyright year if needed
- Review and update dependencies
- Consider deprecation notices for changed behavior

---
<sub>General improvement suggestions • Use `/ai help` for more commands</sub>"""

    def handle_help_command(self):
        """Show available commands"""
        ai_provider = f" (using {self.ai_client.active_provider})" if self.ai_client and self.ai_client.active_provider else ""

        comment = f"""## 🤖 AI Assistant Commands{ai_provider}

I can help with various PR tasks. Use these commands:

### Available Commands
- `/ai review` - Get detailed code review with specific feedback
- `/ai test` - Generate comprehensive test scenarios
- `/ai changelog` - Create changelog entry for this PR
- `/ai docs` - Identify documentation updates needed
- `/ai improve` - Suggest code improvements
- `/ai help` - Show this help message

### Examples
```
/ai review
/ai test
/ai changelog
```

### Tips
- Commands are case-insensitive
- One command per comment
- AI analysis may take a few moments
- All suggestions should be verified by human reviewers

### Current Configuration
- **AI Provider**: {self.ai_client.active_provider if self.ai_client and self.ai_client.active_provider else 'Not available (using fallback)'}
- **Fallback Mode**: {'Disabled' if self.ai_client and self.ai_client.active_provider else 'Active'}

---
<sub>I'm here to help make your PR better! 🚀</sub>"""

        self.pr.create_issue_comment(comment)

    def handle_unknown_command(self, command: str):
        """Handle unknown commands"""
        comment = f"""❓ Unknown command: `/ai {command}`

Did you mean one of these?
- `/ai review` - Code review
- `/ai test` - Test scenarios
- `/ai docs` - Documentation analysis
- `/ai improve` - Improvement suggestions
- `/ai changelog` - Changelog entry
- `/ai help` - Show all commands

---
<sub>Use `/ai help` to see all available commands</sub>"""

        self.pr.create_issue_comment(comment)

    def _post_fallback_message(self, command: str):
        """Post a message when AI is not available"""
        comment = f"""## 🤖 AI Assistant - Fallback Mode

AI provider is not available, but I can still help with basic {command} assistance.

### To Enable Full AI Features:
1. Add `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` to GitHub Secrets
2. Ensure the API keys have sufficient credits
3. Re-run the command

### Available Without AI:
- Basic code analysis
- Standard test recommendations  
- Template-based suggestions

Use `/ai help` to see all available commands.

---
<sub>Running in fallback mode • Configure AI provider for enhanced features</sub>"""

        self.pr.create_issue_comment(comment)

    def run(self):
        """Process the command"""
        command = self.parse_command()

        if not command:
            return

        print(f"🤖 Processing command: /ai {command}")

        # React to show we're processing
        try:
            self.pr.create_issue_comment("🤖 Processing AI command...")
        except Exception as e:
            print(f"Warning: Could not post processing message: {e}")

        # Handle commands
        handlers = {
            'review': self.handle_review_command,
            'test': self.handle_test_command,
            'changelog': self.handle_changelog_command,
            'docs': self.handle_docs_command,
            'improve': self.handle_improve_command,
            'help': self.handle_help_command,
        }

        handler = handlers.get(command.lower())
        if handler:
            try:
                handler()

                # Show usage summary if AI was used
                if self.ai_client and self.ai_client.usage_stats['requests'] > 0:
                    usage = self.ai_client.get_usage_summary()
                    print(f"💰 AI Usage: {usage['requests_made']} requests, "
                          f"{usage['total_tokens']} tokens, "
                          f"~${usage['estimated_cost_usd']}")

            except Exception as e:
                print(f"Error handling command {command}: {e}")
                error_comment = f"""❌ Error processing command `/ai {command}`

An error occurred while processing your request. Please try again or use `/ai help` for available commands.

Error details: {str(e)[:200]}...

---
<sub>AI Assistant error • Use `/ai help` for more commands</sub>"""

                try:
                    self.pr.create_issue_comment(error_comment)
                except:
                    pass
        else:
            self.handle_unknown_command(command)


def main():
    parser = argparse.ArgumentParser(description='AI PR Assistant')
    parser.add_argument('--pr-number', type=int, required=True)
    parser.add_argument('--comment', type=str, required=True)
    args = parser.parse_args()

    assistant = AIPRAssistant(args.pr_number, args.comment)
    assistant.run()


if __name__ == '__main__':
    main()