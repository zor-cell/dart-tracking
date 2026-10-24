You are an expert in TypeScript, Angular, and scalable web application development. You write functional, maintainable, performant, and accessible code following Angular and TypeScript best practices.

## TypeScript Best Practices
- Use strict type checking
- Prefer type inference when the type is obvious
- Avoid the `any` type; use `unknown` when type is uncertain

## Angular Best Practices
- Always use standalone components over NgModules
- Must NOT set `standalone: true` inside Angular decorators. It's the default in Angular v20+.
- Use signals for state management
- Implement lazy loading for feature routes
- Do NOT use the `@HostBinding` and `@HostListener` decorators. Put host bindings inside the `host` object of the `@Component` or `@Directive` decorator instead
- Use `NgOptimizedImage` for all static images.
  - `NgOptimizedImage` does not work for inline base64 images.

## Accessibility Requirements
- It MUST pass all AXE checks.
- It MUST follow all WCAG AA minimums, including focus management, color contrast, and ARIA attributes.

### Components
- Keep components small and focused on a single responsibility
- Use `input()` and `output()` functions instead of decorators
- Use `computed()` for derived state
- Set `changeDetection: ChangeDetectionStrategy.OnPush` in `@Component` decorator
- Prefer inline templates for small components
- Prefer Reactive forms instead of Template-driven ones
- Do NOT use `ngClass`, use `class` bindings instead
- Do NOT use `ngStyle`, use `style` bindings instead
- When using external templates/styles, use paths relative to the component TS file.

## State Management
- Use signals for local component state
- Use `computed()` for derived state
- Keep state transformations pure and predictable
- Do NOT use `mutate` on signals, use `update` or `set` instead

## Templates
- Keep templates simple and avoid complex logic
- Use native control flow (`@if`, `@for`, `@switch`) instead of `*ngIf`, `*ngFor`, `*ngSwitch`
- Use the async pipe to handle observables
- Do not assume globals like (`new Date()`) are available.

## Services
- Design services around a single responsibility
- Use the `providedIn: 'root'` option for singleton services
- Use the `inject()` function instead of constructor injection

## Styling
- PrimeNG is used for styling components

## Style Guide
- Components should always be created with 3 different files for .ts, .html and .scss
- A feature should be structured with the following folders in src/app/features:
  - components/: contains the components for this feature
  - dto/: contains dto .ts interfaces that are sent to the server (one file for each dto)
  - guards/: route guards belonging to this feature, if it has any
  - models/: contains other .ts files that are used for this feature but not simply network data wrappers
  - services/: the services used for this feature
## Consistency and reuse
The same problem gets the same building block everywhere. Before writing a spinner, a
table, a filter or a dialog, use the shared one; when something is needed a second
time, extract it into `core/` (or the feature's `components/`/`models/`) instead of
copying it, the way the board face is shared by the live board, the replay and the
heatmaps.

- **Loading a view:** `app-loading-state` (skeletons only as listed under deviations).
- **Errors:** each error shows once, next to what caused it.
  - Invalid input: `app-field-error` directly under its input, inside the same table
    row or list row for inline edits, never below the whole list.
  - A request a form or inline edit sent: `p-message severity="error"` right under that
    form or row, worded with `httpErrorMessage()`.
  - A view that failed to load: `app-load-error` with a retry.
  - Anything else: the toast from the error interceptor.
  - Wherever the view shows the error itself, the service call passes
    `SILENT_ERROR_CONTEXT`, so no toast repeats it.
- **Nothing to show:** `app-empty-state`, inside tables too (`#emptymessage`).
- **Tables:** every list of records is a `p-table` with `class="data-table"` and
  `size="small"`. Rows are compact and cells are centred; use `data-table__number`,
  `data-table__actions`, `data-table__hint` and `data-table__link` (rows that open a
  record), statuses as `p-tag`, and `app-loading-state` in `#loadingicon`. Spacing,
  tag and button sizes come from the `.data-table` tokens in `styles.scss`, not from
  the component.
- **Paging:** lists that come from the server are paged on the server through
  `PagedTable` (`core/view/models/paged-table.ts`) and `PAGE_SIZE`. The endpoint takes
  `limit`, `offset` and its filters and returns `{ items, total }`. The paginator is
  shown whenever there are results and reports the range and the total
  (`PagedTable.pageReport`) centred below the page links; there is no separate count
  above the table.
- **Search and filters:** `app-list-toolbar`. Filter fields are projected into its
  popover with the `list-filters` classes; active filters show as `FilterChip`s.
- **Dialogs:** destructive actions ask through `ConfirmService.ask()`; the one
  `p-confirmdialog` lives in the app shell. Other dialogs use `DIALOG_STYLE`.
- **Colours:** theme tokens (`var(--p-…)`) without hex fallbacks. Hardcoded colours
  only where the theme has none, such as the board or overlays on the camera picture.
- **Bundle budget:** the limits in `angular.json` are a rough guard. Raise them when a
  sensible change needs it rather than deferring code just to stay under them.

### Deliberate deviations
These differ from the rules above on purpose; a refactor must keep them.

- **Player names start left:** the name column of the player list and of the links
  tab uses `data-table__start`, because names of different length read badly centred.
- **Figure labels start left:** the row labels of the per-player figures in the game
  detail (`figures__label`) stay left of the centred values.
- **Actions end right:** `data-table__actions` keeps the buttons at the row's end.
- **Skeletons while playing:** the running game and the new-game view load behind
  `p-skeleton` instead of `app-loading-state`, so the layout does not jump.
