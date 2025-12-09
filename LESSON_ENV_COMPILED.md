# Lesson Learned: .env Files & PyInstaller Compilation Strategy

## Problem

When compiling Python applications to .exe with PyInstaller:
- .env file is NOT automatically bundled
- Compiled app crashes if .env is missing
- Hard to manage different .env files per environment
- Unclear how to deploy configuration with executable

## Three Approaches

### Approach 1: External .env (Recommended for Secrets)

```
Program Files/
└── TrackAttendance/
    └── TrackAttendance.exe

C:/Users/user/.gcp/
├── credentials.json
└── .env (alongside executable)
```

**Pros:**
- Easy to update without recompiling
- Secrets stay outside executable
- Different .env per machine
- Follows best practices

**Cons:**
- User must manage .env file manually
- Risk of losing .env during upgrades
- More deployment steps

**Implementation:**
```bash
python main.py
# Looks for .env in current directory
# Falls back to environment variables
```

### Approach 2: Bundle .env with PyInstaller

```
Program Files/
└── TrackAttendance/
    ├── TrackAttendance.exe
    ├── _internal/
    └── .env (bundled inside)
```

**Pros:**
- Single file to deploy (.env inside executable)
- Configuration travels with app
- User doesn't need to manage .env

**Cons:**
- Secrets bundled with executable
- Hard to update without recompiling
- Security risk if .env exposed
- Different .env per environment needs rebuild

**PyInstaller Command:**
```bash
pyinstaller \
  --add-data "src/config/.env:config" \
  --add-data "data:data" \
  TrackAttendance.spec
```

**Code to Load Bundled .env:**
```python
import sys
from pathlib import Path
from dotenv import load_dotenv

if getattr(sys, 'frozen', False):
    # Running as compiled .exe
    bundled_env = Path(sys._MEIPASS) / 'config' / '.env'
    if bundled_env.exists():
        load_dotenv(bundled_env)
else:
    # Running as Python script
    load_dotenv('.env')
```

### Approach 3: Hybrid (Recommended for Production)

```
Program Files/
└── TrackAttendance/
    ├── TrackAttendance.exe
    └── .env.default (bundled, non-secret)

C:/ProgramData/TrackAttendance/
└── .env (local overrides, ignored by installer)
```

**Pros:**
- Defaults bundled with app
- Local overrides per machine
- Easy updates
- Flexible deployment

**Cons:**
- More complex setup
- Two configuration files to manage

**Implementation:**
```python
if getattr(sys, 'frozen', False):
    # Load bundled defaults
    bundled_env = Path(sys._MEIPASS) / '.env.default'
    if bundled_env.exists():
        load_dotenv(bundled_env)

    # Override with local config
    local_env = Path('C:/ProgramData/TrackAttendance/.env')
    if local_env.exists():
        load_dotenv(local_env)
else:
    # Development: just load .env
    load_dotenv('.env')
```

## Detecting Compiled vs Script

```python
import sys

if getattr(sys, 'frozen', False):
    # Running as compiled executable
    base_path = Path(sys._MEIPASS)
    print(f'Running as: Compiled .exe at {base_path}')
else:
    # Running as Python script
    base_path = Path(__file__).parent
    print(f'Running as: Python script at {base_path}')
```

## How Bundled Files are Extracted

When .exe runs:
1. PyInstaller extracts _internal to temp folder
2. `sys._MEIPASS` points to temp folder
3. .env is at: `{temp_folder}/_internal/config/.env`
4. Code reads from: `Path(sys._MEIPASS) / 'config' / '.env'`
5. On exit: temp folder cleaned up

**Example temp path:**
```
C:\Users\user\AppData\Local\Temp\_MEI123456/
```

## Security Considerations

### Risk 1: Secrets in Compiled Executable
- If .env is bundled, it's part of the .exe file
- Anyone can extract it with tools (7z, etc.)
- Use only for non-secret configuration

### Risk 2: Temp File Security
- Bundled .env extracted to temp folder
- Temp folder may be readable by other users
- Don't store highly sensitive secrets this way

### Recommendation

**Bundle (Non-Secret Configuration):**
```env
SHOW_FULL_SCREEN=True
AUTO_SYNC_IDLE_SECONDS=30
CLOUD_API_URL=https://api.example.com
```

**Keep External (Secrets Only):**
```env
CLOUD_API_KEY=secret-key-12345
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
```

