# Real Hardware Testing Reveals Bugs Code Review Can't

**Date**: 2026-02-24
**Context**: Camera proximity greeting plugin tested on actual kiosk with real users
**Project**: trackattendance-frontend

## Pattern

When building hardware-interactive features (cameras, sensors, scanners), **real-world testing on target hardware** catches entire categories of bugs that code review and unit tests miss:

| Bug Found | How Discovered | Would Code Review Catch It? |
|-----------|---------------|---------------------------|
| Greeting repeats in queue | Users lined up at kiosk | No — requires physical queue |
| False positives from shadows | Camera seeing empty room | No — requires actual lighting conditions |
| Audio overlap (greeting + thank you) | Badge scanned while greeting plays | Unlikely — two separate audio systems |
| Greeting fires on chair backs | MediaPipe low confidence | No — requires actual camera + environment |

### Approach
1. Get the feature working in code (state machine, thread safety, etc.)
2. Deploy to actual hardware ASAP — even if rough
3. Let real users interact with it
4. Each bug report from real use = one iteration cycle
5. Repeat until stable

### Anti-pattern
Spending weeks perfecting the code in isolation before any hardware testing. You'll fix the wrong problems.

## Tags
`testing`, `hardware`, `camera`, `real-world`, `iteration`
