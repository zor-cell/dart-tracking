import { DartAnnouncementDto } from '../dto/dart-announcement.dto';

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

function dartPhrase(value: number, multiplier: number): string {
  if (multiplier === 0) {
    return 'Daneben';
  }
  if (value === 25) {
    return multiplier === 2 ? 'Bullseye' : 'Bull';
  }
  return `${['Single', 'Double', 'Triple'][multiplier - 1]} ${value}`;
}
