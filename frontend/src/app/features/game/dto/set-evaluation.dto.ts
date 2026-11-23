/** Client -> server: keep this game's camera frames, or stop and delete them. */
export interface SetEvaluationDto {
  readonly type: 'set_evaluation';
  readonly enabled: boolean;
}
