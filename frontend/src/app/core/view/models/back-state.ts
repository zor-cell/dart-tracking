/** Router state a link passes so the view it opens leads back to the page it came from. */
export interface BackState {
  /** How the back link names that page. */
  readonly back: string;
}

export function backState(label: string): BackState {
  return { back: label };
}

/** The page to return to, named, when the view was opened with `backState`; else null. */
export function backLabel(state: unknown): string | null {
  const back = (state as Partial<BackState> | null)?.back;
  return typeof back === 'string' ? back : null;
}
