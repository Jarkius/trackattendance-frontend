# Claude Integration Guide

This guide explains how to integrate Claude AI capabilities with your GitHub repository for enhanced development workflows.

## Table of Contents

1. [What is Claude Integration?](#what-is-claude-integration)
2. [Integration Methods](#integration-methods)
3. [Setting Up Claude for Your Repository](#setting-up-claude-for-your-repository)
4. [GitHub Actions Integration](#github-actions-integration)
5. [Best Practices](#best-practices)
6. [This Repository's Setup](#this-repositorys-setup)

---

## What is Claude Integration?

Claude AI can assist with your development workflow in several ways:

- **Code assistance**: Get help writing, reviewing, and refactoring code
- **Documentation**: Generate and maintain documentation
- **Testing**: Create and improve test coverage
- **Code reviews**: Automated code review suggestions
- **Issue management**: Help triage and respond to issues

## Integration Methods

### 1. Claude Code (claude.ai/code)

The most direct way to use Claude with your repository.

**Access**: Visit [claude.ai/code](https://claude.ai/code)

**Capabilities**:
- Direct repository access via GitHub integration
- Full codebase context and understanding
- Can read, edit, and create files
- Execute commands and run tests
- Create commits and pull requests

**How it works**:
1. Connect your GitHub account at claude.ai/code
2. Grant repository access permissions
3. Start a conversation with Claude about your code
4. Claude can make changes directly to your repository

### 2. Claude via GitHub Actions

Integrate Claude into your CI/CD pipeline for automated tasks.

**Use cases**:
- Automated code reviews on pull requests
- Documentation generation
- Test generation
- Security scanning analysis

### 3. Claude API Integration

Use Claude's API for custom integrations.

**Use cases**:
- Custom bots and automations
- IDE plugins
- Command-line tools
- Custom workflows

---

## Setting Up Claude for Your Repository

### Step 1: Create Repository Guidelines Files

Create these files to help Claude understand your project:

#### `CLAUDE.md` (Repository-specific guidance)

```markdown
# Project Overview
Brief description of your project, tech stack, and architecture.

## Commands
List common commands for setup, testing, building, etc.

## Architecture
High-level architecture overview and key patterns.

## Coding Style
Your team's coding conventions and standards.

## Testing
How to run tests and what's expected.
```

**Example** (this repository):
```markdown
# CLAUDE.md

## Project
TrackAttendance Frontend — offline-first desktop kiosk app

**Stack**: Python 3.11+, PyQt6 + QWebEngineView, SQLite

## Commands
python main.py          # Run application
python -m venv .venv    # Setup virtual environment
pip install -r requirements.txt
```

#### `AGENTS.md` (Development guidelines)

```markdown
# Repository Guidelines

## Project Structure
Directory layout and file organization.

## Build, Test, and Development Commands
All the commands developers need.

## Coding Style
Language-specific style guides.

## Key Patterns
Important architectural patterns and conventions.

## Commit & PR Guidelines
How to format commits and create pull requests.
```

### Step 2: Configure Claude Permissions (Optional)

Create `.claude/settings.local.json` to configure Claude's permissions:

```json
{
  "permissions": {
    "allow": [
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git push:*)",
      "Bash(python:*)",
      "Bash(npm:*)"
    ]
  }
}
```

**Common permissions**:
- `Bash(git *)` - Git operations
- `Bash(python *)` - Python commands
- `Bash(npm *)` - Node.js/npm commands
- `Bash(pip *)` - Python package management
- `WebFetch(domain:github.com)` - GitHub API access

### Step 3: Create `.env.example` for Sensitive Configuration

Never commit API keys. Instead, document required environment variables:

```ini
# .env.example
CLAUDE_API_KEY=your-api-key-here
# Add other required variables
```

Add `.env` to `.gitignore`:
```
.env
.env.local
```

---

## GitHub Actions Integration

### Method 1: Anthropic GitHub Actions

Use official Anthropic actions for automated tasks.

**Example**: Code review on pull requests

Create `.github/workflows/claude-review.yml`:

```yaml
name: Claude Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Claude Code Review
        uses: anthropics/claude-code-review@v1
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Method 2: Custom API Integration

Create custom workflows using Claude's API.

**Example**: Documentation generation

```yaml
name: Generate Docs

on:
  push:
    branches: [main]
    paths:
      - 'src/**'

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Generate documentation
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          # Call Claude API to generate docs
          python scripts/generate_docs.py
      
      - name: Commit documentation
        run: |
          git config user.name "Claude Bot"
          git config user.email "bot@example.com"
          git add docs/
          git commit -m "docs: auto-generated documentation"
          git push
```

### Method 3: Issue Triage Bot

Automatically analyze and label new issues.

```yaml
name: Issue Triage

on:
  issues:
    types: [opened]

jobs:
  triage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Analyze issue
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # Use Claude to analyze issue and suggest labels
          python scripts/triage_issue.py ${{ github.event.issue.number }}
```

---

## Best Practices

### 1. Documentation First

- **Always** maintain `CLAUDE.md` and `AGENTS.md`
- Keep documentation up-to-date with code changes
- Include examples and common commands
- Document your architecture and patterns

### 2. Security

- **Never** commit API keys or secrets
- Use GitHub Secrets for sensitive data
- Review Claude's permissions in `.claude/settings.local.json`
- Limit permissions to what's necessary

### 3. Context Management

- Keep focused, single-purpose documentation files
- Use clear, descriptive file and directory names
- Document key decisions and patterns
- Include links to external resources

### 4. Testing

- Ensure Claude can run your tests
- Document test commands clearly
- Include test data setup instructions
- Automate validation where possible

### 5. Version Control

- Commit Claude-generated code in logical chunks
- Write clear commit messages
- Review all generated code before committing
- Use pull requests for major changes

---

## This Repository's Setup

This repository (`Jarkius/trackattendance-frontend`) is already configured for Claude integration:

### Files Present

1. **`CLAUDE.md`** - Project overview, commands, architecture, patterns
   - Located: Repository root
   - Purpose: Quick reference for Claude about the project

2. **`AGENTS.md`** - Repository guidelines and development practices
   - Located: Repository root
   - Purpose: Detailed development guidelines

3. **`.claude/settings.local.json`** - Permission configuration
   - Located: `.claude/` directory
   - Purpose: Control what operations Claude can perform
   - **Permissions granted**:
     - Git operations (add, commit, push)
     - GitHub CLI (issue management)
     - Python execution
     - File system operations
     - Limited web access (GitHub API)

### How to Use Claude with This Repository

#### Option 1: Claude Code (Recommended)

1. Visit [claude.ai/code](https://claude.ai/code)
2. Connect your GitHub account
3. Select `Jarkius/trackattendance-frontend` repository
4. Start asking questions or requesting changes

**Example conversations**:
- "Add a new feature to export data in CSV format"
- "Fix the bug in the sync service"
- "Write tests for the attendance module"
- "Review the code in main.py for improvements"

#### Option 2: GitHub Actions (Future)

To add automated Claude workflows:

1. Create `.github/workflows/` directory
2. Add workflow YAML files (see examples above)
3. Add `ANTHROPIC_API_KEY` to repository secrets:
   - Go to Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `ANTHROPIC_API_KEY`
   - Value: Your Anthropic API key

#### Option 3: Local Development

Use Claude API locally for custom tools:

```python
# Example: Local Claude integration
import anthropic
import os

client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)

# Ask Claude about your code
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": "Review this Python function for bugs..."
    }]
)

print(message.content)
```

### Current Workflow

The repository already uses Claude Code for:
- Feature development
- Bug fixes
- Code reviews
- Documentation updates
- Test creation

**Evidence**: Check commit history for messages like:
- "🤖 Generated with Claude Code"
- "Co-Authored-By: Claude Sonnet 4.5"

---

## Getting Started Checklist

- [ ] Read `CLAUDE.md` to understand project structure
- [ ] Review `AGENTS.md` for coding guidelines
- [ ] Check `.claude/settings.local.json` for permissions
- [ ] Set up environment variables (`.env` file)
- [ ] Run tests to ensure everything works
- [ ] Try Claude Code at claude.ai/code
- [ ] (Optional) Set up GitHub Actions workflows
- [ ] (Optional) Integrate Claude API for custom tools

---

## Resources

- **Claude Code**: [claude.ai/code](https://claude.ai/code)
- **Anthropic API Docs**: [docs.anthropic.com](https://docs.anthropic.com)
- **GitHub Actions Docs**: [docs.github.com/actions](https://docs.github.com/en/actions)
- **This Repository**:
  - [CLAUDE.md](../CLAUDE.md) - Project guidance
  - [AGENTS.md](../AGENTS.md) - Development guidelines
  - [README.md](../README.md) - General documentation

---

## Support

For questions about:
- **Claude integration**: Check [Anthropic documentation](https://docs.anthropic.com)
- **This repository**: Open an issue on GitHub
- **GitHub Actions**: Check [GitHub Actions documentation](https://docs.github.com/en/actions)

---

**Last Updated**: 2026-02-03  
**Maintainer**: Repository team  
**Claude Version**: Claude 3.5 Sonnet
