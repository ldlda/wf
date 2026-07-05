# Presentation Visual Review

## Review States

Open each URL in a browser at 100% zoom, 1280x720 viewport:

1. **Scene 6 root**: `http://127.0.0.1:5173/present#scene/architecture/client`
2. **Scene 6 runtime**: `http://127.0.0.1:5173/present#scene/architecture/runtime/focus/runtime-providers`
3. **Scene 6 providers**: `http://127.0.0.1:5173/present#scene/architecture/runtime/focus/runtime-providers/configured-providers`
4. **Console**: `http://127.0.0.1:5173/console`

## Adaptive Canvas Matrix

Review these routes at `1024x768`, `1200x800`, and `1280x720`, always at 100%
browser zoom:

1. `/present#scene/architecture/node-use/focus/node-use`
2. `/present#scene/interrupt-evidence/trace`

The logical canvas widths must be `960`, `1080`, and `1280` respectively.
Capture the receipt state and open-inspector state at each viewport. Confirm
no page scroll, unchanged primary geometry, bounded raw evidence, focus
restoration, compact chat exclusion, and a clean browser console.

## Automated Smoke

```bash
pnpm --filter @lda/console exec vitest run
pnpm --filter @lda/console typecheck
pnpm --filter @lda/console build
```

## Browser Checklist

1. 1024x768 uses a 960x720 logical canvas without vertical letterboxing
2. 1200x800 uses a 1080x720 logical canvas
3. 1280x720 uses a 1280x720 logical canvas
4. Ratios outside 4:3 through 16:9 letterbox at the nearest supported ratio
5. Warm Editorial Canvas unchanged across Scene 1 and Scene 6
6. No scene rail, replay label, discussion button, or presenter controls
7. Scene 6 root has one primary figure and no competing card grid
8. Runtime & providers expands in place with breadcrumb
9. Configured providers expands second level
10. Escape pops exactly one level
11. Tab, arrows, and Enter work without advancing presentation while figure focus active
12. Deep links reproduce both focus depths after reload
13. Every visible node readable without relying on color
14. No vertical or horizontal scrollbar
15. Console retains connection, lifecycle, graph, and execution layouts
16. Reduced-motion mode preserves all figure content
17. Evidence beats show a receipt but never auto-open the inspector
18. Opening the inspector leaves primary geometry unchanged
19. Escape closes the inspector and restores focus
20. Compact chat is hidden while the inspector is open

Screenshots require human approval and are not pixel-diff tests.
