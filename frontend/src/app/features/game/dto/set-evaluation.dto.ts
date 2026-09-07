/** Client -> server: mark this game as a tracking test run, or stop. */
export interface SetEvaluationDto {
  readonly type: 'set_evaluation';
  readonly enabled: boolean;
}
