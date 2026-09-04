/** One seat in a new game: either a known identity or a name typed for a guest. */
export type PlayerSlotDto = { readonly playerId: string } | { readonly name: string };
