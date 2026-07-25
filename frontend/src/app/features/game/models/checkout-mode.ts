// How a leg may be finished. Double-out requires the finishing dart to land in a
// double (the bullseye counts); single-out finishes on any field. The string
// values match the backend CheckoutMode enum sent over the wire.
export type CheckoutMode = 'single_out' | 'double_out';

export const CHECKOUT_MODES: readonly { label: string; value: CheckoutMode }[] = [
  { label: 'Single Out', value: 'single_out' },
  { label: 'Double Out', value: 'double_out' },
];
