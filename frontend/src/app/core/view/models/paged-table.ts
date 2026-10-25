import { signal } from '@angular/core';
import { TableLazyLoadEvent } from 'primeng/table';
import { PAGE_SIZE } from './page-size';

/** How long a reload runs before the table shows its spinner, in ms. */
const SPINNER_DELAY = 250;

/** One page of a server-side list, and how many entries match across all pages. */
export interface Page<T> {
  readonly items: readonly T[];
  readonly total: number;
}

/** The state behind a server-paged p-table; `fetch` asks the server for one page. */
export class PagedTable<T> {
  readonly items = signal<T[]>([]);
  readonly total = signal(0);
  readonly first = signal(0);
  /** A reload that has run longer than `SPINNER_DELAY`. */
  readonly loading = signal(false);
  readonly failed = signal(false);
  /** Whether a page has arrived; until then the view shows its loading state. */
  readonly loaded = signal(false);
  readonly pageSize = PAGE_SIZE;
  /** The paginator's note on which entries are shown, out of how many. */
  readonly pageReport = '{first}–{last} von {totalRecords}';

  /** Bumped per load, so a slow answer to an older page or filter is dropped. */
  private generation = 0;
  private spinner?: ReturnType<typeof setTimeout>;

  constructor(private readonly fetch: (limit: number, offset: number) => Promise<Page<T>>) {}

  onLazyLoad(event: TableLazyLoadEvent): void {
    this.first.set(event.first ?? 0);
    void this.load();
  }

  /** Back to the first page, for when the filter changed. */
  restart(): void {
    this.first.set(0);
    void this.load();
  }

  /** Fetches the current page again, one page back if it has run empty. */
  async load(): Promise<void> {
    const generation = ++this.generation;
    clearTimeout(this.spinner);
    this.spinner = setTimeout(() => this.loading.set(true), SPINNER_DELAY);
    this.failed.set(false);
    try {
      const page = await this.fetch(this.pageSize, this.first());
      if (generation !== this.generation) {
        return;
      }
      if (page.items.length === 0 && this.first() > 0) {
        this.first.set(Math.max(0, this.first() - this.pageSize));
        await this.load();
        return;
      }
      this.items.set([...page.items]);
      this.total.set(page.total);
      this.loaded.set(true);
    } catch {
      if (generation === this.generation) {
        this.failed.set(true);
      }
    } finally {
      if (generation === this.generation) {
        clearTimeout(this.spinner);
        this.loading.set(false);
      }
    }
  }
}
