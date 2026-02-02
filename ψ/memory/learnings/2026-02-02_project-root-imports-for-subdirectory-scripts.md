---
title: Project Root Imports for Subdirectory Scripts
tags: [python, imports, project-structure, sys-path, trackattendance]
created: 2026-02-02
source: "rrr: Jarkius/trackattendance-frontend"
---

# Project Root Imports for Subdirectory Scripts

When moving Python scripts from project root into subdirectories (`scripts/`, `tests/`), relative imports like `from database import DatabaseManager` break because the parent directory isn't on sys.path.

## The Pattern

```python
import os
import sys
from pathlib import Path

# Resolve project root (parent of scripts/ or tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# Now imports work as if running from root
from config import CLOUD_API_URL, CLOUD_API_KEY
from database import DatabaseManager
```

Key points:
- Use `Path(__file__).resolve()` not `os.path.abspath` — handles symlinks correctly
- `sys.path.insert(0, ...)` not `append` — ensures project modules take precedence
- `os.chdir(PROJECT_ROOT)` — fixes relative file paths like `Path("data/database.db")`
- Place before any project imports

## Why This Matters

Moving scripts to subdirectories is standard project hygiene, but Python's import system assumes scripts run from their parent directory. This 4-line pattern makes any script location-independent without requiring `__init__.py` files or package installation.

Also prevents hardcoded API keys — scripts can import from `config.py` which reads `.env` files, instead of embedding secrets directly.

---
*Added via Oracle Learn*
