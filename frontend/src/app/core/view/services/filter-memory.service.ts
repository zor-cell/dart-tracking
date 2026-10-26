import { HttpClient } from '@angular/common/http';
import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormGroup } from '@angular/forms';
import { firstValueFrom, map, pairwise, startWith } from 'rxjs';
import { SILENT_ERROR_CONTEXT } from '../../interceptors';
import { environment } from '../../../../environments/environment';
import { FilterUsageDto, FilterUseDto } from '../dto/filter-usage.dto';
import { FilterSuggestion } from '../models/filter-chip';

/** Days after which a pick weighs half. */
const HALF_LIFE_DAYS = 30;
/** Weight a pick needs before it is offered: two recent uses, while one alone stays below. */
const MIN_SCORE = 1.5;
/** Picks kept per account; the weakest beyond are dropped. */
const MAX_USES = 50;
const DAY_MS = 24 * 60 * 60 * 1000;

/** Remembers on the server which filters the account picks in each list, and turns
 * them into the suggestions beside the active filters. */
@Injectable({ providedIn: 'root' })
export class FilterMemoryService {
  private readonly http = inject(HttpClient);
  private readonly url = `${environment.httpApiUrl}/settings/filter-usage`;
  private readonly uses = signal<readonly FilterUseDto[]>([]);

  /** Fetch the account's picks; on a failure the suggestions fall back to the defaults. */
  async load(): Promise<void> {
    try {
      const usage = await firstValueFrom(
        this.http.get<FilterUsageDto>(this.url, { context: SILENT_ERROR_CONTEXT }),
      );
      this.uses.set(usage.uses);
    } catch {
      this.uses.set([]);
    }
  }

  /** Remember each of `keys` in `form` whenever it is set to a value; clearing is no pick. */
  watch(view: string, form: FormGroup, keys: readonly string[], destroyRef: DestroyRef): void {
    form.valueChanges
      .pipe(
        map(() => form.getRawValue() as Record<string, unknown>),
        startWith(form.getRawValue() as Record<string, unknown>),
        pairwise(),
        takeUntilDestroyed(destroyRef),
      )
      .subscribe(([before, after]) => {
        for (const key of keys) {
          const value = after[key];
          if (value !== null && value !== undefined && value !== before[key]) {
            this.remember(view, key, value);
          }
        }
      });
  }

  /**
   * Up to `count` filters to offer: the account's own strong picks first, then the
   * `defaults`; only those `label` can name and `open` still allows.
   */
  suggest(
    view: string,
    defaults: readonly FilterSuggestion[],
    label: (key: string, value: unknown) => string | null,
    open: (key: string) => boolean,
    count = 2,
  ): FilterSuggestion[] {
    const now = Date.now();
    const learned = this.uses()
      .filter((use) => use.view === view && faded(use, now) >= MIN_SCORE)
      .sort((a, b) => faded(b, now) - faded(a, now))
      .flatMap((use) => {
        const value = parse(use.value);
        const name = value === undefined ? null : label(use.key, value);
        return name === null ? [] : [{ key: use.key, label: name, value }];
      });

    const picked: FilterSuggestion[] = [];
    for (const suggestion of [...learned, ...defaults]) {
      const taken = picked.some((p) => p.key === suggestion.key && p.value === suggestion.value);
      if (picked.length < count && open(suggestion.key) && !taken) {
        picked.push(suggestion);
      }
    }
    return picked;
  }

  /** Count one pick: its weight fades to now and gains one. */
  private remember(view: string, key: string, value: unknown): void {
    const now = Date.now();
    const encoded = JSON.stringify(value);
    const same = (use: FilterUseDto) =>
      use.view === view && use.key === key && use.value === encoded;
    const previous = this.uses().find(same);
    const use: FilterUseDto = {
      view,
      key,
      value: encoded,
      score: (previous ? faded(previous, now) : 0) + 1,
      lastUsedAt: new Date(now).toISOString(),
    };
    const uses = [use, ...this.uses().filter((other) => !same(other))]
      .sort((a, b) => faded(b, now) - faded(a, now))
      .slice(0, MAX_USES);
    this.uses.set(uses);
    firstValueFrom(
      this.http.put<void>(this.url, { uses }, { context: SILENT_ERROR_CONTEXT }),
    ).catch(() => {});
  }
}

/** A pick's weight as of `now`, halving every `HALF_LIFE_DAYS`. */
function faded(use: FilterUseDto, now: number): number {
  const days = Math.max(0, now - Date.parse(use.lastUsedAt)) / DAY_MS;
  return use.score * 0.5 ** (days / HALF_LIFE_DAYS);
}

/** The stored value, or undefined for one this client cannot read. */
function parse(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return undefined;
  }
}
