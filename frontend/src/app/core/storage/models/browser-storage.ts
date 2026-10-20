/** Which of the browser's stores a value lives in: across sessions, or this tab's only. */
export type StorageArea = 'local' | 'session';

function area(name: StorageArea): Storage {
  return name === 'local' ? localStorage : sessionStorage;
}

/** The value under `key`, or null when there is none or storage is unavailable (private mode). */
export function readStored(key: string, from: StorageArea = 'local'): string | null {
  try {
    return area(from).getItem(key);
  } catch {
    return null;
  }
}

/** Keep `value` under `key`, or drop the key for null; silently a no-op when storage is unavailable. */
export function writeStored(key: string, value: string | null, to: StorageArea = 'local'): void {
  try {
    if (value === null) {
      area(to).removeItem(key);
    } else {
      area(to).setItem(key, value);
    }
  } catch {
    // Without storage the value lasts this page load only.
  }
}
