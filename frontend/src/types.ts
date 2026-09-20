// API contract shared with the FastAPI backend.

export interface CandidateBoxInput {
  id: number;
  correction: number | string;
  loss: number | string;
}

export interface StationInput {
  increment: number | string;
  lower: number | string;
  upper: number | string;
  boxes: CandidateBoxInput[];
}

export interface SolveRequest {
  stations: StationInput[];
}

export interface ValidationErrorItem {
  station: number | null;
  field: string;
  message: string;
}

export interface StationChoice {
  station: number;
  installed: boolean;
  box_id: number | null;
}

export interface SolveSummary {
  installed_count: number;
  total_insertion_loss_milli_db: number;
  final_abs_residual_milli: number;
  tie: boolean;
}

export interface OptimalResponse {
  status: "optimal";
  stations: StationChoice[];
  // One witness, or the first two lexicographic witnesses on a tie.
  witnesses: (number | null)[][];
  summary: SolveSummary;
}

export interface InfeasibleResponse {
  status: "infeasible";
  failed_station: number;
  reachable_count: number;
  message: string;
}

export interface InvalidResponse {
  status: "invalid";
  errors: ValidationErrorItem[];
}

export type SolveResponse =
  | OptimalResponse
  | InfeasibleResponse
  | InvalidResponse;

// ---- Client-side exact validation mirror (used for instant field marks) ----

const DECIMAL_RE = /^-?(?:\d+(?:\.\d{0,3})?|\.\d{1,3})$/;

export interface LocalFieldError {
  station: number; // 1-based
  field: string;
  message: string;
}

export function validateRequest(
  req: SolveRequest
): LocalFieldError[] {
  const errors: LocalFieldError[] = [];
  const n = req.stations.length;
  if (n < 2) {
    errors.push({
      station: 0,
      field: "stations",
      message: "线路段数至少为 2",
    });
  }
  if (n > 80) {
    errors.push({
      station: 0,
      field: "stations",
      message: "线路段数至多为 80",
    });
  }

  const checkMilli = (
    station: number,
    field: string,
    raw: string,
    { nonNegative = false }: { nonNegative?: boolean } = {}
  ): number | null => {
    const s = raw.trim();
    if (!DECIMAL_RE.test(s)) {
      errors.push({
        station,
        field,
        message: "必须是数字且至多三位小数",
      });
      return null;
    }
    const neg = s.startsWith("-");
    const [intPart, fracPart = ""] = s.replace("-", "").split(".");
    const milli =
      Number(intPart) * 1000 +
      Number((fracPart + "000").slice(0, 3)) * (neg ? -1 : 1);
    if (milli < -20000 || milli > 20000) {
      errors.push({
        station,
        field,
        message: "缩放后须落在 −20000 至 20000",
      });
      return null;
    }
    if (nonNegative && milli < 0) {
      errors.push({ station, field, message: "不能为负数" });
      return null;
    }
    return milli;
  };

  req.stations.forEach((st, i) => {
    const station = i + 1;
    const incMilli = checkMilli(station, "increment", String(st.increment));
    const loMilli = checkMilli(station, "lower", String(st.lower));
    const hiMilli = checkMilli(station, "upper", String(st.upper));
    if (
      incMilli !== null &&
      loMilli !== null &&
      hiMilli !== null &&
      loMilli > hiMilli
    ) {
      errors.push({
        station,
        field: "lower",
        message: "下界不能大于上界",
      });
    }
    if (st.boxes.length > 12) {
      errors.push({
        station,
        field: "boxes",
        message: "每站候选盒至多 12 个",
      });
    }
    const seen = new Set<number>();
    st.boxes.forEach((b, bi) => {
      const idField = `boxes[${bi}].id`;
      if (!Number.isInteger(b.id) || b.id < 1) {
        errors.push({
          station,
          field: idField,
          message: "编号必须是正整数（从 1 开始）",
        });
      } else if (seen.has(b.id)) {
        errors.push({
          station,
          field: idField,
          message: `编号 ${b.id} 在本站重复`,
        });
      } else {
        seen.add(b.id);
      }
      checkMilli(
        station,
        `boxes[${bi}].correction`,
        String(b.correction)
      );
      checkMilli(station, `boxes[${bi}].loss`, String(b.loss), {
        nonNegative: true,
      });
    });
  });

  return errors;
}

// Convert milli-units back to a three-decimal display string.
export function formatMilli(milli: number): string {
  const sign = milli < 0 ? "-" : "";
  const abs = Math.abs(milli);
  return `${sign}${Math.floor(abs / 1000)}.${String(abs % 1000).padStart(
    3,
    "0"
  )}`;
}
