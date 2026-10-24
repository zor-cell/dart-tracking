/** Whether an entry is linked to another account. */
export type LinkState = 'linked' | 'unlinked';

export const LINK_STATE_LABELS: Record<LinkState, string> = {
  linked: 'Verknüpft',
  unlinked: 'Nicht verknüpft',
};

/** Narrows the player list; a null field leaves it open. */
export interface PlayerFilter {
  readonly query: string | null;
  readonly linked: LinkState | null;
}
