# Tiered Search Architecture for Name Lookup

**Date**: 2026-03-14
**Context**: TrackAttendance employee name lookup with typo tolerance
**Confidence**: High

## Key Learning

When building a name search feature for a kiosk/attendance system, a single search strategy (exact substring match) fails for real-world input. Users type names with extra spaces, reversed order, and typos. A 3-tier search architecture handles all these cases while keeping exact matches fast and prioritized.

The key insight is that each tier has clear semantics and a natural fallback chain. Exact substring is tried first (fastest, most relevant). If nothing matches, word-order-independent matching catches reversed names. Only if both fail does fuzzy matching activate, which tolerates 1-2 character typos using `difflib.SequenceMatcher` with a 0.75 threshold.

Whitespace normalization (`" ".join(s.split())`) should happen at both import time (in `_safe_string()`) and query time. This ensures Excel data with inconsistent spacing is cleaned once and matched consistently.

## The Pattern

```python
def search_employee(self, query: str) -> List[Dict]:
    query = " ".join(query.split()).lower()  # normalize whitespace
    query_words = query.split()
    exact, word_match, fuzzy = [], [], []

    for emp in employees:
        name = " ".join(emp.full_name.split()).lower()

        # Tier 1: exact substring
        if query in name:
            exact.append(emp)
            continue

        # Tier 2: all words present (any order)
        if len(query_words) > 1 and all(w in name for w in query_words):
            word_match.append(emp)
            continue

        # Tier 3: fuzzy (tolerate typos)
        if _fuzzy_word_score(query_words, name.split()) >= 0.75:
            fuzzy.append((score, emp))

    return exact[:10] or word_match[:10] or sorted(fuzzy)[:10]

def _fuzzy_word_score(query_words, name_words) -> float:
    from difflib import SequenceMatcher
    return sum(
        max(SequenceMatcher(None, qw, nw).ratio() for nw in name_words)
        for qw in query_words
    ) / len(query_words)
```

## Why This Matters

This pattern applies to any lookup feature where users type freeform text to find records. The 3-tier approach avoids the common trap of either (a) only doing exact match (misses typos) or (b) always doing fuzzy match (pollutes results with irrelevant matches when exact is available). Using stdlib `difflib` means no external dependencies — important for a compiled desktop app where every dependency adds to binary size and potential compatibility issues.

The 0.75 threshold was chosen empirically: it catches common typos (1-2 chars off in 5-7 char names) while rejecting completely unrelated names. For different name character distributions (e.g., Thai names), the threshold may need adjustment.

## Tags

`search`, `fuzzy-matching`, `difflib`, `whitespace-normalization`, `name-lookup`, `tiered-architecture`, `python`
