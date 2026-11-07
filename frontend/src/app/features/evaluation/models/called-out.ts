/** A detection label (S20, BULL, MISS) as the board names its fields (20, 50, 0). */
export function calledOut(label: string): string {
  if (label === 'MISS') {
    return '0';
  }
  if (label === 'BULL') {
    return '50';
  }
  return label.startsWith('S') ? label.slice(1) : label;
}
