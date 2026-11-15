import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, model, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SelectButton } from 'primeng/selectbutton';
import {
  HeatBoardComponent,
  HeatField,
} from '../../../game/components/heat-board/heat-board.component';
import {
  HeatmapPick,
  TipHeatmapComponent,
} from '../../../game/components/tip-heatmap/tip-heatmap.component';
import { SECTOR_ORDER } from '../../../game/models/board-geometry';
import { fieldName, parseField } from '../../../game/models/field-label';
import {
  HEATMAP_LAYERS,
  HeatmapLayer,
  storeHeatmapLayer,
  storedHeatmapLayer,
} from '../../../game/models/heatmap-layer';
import { MISS, heatFields, mostOnBoard } from '../../../game/models/heat-fields';
import { TipPoint } from '../../../game/models/tip-density';
import { FieldTallyDto } from '../../dto/field-tally.dto';
import { targetAt, targetKey, targetLabel, targetOutline } from '../../models/statistics-game';

/** The aims a board shows: targets of a game, or the doubles a checkout went for. */
export type TargetBoardKind = 'targets' | 'doubles';

/** Half the drawn area in board mm, with a margin for the misses; wider at the doubles. */
const VIEW_EXTENT: Record<TargetBoardKind, number> = { targets: 230, doubles: 260 };

const LAYER_LABELS: Record<TargetBoardKind, string> = {
  targets: $localize`:@@stats.targets.layer:Darstellung der Ziele`,
  doubles: $localize`:@@stats.doublesLayer:Darstellung der Doppel`,
};

const BOARD_LABELS: Record<TargetBoardKind, string> = {
  targets: $localize`:@@stats.targets.boardLabel:Darts auf Ziele nach getroffenem Feld`,
  doubles: $localize`:@@stats.doubles.label:Checkout-Darts nach getroffenem Feld`,
};

/** The darts thrown at targets, as a tip cloud or as the fields they hit. A tap on a field
 * picks the target aimed at there and narrows both to the darts at it. */
@Component({
  selector: 'app-target-board',
  imports: [DecimalPipe, FormsModule, HeatBoardComponent, SelectButton, TipHeatmapComponent],
  templateUrl: './target-board.component.html',
  styleUrl: './target-board.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TargetBoardComponent {
  readonly targets = input.required<readonly FieldTallyDto[]>();
  readonly kind = input<TargetBoardKind>('targets');
  /** Key of the picked target, see `targetKey`. */
  readonly selected = model<string | null>(null);
  readonly layer = model<HeatmapLayer>(storedHeatmapLayer());
  /** Whether the board offers its own layer switch; two side by side share one above them. */
  readonly layerSwitch = input(true);

  protected readonly hovered = signal<string | null>(null);
  protected readonly layerOptions = [...HEATMAP_LAYERS];
  protected readonly extent = computed(() => VIEW_EXTENT[this.kind()]);
  protected readonly layerLabel = computed(() => LAYER_LABELS[this.kind()]);
  protected readonly boardLabel = computed(() => BOARD_LABELS[this.kind()]);
  protected readonly outlineOf = targetOutline;

  private readonly keyed = computed(
    () => new Map(this.targets().map((target) => [targetKey(target), target])),
  );

  /** The target a tap on the field `label` picks: its sector's double on a doubles board,
   * else the target aimed there or the field itself; null off the board. */
  protected readonly resolve = (label: string): string | null => {
    const field = parseField(label);
    if (field === null) {
      return null;
    }
    if (this.kind() === 'doubles') {
      return 'index' in field ? `D${SECTOR_ORDER[field.index]}` : '50';
    }
    return targetAt(label, new Set(this.keyed().keys())) ?? label;
  };

  private readonly picked = computed(() => {
    const key = this.selected();
    return key === null ? null : (this.keyed().get(key) ?? null);
  });

  /** The picked target, none for a field nobody aimed at, or every target without a pick. */
  private readonly shownTargets = computed(() => {
    const picked = this.picked();
    return picked ? [picked] : this.selected() === null ? this.targets() : [];
  });

  protected readonly darts = computed(() =>
    this.targets().reduce((sum, target) => sum + target.darts, 0),
  );

  /** What the darts at the picked target hit, or at every target without a pick. */
  private readonly scored = computed(() => {
    const counts = new Map<string, number>();
    for (const target of this.shownTargets()) {
      for (const [label, count] of Object.entries(target.fields)) {
        counts.set(label, (counts.get(label) ?? 0) + count);
      }
    }
    return counts;
  });

  protected readonly misses = computed(() => this.scored().get(MISS) ?? 0);

  private readonly most = computed(() => mostOnBoard(this.scored()));

  protected readonly fields = computed<HeatField[]>(() => heatFields(this.scored(), this.most()));

  protected readonly legendMax = computed(() => `${this.most()}`);

  protected readonly tips = computed<TipPoint[]>(() =>
    this.shownTargets().flatMap((target) => target.cells),
  );

  /** Every target as a tap target over the cloud, whole numbers first so a ring lies on top. */
  protected readonly overlay = computed(() =>
    [...this.keyed()]
      .sort(([, a], [, b]) => Number(a.multiplier !== null) - Number(b.multiplier !== null))
      .map(([key, target]) => ({
        key,
        d: targetOutline(key) ?? '',
        ariaLabel:
          this.kind() === 'doubles'
            ? $localize`:@@stats.doubles.hitRate:${targetLabel(target)}:field:: ${target.hits}:hits: von ${target.darts}:attempts: getroffen`
            : $localize`:@@stats.targets.hitRate:${targetLabel(target)}:field:: ${target.hits}:hits: von ${target.darts}:darts: getroffen`,
      })),
  );

  protected readonly outline = computed(() => {
    const key = this.hovered() ?? this.selected();
    return key === null ? null : targetOutline(key);
  });

  /** The target under the pointer or picked, with its rate over every dart thrown at it; a
   * field nobody aimed at has none. */
  protected readonly shown = computed(() => {
    const key = this.hovered() ?? this.selected();
    if (key === null) {
      return null;
    }
    const target = this.keyed().get(key);
    return target
      ? { ...target, name: targetLabel(target), rate: target.hits / target.darts }
      : { hits: 0, darts: 0, located: 0, locatedHits: 0, name: fieldName(key), rate: null };
  });

  /** The same target on the cloud, its rate over the darts that were located. */
  protected readonly tipPick = computed<HeatmapPick | null>(() => {
    const target = this.shown();
    if (target === null) {
      return null;
    }
    const { located, locatedHits: hits } = target;
    const rate = Math.round((hits / Math.max(1, located)) * 100);
    return {
      name: target.name,
      detail: located === 0 ? $localize`:@@game.heatmap.noHits:keine Treffer` : `${hits} / ${located} (${rate} %)`,
    };
  });

  protected selectLayer(layer: HeatmapLayer): void {
    this.layer.set(layer);
    storeHeatmapLayer(layer);
  }

  protected toggle(key: string, event: Event): void {
    event.stopPropagation();
    event.preventDefault();
    this.selected.update((picked) => (picked === key ? null : key));
  }

  /** A tap on a field picks its target; a second tap or one off the targets clears it. */
  protected pickSegment(event: MouseEvent): void {
    const label = (event.target as Element).getAttribute('data-label');
    const key = label === null ? null : this.resolve(label);
    this.selected.update((picked) => (key === null || key === picked ? null : key));
  }

  protected onTargetEnter(key: string, event: PointerEvent): void {
    if (event.pointerType === 'mouse') {
      this.hovered.set(key);
    }
  }
}
