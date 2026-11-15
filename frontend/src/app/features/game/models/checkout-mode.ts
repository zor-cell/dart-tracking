// How a leg may be finished: on any field or on a double, Bull included; the
// values match the backend's CheckoutMode.
export type CheckoutMode = 'single_out' | 'double_out';

export const CHECKOUT_MODES: readonly { label: string; value: CheckoutMode }[] = [
  { label: 'Single Out', value: 'single_out' },
  { label: 'Double Out', value: 'double_out' },
];
