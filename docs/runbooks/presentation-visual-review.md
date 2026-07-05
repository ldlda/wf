# Presentation Visual Review

## Review States

Open each URL in a browser at 100% zoom, 1280x720 viewport:

1. **Scene 6 root**: `http://127.0.0.1:5173/present#scene/architecture/client`
2. **Scene 6 runtime**: `http://127.0.0.1:5173/present#scene/architecture/runtime/focus/runtime-providers`
3. **Scene 6 providers**: `http://127.0.0.1:5173/present#scene/architecture/runtime/focus/runtime-providers/configured-providers`
4. **Console**: `http://127.0.0.1:5173/console`

## Automated Smoke

```bash
pnpm --filter @lda/console exec vitest run
pnpm --filter @lda/console typecheck
pnpm --filter @lda/console build
```

## Browser Checklist

1. Canvas is exactly 1280x720 at matching viewport
2. 1024x768 scales to 0.8 with vertical letterboxing and no reflow
3. Warm Editorial Canvas unchanged across Scene 1 and Scene 6
4. No scene rail, replay label, discussion button, or presenter controls
5. Scene 6 root has one primary figure and no competing card grid
6. Runtime & providers expands in place with breadcrumb
7. Configured providers expands second level
8. Escape pops exactly one level
9. Tab, arrows, and Enter work without advancing presentation while figure focus active
10. Deep links reproduce both focus depths after reload
11. Every visible node readable without relying on color
12. No vertical or horizontal scrollbar
13. Console retains connection, lifecycle, graph, and execution layouts
14. Reduced-motion mode preserves all figure content

Screenshots require human approval and are not pixel-diff tests.
