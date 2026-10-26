import { DartAnnouncementDto } from '../dto/dart-announcement.dto';
import { TurnAnnouncementDto } from '../dto/turn-announcement.dto';

/** The phrases to speak for one booked dart, in order. */
export function announcementPhrases(announcement: DartAnnouncementDto): string[] {
  const phrases = [dartPhrase(announcement.value, announcement.multiplier)];

  if (announcement.won) {
    phrases.push('Game shot');
  } else if (announcement.busted) {
    phrases.push('Bust');
  } else if (announcement.visitPoints !== null) {
    phrases.push(String(announcement.visitPoints));
  }
  return phrases;
}

/** The phrase that calls the next player to the oche. */
export function turnPhrase(announcement: TurnAnnouncementDto): string {
  const { player, remaining } = announcement;
  return remaining === null ? player : `${player}, ${remaining}`;
}

function dartPhrase(value: number, multiplier: number): string {
  if (multiplier === 0) {
    return 'Miss';
  }
  if (value === 25) {
    return multiplier === 2 ? 'Double Bull' : 'Bull';
  }
  return `${['Single', 'Double', 'Triple'][multiplier - 1]} ${value}`;
}
