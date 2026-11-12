import { Injectable } from '@angular/core';
import { readStored, writeStored } from '../../../core/storage/models/browser-storage';
import { GameDraft } from '../models/game-draft';

const DRAFT_KEY = 'dart-tracking.game-draft';

/** The new game being set up, kept for this tab so leaving the page does not lose it. */
@Injectable({ providedIn: 'root' })
export class GameDraftService {
  /** The draft left by `account` (null when signed out), or null without one. */
  read(account: string | null): GameDraft | null {
    try {
      const draft = JSON.parse(readStored(DRAFT_KEY, 'session') ?? 'null') as GameDraft | null;
      return draft !== null && draft.account === account ? draft : null;
    } catch {
      return null;
    }
  }

  save(draft: GameDraft): void {
    writeStored(DRAFT_KEY, JSON.stringify(draft), 'session');
  }

  clear(): void {
    writeStored(DRAFT_KEY, null, 'session');
  }
}
