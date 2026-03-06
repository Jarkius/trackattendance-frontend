# Lesson: WebKit Range Slider Track Styling

**Date**: 2026-03-06
**Context**: Fixing admin panel slider CSS in PyQt6 QWebEngineView (Chromium-based)
**Source**: rrr: trackattendance-frontend

## Problem

Setting `background: linear-gradient(...)` on an `input[type=range]` element creates a "border" effect in WebKit/Chromium — the green fill appears as thin lines around a grey track instead of a solid fill bar.

## Root Cause

In WebKit, the `<input type=range>` has two layers:
1. The **element background** (where we put the gradient)
2. The **`-webkit-slider-runnable-track`** pseudo-element (which has its own background, often overridden by CSS frameworks like Materialize)

The track renders **on top of** the element background, obscuring the gradient.

## Solution

```css
.slider {
    background: transparent !important;  /* Clear element bg */
}
.slider::-webkit-slider-runnable-track {
    background: linear-gradient(to right, #86bc25 var(--fill), #ddd var(--fill)) !important;
    /* Put gradient HERE, on the track */
}
```

Use `!important` to override Materialize/framework defaults. Update `--fill` CSS variable via JS on `input` event.

## Key Insight

Always style the **track pseudo-element** for range inputs in WebKit, not the element itself. The element background is only visible around the edges (creating the "border" illusion).
