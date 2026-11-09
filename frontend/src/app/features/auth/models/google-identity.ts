/** The part of Google Identity Services' `google.accounts.id` the app uses. */
export interface GoogleAccountsId {
  initialize(config: {
    client_id: string;
    callback: (response: { credential: string }) => void;
    auto_select?: boolean;
  }): void;
  renderButton(parent: HTMLElement, options: GoogleButtonOptions): void;
}

export type GoogleButtonText = 'signin_with' | 'signup_with' | 'continue_with';

export interface GoogleButtonOptions {
  readonly type: 'standard';
  readonly theme: 'outline' | 'filled_black';
  readonly size: 'large';
  readonly text: GoogleButtonText;
  readonly shape: 'rectangular' | 'pill';
  readonly width: number;
  readonly locale: string;
}

export interface GoogleWindow {
  readonly google?: { readonly accounts: { readonly id: GoogleAccountsId } };
}
