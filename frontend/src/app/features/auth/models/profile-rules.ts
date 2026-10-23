/** The name constraints, mirrored from the server's `ProfileDto` so a value it
 * would reject is caught in the form. Used by registration and by the account
 * page, which write the same two fields. */
export const USERNAME_PATTERN = /^[A-Za-z0-9_.-]+$/;
export const USERNAME_MIN_LENGTH = 3;
export const USERNAME_MAX_LENGTH = 32;
export const DISPLAY_NAME_MAX_LENGTH = 64;

/** Field error for a username that breaks `USERNAME_PATTERN`. */
export const USERNAME_MESSAGES = {
  pattern: 'Nur Buchstaben, Ziffern, Punkt, Bindestrich oder Unterstrich.',
};
