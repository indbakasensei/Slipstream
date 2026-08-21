# 07 - GUI/UX Audit

**Audit Version:** v2.3.0-dev | **Date:** 2026-08-21 | **Auditor:** Freebuff

---

## 1. Design System: 9/10

Token-based system in gui/theme.py. Spacing scale 4-based (4/8/12/16/24/32/48).
Elevation ladder (BG_WINDOW < BG_PANEL < BG_FIELD < BG_CARD < BG_ELEVATED).
Typography roles (display/h1/h2/body/caption/stat). Shared STATUS_COLORS.
Single QSS stylesheet applied at startup. No per-widget inline styles.

## 2. Layout Hierarchy: 8.5/10

Clear hierarchy: sidebar < center < queue. Dashboard KPI cards for status.
Monitor cards answer one question each. Queue is engineering worklist.
Compact 30px rows. Consistent spacing tokens throughout.

## 3. Responsive: 9/10

Minimum width floors (MIN_SIDEBAR=200, MIN_CENTER=420, MIN_QUEUE=320).
Non-collapsible splitter. Content scrolls not clips.
Focus Mode gives full window. Queue collapse preserves width.
Min ~773px with bottom group, ~555px without.

## 4. Dock Architecture: 8/10

Monitor/Parameters hidden by default. Focus Mode saves/restores state.
View menu for dock toggling. First-show width for right docks.
Gap: No floating windows. No dock persistence to disk.

## 5. Keyboard UX: 7/10

| Shortcut | Action |
|----------|--------|
| F5 | Run All |
| Shift+F5 | Stop |
| Ctrl+O | Open Project |
| Ctrl+R | Reload |
| Ctrl+Q | Exit |
| Ctrl+A | Select all |

Gaps: No shortcut for Queue collapse, Focus Mode, page switching, dock toggle.

## 6. Discoverability: 8/10

Mock mode unmissable (orange banner). WorkspaceHeader shows context.
Empty states guide users. Console provides discoverability.
Monitor/Parameters hidden by default (discoverable via View menu only).

## 7. UX Health: 8.2/10

*This document is part of the Freebuff Engineering Audit.*