import {
  LineDraft,
  BoxDraft,
  MAX_BOXES,
  MAX_SEGMENTS,
  MIN_SEGMENTS,
} from "./types";
import { normalizeDecimal } from "./decimal";

let idSeq = 0;
export function nextRowKey(): number {
  idSeq += 1;
  return idSeq;
}

export function emptyBox(): BoxDraft {
  return { id: "", correction: "0", loss: "0" };
}

export function emptyLine(n: number): LineDraft {
  const count = Math.min(Math.max(n, MIN_SEGMENTS), MAX_SEGMENTS);
  return {
    segments: Array.from({ length: count }, () => ({ increment: "0" })),
    stations: Array.from({ length: count }, () => ({
      lower: "0",
      upper: "0",
      boxes: [],
    })),
  };
}

export function exampleLine(): LineDraft {
  return {
    segments: [
      { increment: "3.200" },
      { increment: "-1.500" },
      { increment: "2.100" },
      { increment: "-0.800" },
    ],
    stations: [
      {
        lower: "0",
        upper: "6",
        boxes: [
          { id: "A1", correction: "0.500", loss: "1.200" },
          { id: "A2", correction: "-1.000", loss: "0.800" },
        ],
      },
      {
        lower: "0",
        upper: "5",
        boxes: [
          { id: "B1", correction: "1.000", loss: "0.500" },
          { id: "B2", correction: "-0.500", loss: "0.300" },
        ],
      },
      {
        lower: "1",
        upper: "6",
        boxes: [
          { id: "C1", correction: "-2.000", loss: "1.000" },
          { id: "C2", correction: "0.500", loss: "0.200" },
        ],
      },
      {
        lower: "0",
        upper: "4",
        boxes: [
          { id: "D1", correction: "-1.200", loss: "0.400" },
          { id: "D2", correction: "0.800", loss: "0.900" },
        ],
      },
    ],
  };
}

/** 客户端即时检查；服务端仍做最终精确定位校验。返回 field -> 提示。 */
export function clientChecks(line: LineDraft): Map<string, string> {
  const errs = new Map<string, string>();
  const num = (raw: string) => normalizeDecimal(raw);
  line.segments.forEach((seg, i) => {
    if (num(seg.increment) === null)
      errs.set(`segments[${i}].increment`, "需为最多三位小数");
  });
  line.stations.forEach((st, i) => {
    const lo = num(st.lower);
    const hi = num(st.upper);
    if (lo === null) errs.set(`stations[${i}].lower`, "需为最多三位小数");
    if (hi === null) errs.set(`stations[${i}].upper`, "需为最多三位小数");
    const seen = new Set<string>();
    st.boxes.forEach((b, j) => {
      const base = `stations[${i}].boxes[${j}]`;
      if (!b.id.trim()) errs.set(`${base}.id`, "编号不能为空");
      else if (seen.has(b.id)) errs.set(`${base}.id`, "本站编号重复");
      seen.add(b.id);
      if (num(b.correction) === null)
        errs.set(`${base}.correction`, "需为最多三位小数");
      const loss = num(b.loss);
      if (loss === null) errs.set(`${base}.loss`, "需为最多三位小数");
      else if (loss.startsWith("-")) errs.set(`${base}.loss`, "插损必须非负");
    });
  });
  return errs;
}

/** 导入 JSON 文本（数值或字符串均可），失败抛出带信息的 Error。 */
export function importLine(text: string): LineDraft {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (e) {
    throw new Error(`JSON 解析失败：${(e as Error).message}`);
  }
  const obj = data as Record<string, unknown>;
  if (!obj || typeof obj !== "object" || Array.isArray(obj))
    throw new Error("顶层必须是 JSON 对象");
  const segs = obj.segments;
  const stats = obj.stations;
  if (!Array.isArray(segs) || !Array.isArray(stats))
    throw new Error("必须含 segments 与 stations 两个数组");
  if (segs.length !== stats.length)
    throw new Error(
      `段数(${segs.length}) 与站点数(${stats.length}) 必须相等`
    );
  if (segs.length < MIN_SEGMENTS || segs.length > MAX_SEGMENTS)
    throw new Error(`段数必须在 ${MIN_SEGMENTS}–${MAX_SEGMENTS} 之间`);

  const asStr = (v: unknown): string => {
    if (typeof v === "string") return v;
    if (typeof v === "number" && Number.isFinite(v)) return String(v);
    throw new Error("数值字段必须是数字或字符串");
  };

  const line: LineDraft = { segments: [], stations: [] };
  segs.forEach((s, i) => {
    const seg = s as Record<string, unknown>;
    if (!seg || typeof seg !== "object")
      throw new Error(`segments[${i}] 必须是对象`);
    line.segments.push({ increment: asStr(seg.increment) });
  });
  stats.forEach((s, i) => {
    const st = s as Record<string, unknown>;
    if (!st || typeof st !== "object")
      throw new Error(`stations[${i}] 必须是对象`);
    const boxesRaw = Array.isArray(st.boxes) ? st.boxes : [];
    if (boxesRaw.length > MAX_BOXES)
      throw new Error(`stations[${i}] 候选盒超过 ${MAX_BOXES} 个`);
    const boxes: BoxDraft[] = boxesRaw.map((b, j) => {
      const box = b as Record<string, unknown>;
      if (!box || typeof box !== "object")
        throw new Error(`stations[${i}].boxes[${j}] 必须是对象`);
      if (typeof box.id !== "string" || !box.id.trim())
        throw new Error(`stations[${i}].boxes[${j}].id 必须是非空字符串`);
      return {
        id: box.id,
        correction: asStr(box.correction),
        loss: asStr(box.loss),
      };
    });
    line.stations.push({
      lower: asStr(st.lower),
      upper: asStr(st.upper),
      boxes,
    });
  });
  return line;
}

/** 导出为 JSON 文本：数值一律用字符串，彻底规避浮点。 */
export function exportLine(line: LineDraft): string {
  return JSON.stringify(line, null, 2);
}
