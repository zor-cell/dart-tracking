import { FieldRecordDto } from '../dto/field-record.dto';
import { PlanBlockDto } from '../dto/plan-block.dto';
import { PersonalStandingDto } from '../dto/personal-standing.dto';
import { fieldLabel } from './variant-options';

/** One block of a personal training with its darts today and its fields' record before. */
export interface PersonalBlockRow {
  readonly label: string;
  /** Darts the block plans. */
  readonly planned: number;
  readonly darts: number;
  readonly hits: number;
  /** Hit rate in percent; null before a dart. */
  readonly rate: number | null;
  /** The fields' hit rate before, in percent; null without a record. */
  readonly before: number | null;
}

/** A block named by its field, the closing one as "Gemischt (D16, D8, T19)". */
export function blockLabel(block: PlanBlockDto): string {
  const fields = block.fields.map(fieldLabel);
  return fields.length === 1
    ? fields[0]
    : $localize`:@@game.personal.mixed:Gemischt (${fields.join(', ')}:fields:)`;
}

export function hitRate(hits: number, darts: number): number | null {
  return darts === 0 ? null : (100 * hits) / darts;
}

/** The record before the training over the fields of `block`. */
export function recordBefore(block: PlanBlockDto, baselines: readonly FieldRecordDto[]): number | null {
  const own = baselines.filter((baseline) =>
    block.fields.some((field) => field.value === baseline.value && field.multiplier === baseline.multiplier),
  );
  const darts = own.reduce((sum, baseline) => sum + baseline.darts, 0);
  return hitRate(
    own.reduce((sum, baseline) => sum + baseline.hits, 0),
    darts,
  );
}

/** The seat's blocks in plan order. */
export function personalBlocks(standing: PersonalStandingDto, seat: number): PersonalBlockRow[] {
  const player = standing.players[seat];
  return standing.blocks.map((block, index) => {
    const tally = player.blocks[index];
    return {
      label: block.fields.length === 1 ? fieldLabel(block.fields[0]) : $localize`:@@game.training.mixed:Gemischt`,
      planned: block.darts,
      darts: tally.darts,
      hits: tally.hits,
      rate: hitRate(tally.hits, tally.darts),
      before: recordBefore(block, standing.baselines),
    };
  });
}

/** The field of the player's dart number `dart`, from 0; null past the plan. */
export function plannedField(blocks: readonly PlanBlockDto[], dart: number): PlanBlockDto['fields'][number] | null {
  for (const block of blocks) {
    if (dart < block.darts) {
      return block.fields[dart % block.fields.length];
    }
    dart -= block.darts;
  }
  return null;
}
