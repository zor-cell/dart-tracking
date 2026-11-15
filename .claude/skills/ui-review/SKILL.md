---
name: ui-review
description: Review a view of this dart-tracking Angular app for clean, mobile-first, accessible UI built from PrimeNG and the app's shared components. Use after building or changing a view, when asked to check, polish or review the UI or UX, or when something "looks off" on the phone. Checks the code and the running page at phone width, then fixes what it finds.
---

# Review a view

The app is a mobile-first web app. A view is done when it reads well at 375 px,
uses PrimeNG and the shared blocks instead of hand-made ones, and passes AXE.

## 1. Code pass

Read the component's `.ts`, `.html` and `.scss` (and the diff, if reviewing a change)
against `docs/guidelines/frontend-best-practices.md`. Flag:

- **Hand-built where a library piece exists**: custom buttons, spinners, dropdowns,
  dialogs, tabs, tags, toggles, tables. Replace with the PrimeNG component; look up its
  inputs, templates and pass-through options via the PrimeNG MCP server or docs.
- **Shared blocks not used**: loading, empty, error states, tables, toolbars, filters,
  confirmations, dialogs, step buttons, stat links — see "Consistency and reuse".
  Also a second variant of something the app already has (wording or component).
- **Styling**: hex colours or fallbacks instead of `var(--p-…)`, styles that fight the
  theme (overriding PrimeNG internals with deep selectors), magic pixel values for
  spacing where a token exists, `ngClass`/`ngStyle`.
- **Template**: `*ngIf`/`*ngFor`, logic that belongs in a `computed()`, missing i18n
  ids, middle dots in joined labels.

## 2. Look at it running

1. `preview_start` with `{name: "frontend"}` (backend: `{name: "backend"}` if the view
   needs data). Before anything that could play audio, set announcerVolume to 0.
2. `resize_window` preset `mobile` (375×812), reload, navigate to the view. Check light
   and dark (`colorScheme`).
3. Inspect with `read_page` and screenshots, then measure with `javascript_tool`:
   - No horizontal page scroll: `document.documentElement.scrollWidth <= innerWidth`.
   - Control rows and pill rows stay on one line; pills scroll sideways, never wrap.
   - Gaps in flex containers are even — an empty host element doubles a gap.
   - Touch targets at least 44×44 px; nothing important hidden below the first screen
     on the main action of the view.
   - Loading, empty and error states look right (throttle or stub if needed).
4. Run AXE on the page:
   ```js
   await import('https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js');
   (await axe.run()).violations.map(v => [v.id, v.impact, v.nodes.length])
   ```
   Every violation is a finding; also check focus order and visible focus by keyboard.
5. Check `tablet` and the default desktop size once, so wider screens do not stretch
   or float oddly.
6. Reset with preset `desktop` when done.

## 3. Report and fix

List findings most important first, each with where it is and the concrete fix
(which PrimeNG component or shared block replaces what). Then fix them, recheck at
375 px, and show a final phone-width screenshot. If a fix needs a new shared block
(the same thing needed twice), extract it into `core/` rather than copying it.
