import { Location, formatDate } from '@angular/common';
import { DestroyRef, Injector, WritableSignal, effect, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormGroup } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { DayRange } from './day-range';

/** How one value is written into the query params and read back. */
export interface QueryParam<T> {
  /** The value, or undefined for one that is unknown. */
  parse(raw: string): T | undefined;
  format(value: T): string;
}

/** Any text, such as an id. */
export const TEXT_PARAM: QueryParam<string> = {
  parse: (raw) => raw,
  format: (value) => value,
};

/** One of `values`, written as its text. */
export function oneOfParam<T extends string | number>(values: readonly T[]): QueryParam<T> {
  return {
    parse: (raw) => values.find((value) => `${value}` === raw),
    format: (value) => `${value}`,
  };
}

/** A range of days as `2026-10-01_2026-10-07`, or one day. */
export const DAY_RANGE_PARAM: QueryParam<DayRange> = {
  parse: (raw) => {
    const days = raw.split('_').map(parseDay);
    return days.length > 2 || days.some((day) => day === null)
      ? undefined
      : [days[0], days[1] ?? null];
  },
  format: (range) =>
    (range ?? []).flatMap((day) => (day ? [formatDate(day, 'yyyy-MM-dd', 'en-US')] : [])).join('_'),
};

/**
 * A view's filters kept in its query params, so a reload restores them. Create it in a
 * field initializer and bind before the view loads anything.
 */
export class QueryState {
  private readonly location = inject(Location);
  private readonly router = inject(Router);
  private readonly injector = inject(Injector);
  private readonly destroyRef = inject(DestroyRef);
  private readonly initial = inject(ActivatedRoute).snapshot.queryParamMap;

  /** Restores the controls of `form` named in `params`, then writes each change back. */
  form(form: FormGroup, params: Readonly<Record<string, QueryParam<unknown>>>): void {
    const restored: Record<string, unknown> = {};
    for (const [key, param] of Object.entries(params)) {
      const value = this.read(key, param);
      if (value !== undefined) {
        restored[key] = value;
      }
    }
    form.patchValue(restored);
    form.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      const value = form.getRawValue() as Record<string, unknown>;
      this.write(
        Object.fromEntries(
          Object.entries(params).map(([key, param]) => [key, formatted(param, value[key])]),
        ),
      );
    });
  }

  /** Restores `state` from `key`, then writes it back on every change; `empty` leaves it out. */
  signal<T>(key: string, state: WritableSignal<T>, param: QueryParam<T>, empty: T): void {
    const value = this.read(key, param);
    if (value !== undefined) {
      state.set(value);
    }
    effect(
      () => {
        const current = state();
        this.write({ [key]: current === empty ? null : formatted(param, current) });
      },
      { injector: this.injector },
    );
  }

  private read<T>(key: string, param: QueryParam<T>): T | undefined {
    const raw = this.initial.get(key);
    return raw === null ? undefined : param.parse(raw);
  }

  /** Replaces the URL in place: no navigation, no history entry. */
  private write(changes: Record<string, string | null>): void {
    const tree = this.router.parseUrl(this.location.path());
    const query = { ...tree.queryParams };
    for (const [key, value] of Object.entries(changes)) {
      if (value === null) {
        delete query[key];
      } else {
        query[key] = value;
      }
    }
    tree.queryParams = query;
    // Keeps the history state, which can tell the view where its back link leads.
    this.location.replaceState(this.router.serializeUrl(tree), '', this.location.getState());
  }
}

function formatted<T>(param: QueryParam<T>, value: T | null | undefined): string | null {
  const text = value === null || value === undefined ? '' : param.format(value);
  return text === '' ? null : text;
}

/** A `yyyy-MM-dd` day at local midnight, or null for anything else. */
function parseDay(raw: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
  if (match === null) {
    return null;
  }
  const day = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isNaN(day.getTime()) ? null : day;
}
