# Claude Code Action Setup

This repository uses the [Claude Code Action](https://github.com/anthropics/claude-code-action) to enable AI-powered code assistance on pull requests and issues.

## What It Does

The Claude Code Action allows you to:
- Get AI-powered code reviews on pull requests
- Request code changes via PR comments
- Have Claude make commits directly to PR branches
- Get help with debugging and implementation

## Setup Requirements

### 1. Add Anthropic API Key

The workflow requires an `ANTHROPIC_API_KEY` secret to be configured in your repository:

1. Go to your repository's **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `ANTHROPIC_API_KEY`
4. Value: Your Anthropic API key (get one at https://console.anthropic.com/)
5. Click **Add secret**

### 2. Workflow Triggers

The action automatically runs on:
- **Pull Request events**: opened, synchronize, reopened
- **Issue comments**: created, edited

### 3. Required Permissions

The workflow has been configured with these permissions:
- `contents: write` - To make commits to PR branches
- `pull-requests: write` - To comment on PRs
- `issues: write` - To respond to issue comments

## How to Use

### On Pull Requests

1. Create a pull request
2. Comment with instructions for Claude, e.g.:
   - `@claude please review this PR`
   - `@claude add error handling to the sync function`
   - `@claude write tests for the new feature`

### On Issues

1. Open or comment on an issue
2. Mention Claude with your request:
   - `@claude can you implement this feature?`
   - `@claude please investigate this bug`

### Example Commands

```
@claude please review this code for security issues

@claude add type hints to all functions in attendance.py

@claude create a test file for the sync module

@claude fix the failing test in test_production_sync.py

@claude update the documentation to reflect the new API endpoint
```

## Workflow Configuration

The workflow is defined in `.github/workflows/claude-code.yml`:

```yaml
name: Claude Code Action

on:
  pull_request:
    types: [opened, synchronize, reopened]
  issue_comment:
    types: [created, edited]

permissions:
  contents: write
  pull-requests: write
  issues: write

jobs:
  claude-code:
    runs-on: ubuntu-latest
    
    steps:
      - name: Claude Code Action Official
        uses: anthropics/claude-code-action@v1
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Troubleshooting

### Action Not Running

- Verify `ANTHROPIC_API_KEY` is set in repository secrets
- Check that workflow file is on the default branch
- Ensure GitHub Actions are enabled in repository settings

### Permission Errors

- Verify the workflow has write permissions to contents and PRs
- Check repository settings: **Settings** → **Actions** → **General** → **Workflow permissions**
- Set to "Read and write permissions"

### API Rate Limits

- The action uses your Anthropic API quota
- Monitor usage at https://console.anthropic.com/
- Consider implementing usage limits or branch restrictions for large repos

## More Information

- [Claude Code Action Documentation](https://github.com/anthropics/claude-code-action)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
