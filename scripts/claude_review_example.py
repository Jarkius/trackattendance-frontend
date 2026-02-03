#!/usr/bin/env python3
"""
Example script showing how to integrate Claude API for code review.

This is a TEMPLATE. To use:
1. Install: pip install anthropic requests
2. Set environment variable: ANTHROPIC_API_KEY
3. Customize the prompts and logic for your needs
4. Use in GitHub Actions or locally

Usage:
    python claude_review_example.py --file main.py
    python claude_review_example.py --pr 123
"""

import os
import sys
import argparse
from anthropic import Anthropic


def review_file(file_path: str, api_key: str) -> dict:
    """
    Use Claude to review a single file.
    
    Args:
        file_path: Path to the file to review
        api_key: Anthropic API key
        
    Returns:
        dict with review results
    """
    # Read file content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return {"error": f"Failed to read file: {e}"}
    
    # Initialize Claude client
    client = Anthropic(api_key=api_key)
    
    # Create review prompt
    prompt = f"""Please review this code file for:
1. Potential bugs or errors
2. Security vulnerabilities
3. Performance issues
4. Code quality and best practices
5. Maintainability concerns

File: {file_path}

```
{content}
```

Provide a structured review with specific line numbers where applicable.
Focus on issues that genuinely matter - don't comment on style or formatting.
"""
    
    # Call Claude API
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        return {
            "file": file_path,
            "review": message.content[0].text,
            "model": "claude-3-5-sonnet-20241022"
        }
    except Exception as e:
        return {"error": f"Claude API error: {e}"}


def review_diff(diff_text: str, api_key: str) -> dict:
    """
    Use Claude to review a git diff.
    
    Args:
        diff_text: Git diff output
        api_key: Anthropic API key
        
    Returns:
        dict with review results
    """
    client = Anthropic(api_key=api_key)
    
    prompt = f"""Please review these code changes for:
1. Potential bugs introduced
2. Security implications
3. Breaking changes
4. Missing error handling
5. Test coverage needed

Git diff:
```
{diff_text}
```

Provide actionable feedback on the changes.
"""
    
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        return {
            "review": message.content[0].text,
            "model": "claude-3-5-sonnet-20241022"
        }
    except Exception as e:
        return {"error": f"Claude API error: {e}"}


def review_pull_request(pr_number: int, api_key: str, github_token: str) -> dict:
    """
    Use Claude to review an entire pull request.
    
    Args:
        pr_number: GitHub PR number
        api_key: Anthropic API key
        github_token: GitHub API token
        
    Returns:
        dict with review results
    """
    import requests
    
    # Get repository info from environment or git config
    # This is a simplified example - you'd need proper repo detection
    repo = os.environ.get('GITHUB_REPOSITORY', 'owner/repo')
    
    # Fetch PR diff from GitHub API
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3.diff"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        diff = response.text
    except Exception as e:
        return {"error": f"Failed to fetch PR: {e}"}
    
    # Review the diff
    return review_diff(diff, api_key)


def main():
    parser = argparse.ArgumentParser(
        description="Use Claude to review code"
    )
    parser.add_argument(
        "--file",
        help="Path to file to review"
    )
    parser.add_argument(
        "--pr",
        type=int,
        help="GitHub PR number to review"
    )
    parser.add_argument(
        "--diff",
        help="Path to diff file to review"
    )
    
    args = parser.parse_args()
    
    # Get API keys from environment
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    # Execute requested review
    result = None
    
    if args.file:
        result = review_file(args.file, api_key)
    elif args.pr:
        github_token = os.environ.get("GITHUB_TOKEN")
        if not github_token:
            print("Error: GITHUB_TOKEN environment variable not set")
            sys.exit(1)
        result = review_pull_request(args.pr, api_key, github_token)
    elif args.diff:
        try:
            with open(args.diff, 'r') as f:
                diff_text = f.read()
            result = review_diff(diff_text, api_key)
        except Exception as e:
            result = {"error": f"Failed to read diff: {e}"}
    else:
        parser.print_help()
        sys.exit(1)
    
    # Output results
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)
    else:
        print("\n=== Claude Code Review ===\n")
        if "file" in result:
            print(f"File: {result['file']}")
        print(f"\n{result['review']}\n")
        print(f"Model: {result.get('model', 'N/A')}")


if __name__ == "__main__":
    main()
