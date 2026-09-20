/** 领域类型与 API 载荷定义。数值在 UI 中以字符串保存，避免二进制浮点。 */

export interface BoxDraft {
  id: string;
  correction: string;
  loss: string;
}

export interface SegmentDraft {
  increment: string;
}

export interface StationDraft {
  lower: string;
  upper: string;
  boxes: BoxDraft[];
}

export interface LineDraft {
  segments: SegmentDraft[];
  stations: StationDraft[];
}

export interface ChosenBox {
  id: string;
  correction: number; // 缩放后的整数
  loss: number;
}

export interface WitnessStep {
  station: number;
  choice: ChosenBox | null;
  cumulative: number;
}

export interface Witness {
  sequence: WitnessStep[];
}

export interface Objective {
  boxes_installed: number;
  total_loss: number;
  final_abs_residual: number;
}

export type SolveResponse =
  | {
      status: "optimal";
      infeasible_station: null;
      objective: Objective;
      witnesses: Witness[];
      unique: boolean;
    }
  | {
      status: "infeasible";
      infeasible_station: number;
      objective: null;
      witnesses: [];
    };

export interface FieldError {
  field: string;
  message: string;
}

export type ApiResponse =
  | SolveResponse
  | { status: "invalid"; errors: FieldError[] };

export const MIN_SEGMENTS = 2;
export const MAX_SEGMENTS = 80;
export const MAX_BOXES = 12;
export const SCALED_MIN = -20000;
export const SCALED_MAX = 20000;
