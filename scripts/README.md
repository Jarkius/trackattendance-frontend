# Scripts Directory

This directory contains utility scripts for the TrackAttendance Frontend application.

## Categories

### Database Management
- `reset_failed_scans.py` - Reset failed scans back to pending status
- `migrate_sync_schema.py` - Database schema migrations for sync features
- `create_test_scan.py` - Insert test scan records for debugging

### Debugging & Performance
- `debug_sync_performance.py` - Profile sync bottlenecks and performance issues
- `check_timestamp_format.py` - Verify timestamp formats in database

### Integration Examples
- `claude_review_example.py` - Example script showing Claude API integration for code review

## Usage

Most scripts can be run directly:

```bash
python scripts/script_name.py
```

Some scripts accept command-line arguments. Use `--help` to see options:

```bash
python scripts/script_name.py --help
```

## Integration Examples

### Claude Review Example

**Purpose**: Demonstrates how to integrate Claude API for automated code reviews.

**Dependencies**:
```bash
pip install anthropic requests
```

**Usage**:
```bash
# Set API key
export ANTHROPIC_API_KEY="your-key-here"

# Review a single file
python scripts/claude_review_example.py --file main.py

# Review a git diff
git diff > changes.diff
python scripts/claude_review_example.py --diff changes.diff

# Review a pull request (requires GITHUB_TOKEN)
export GITHUB_TOKEN="your-github-token"
python scripts/claude_review_example.py --pr 123
```

**Note**: This is a template script. Customize it for your specific needs. See [docs/CLAUDE_INTEGRATION_GUIDE.md](../docs/CLAUDE_INTEGRATION_GUIDE.md) for more information.

## Adding New Scripts

When adding new scripts:

1. Add a docstring explaining the purpose
2. Use command-line arguments for flexibility
3. Include error handling
4. Update this README with usage instructions
5. Add the script to the appropriate category above

## Requirements

Most scripts use the main application dependencies from `requirements.txt`. Integration examples may require additional packages as noted in their docstrings.
