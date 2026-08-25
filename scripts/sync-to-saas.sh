#!/usr/bin/env bash
# Diff trackattendance-latest (internal Deloitte tool) against
# trackattendance-saas (commercial fork) for the set of files most likely to
# carry shared bugfixes, and optionally port the ones that actually differ.
#
# Why this exists: the two repos are separate git histories on purpose (no
# GitHub fork lineage), so there's no `git merge`/cherry-pick path between
# them. Each sync pass has to diff-then-copy by hand. This script automates
# the "which files actually differ" step and the "copy + reapply rebranding"
# step, so a sync doesn't require re-deriving the process each time.
#
# What it does NOT do: decide whether a fix is Deloitte-specific and
# shouldn't be ported at all (e.g. shutdown-path changes tied to Deloitte's
# own Cloud Run URL) — that judgment call stays manual. It only tells you
# what's different and copies what you ask it to.
#
# Usage:
#   scripts/sync-to-saas.sh                 # report only — lists files that differ
#   scripts/sync-to-saas.sh --apply <file>  # copy one file over + reapply rebranding
#   scripts/sync-to-saas.sh --apply-all     # copy every differing file + reapply rebranding
#
# After running --apply/--apply-all, review the result in the saas repo,
# commit, push, and open a PR there yourself — this script never commits.

set -euo pipefail

LATEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAAS_DIR="${TRACKATTENDANCE_SAAS_DIR:-C:/Workspace/Projects/trackattendance-saas}"

if [ ! -d "$SAAS_DIR/.git" ]; then
    echo "trackattendance-saas not found at: $SAAS_DIR" >&2
    echo "Set TRACKATTENDANCE_SAAS_DIR if it lives somewhere else." >&2
    exit 1
fi

# Files worth checking on every sync pass — the ones that have carried real
# shared bugfixes so far. Add to this list as new shared files accumulate
# fixes worth porting; don't add saas-only files (billing, licensing) or
# files that are expected to permanently diverge (README.md's branding).
CANDIDATE_FILES=(
    "attendance.py"
    "main.py"
    "sync.py"
    "database.py"
    "config.py"
    "dashboard.py"
    "web/script.js"
    "web/css/style.css"
    ".github/workflows/test.yml"
    "TrackAttendance.spec"
    "requirements.txt"
)

# Files that need --brand-*/#2563eb rebranding reapplied after copying,
# because they contain --deloitte-* CSS variables or the Deloitte green hex.
# Kept as a subset, not "all files", so plain Python files without any color
# references don't get needlessly run through the rename pass.
REBRAND_FILES=(
    "web/script.js"
    "web/css/style.css"
    "main.py"
)

reapply_rebranding() {
    local target="$1"
    node -e "
        const fs = require('fs');
        const path = process.argv[1];
        let content = fs.readFileSync(path, 'utf8');
        const renames = [
            ['--deloitte-green', '--brand-primary'],
            ['--deloitte-black', '--brand-black'],
            ['--deloitte-grey-dark', '--brand-grey-dark'],
            ['--deloitte-grey-medium', '--brand-grey-medium'],
            ['--deloitte-grey-light', '--brand-grey-light'],
        ];
        for (const [oldName, newName] of renames) {
            content = content.split(oldName).join(newName);
        }
        content = content.replace(/#86bc25/gi, '#2563eb');
        content = content.replace(/134,\s*188,\s*37/g, '37, 99, 235');
        fs.writeFileSync(path, content);
    " "$target"
}

needs_rebranding() {
    local file="$1"
    for f in "${REBRAND_FILES[@]}"; do
        if [ "$f" = "$file" ]; then
            return 0
        fi
    done
    return 1
}

apply_file() {
    local file="$1"
    local src="$LATEST_DIR/$file"
    local dest="$SAAS_DIR/$file"

    if [ ! -f "$src" ]; then
        echo "  SKIP (not found in trackattendance-latest): $file"
        return
    fi

    mkdir -p "$(dirname "$dest")"
    cp "$src" "$dest"

    if needs_rebranding "$file"; then
        reapply_rebranding "$dest"
        echo "  copied + rebranded: $file"
    else
        echo "  copied: $file"
    fi
}

report_only() {
    echo "Comparing trackattendance-latest (main) against trackattendance-saas (main)..."
    echo

    local any_diff=false
    for file in "${CANDIDATE_FILES[@]}"; do
        local src="$LATEST_DIR/$file"
        local dest="$SAAS_DIR/$file"

        if [ ! -f "$src" ]; then
            continue
        fi
        if [ ! -f "$dest" ]; then
            echo "  NEW (doesn't exist in saas yet): $file"
            any_diff=true
            continue
        fi

        # Compare after simulating the rebranding pass on a temp copy, so a
        # file that's only different because of --deloitte-* naming doesn't
        # show up as a false-positive diff.
        if needs_rebranding "$file"; then
            local tmp
            tmp="$(mktemp)"
            cp "$src" "$tmp"
            reapply_rebranding "$tmp"
            if ! diff -q "$tmp" "$dest" > /dev/null 2>&1; then
                echo "  DIFFERS: $file"
                any_diff=true
            fi
            rm -f "$tmp"
        else
            if ! diff -q "$src" "$dest" > /dev/null 2>&1; then
                echo "  DIFFERS: $file"
                any_diff=true
            fi
        fi
    done

    if [ "$any_diff" = false ]; then
        echo "No differences found — trackattendance-saas is up to date with the tracked files."
    else
        echo
        echo "Run 'scripts/sync-to-saas.sh --apply <file>' to port one file, or"
        echo "'scripts/sync-to-saas.sh --apply-all' to port everything listed above."
        echo "This only copies files — review, commit, and PR the result in trackattendance-saas yourself."
    fi
}

case "${1:-}" in
    "")
        report_only
        ;;
    --apply)
        if [ -z "${2:-}" ]; then
            echo "Usage: scripts/sync-to-saas.sh --apply <file>" >&2
            exit 1
        fi
        apply_file "$2"
        ;;
    --apply-all)
        for file in "${CANDIDATE_FILES[@]}"; do
            src="$LATEST_DIR/$file"
            dest="$SAAS_DIR/$file"
            if [ ! -f "$src" ]; then
                continue
            fi
            if needs_rebranding "$file"; then
                tmp="$(mktemp)"
                cp "$src" "$tmp"
                reapply_rebranding "$tmp"
                if [ -f "$dest" ] && diff -q "$tmp" "$dest" > /dev/null 2>&1; then
                    rm -f "$tmp"
                    continue
                fi
                rm -f "$tmp"
            else
                if [ -f "$dest" ] && diff -q "$src" "$dest" > /dev/null 2>&1; then
                    continue
                fi
            fi
            apply_file "$file"
        done
        ;;
    -h|--help)
        echo "Usage:"
        echo "  scripts/sync-to-saas.sh                 # report only"
        echo "  scripts/sync-to-saas.sh --apply <file>  # port one file"
        echo "  scripts/sync-to-saas.sh --apply-all     # port every differing file"
        ;;
    *)
        echo "Unknown argument: $1" >&2
        exit 1
        ;;
esac