## Complete Production Example

**config.py:**
```python
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Detect if running as compiled exe
if getattr(sys, 'frozen', False):
    # Running as .exe
    bundled_env = Path(sys._MEIPASS) / 'config' / '.env.default'
    if bundled_env.exists():
        load_dotenv(bundled_env)

    # Override with local config
    local_env = Path.home() / '.gcp' / '.env.local'
    if local_env.exists():
        load_dotenv(local_env)
else:
    # Running as Python script (development)
    load_dotenv(Path(__file__).parent / '.env')

# Load configuration
CLOUD_API_URL = os.getenv('CLOUD_API_URL', '...')
CLOUD_API_KEY = os.getenv('CLOUD_API_KEY')

# Fail if required settings missing
if not CLOUD_API_KEY:
    print('ERROR: CLOUD_API_KEY not set')
    sys.exit(1)
```

## Updated PyInstaller Spec

```python
# TrackAttendance.spec
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('.env.default', 'config'),        # Bundle default config
        ('data', 'data'),                   # Bundle data folder
        ('logs', 'logs'),                   # Bundle empty logs folder
        ('web', 'web'),                     # Bundle web assets
    ],
    hiddenimports=[
        'dotenv',
        'requests',
        'openpyxl',
    ],
    ...
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TrackAttendance',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    icon='assets/track_attendance.ico',
)
```

## Deployment Scenarios

### Scenario A: Local Testing
```bash
python main.py
# Uses .env in project root
```

### Scenario B: Compiled on Dev Machine
```bash
pyinstaller TrackAttendance.spec
dist/TrackAttendance/TrackAttendance.exe
# Uses bundled .env.default
# Can override with C:/Users/user/.gcp/.env.local
```

### Scenario C: Production Installation
```bash
# Copy TrackAttendance.exe to Program Files
# Create C:/ProgramData/TrackAttendance/.env with prod settings
# Run TrackAttendance.exe
# Uses bundled .env.default as fallback
# Uses prod .env for overrides
```

## Testing Bundled Config

**Test 1: Extract and inspect**
```bash
# Extract .exe contents
7z x TrackAttendance.exe -o_extracted

# Find bundled files
dir _extracted/_internal/config/

# Verify .env is there
type _extracted/_internal/config/.env
```

**Test 2: Verify loading**
```python
# Create test script
import sys
sys.frozen = True
sys._MEIPASS = r'C:\extracted\_internal'

from config import CLOUD_API_URL
print(f'Loaded from bundled: {CLOUD_API_URL}')
```

**Test 3: Override behavior**
```bash
# Set environment variable
set CLOUD_API_URL=http://override

# Run exe
TrackAttendance.exe

# Should use override
```

## Recommendation for TrackAttendance

**Current (Development):**
- External .env ✓
- Secrets in ~/.gcp/ ✓
- No bundling needed ✓

**Recommended for Production:**
- Bundle .env.default (non-secrets) ✓
- Keep CLOUD_API_KEY in environment variable ✓
- Allow local override in C:/ProgramData/ ✓
- Installer sets up directory structure ✓

## Checklist for Distribution

**Before compiling:**
- [ ] Remove .env from project (only keep .env.example)
- [ ] Create .env.default with non-secret defaults
- [ ] Verify config.py detects compiled vs script
- [ ] Test with sys.frozen=True

**In PyInstaller spec:**
- [ ] Add .env.default to datas
- [ ] Add required modules to hiddenimports
- [ ] Set icon for .exe
- [ ] Set console=False for GUI apps

**After compilation:**
- [ ] Extract .exe and verify bundled files
- [ ] Test that .env.default loads
- [ ] Test that environment variables override
- [ ] Test that local .env.local overrides

**In installer/deployment:**
- [ ] Create directory for local config
- [ ] Document where to put .env or secrets
- [ ] Provide .env.example template
- [ ] Test on clean machine

## Key Takeaways

1. **Don't bundle secrets** - Extract and override with external config
2. **Use hybrid approach** - Bundle defaults, allow local overrides
3. **Detect compilation** - Use `sys.frozen` to handle .exe vs script
4. **sys._MEIPASS** - Points to bundled resources in compiled app
5. **Temp extraction** - Bundled files extracted to temp on startup
6. **Configuration hierarchy** - Environment > local .env > bundled defaults
7. **Test thoroughly** - Verify bundled config loads and can be overridden
