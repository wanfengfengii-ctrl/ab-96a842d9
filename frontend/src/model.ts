import type { SolveRequest } from "./types";

export interface BoxDraft {
  id: string;
  correction: string;
  loss: string;
}

export interface StationDraft {
  increment: string;
  lower: string;
  upper: string;
  boxes: BoxDraft[];
}

export function emptyStation(boxCount = 0): StationDraft {
  return {
    increment: "0",
    lower: "0",
    upper: "0",
    boxes: Array.from({ length: boxCount }, () => ({
      id: "",
      correction: "0",
      loss: "0",
    })),
  };
}

export function sampleLine(): StationDraft[] {
  // A hand-built line where greedy "zeroing at every station" fails but the
  // global DP finds a feasible plan.
  return [
    {
      increment: "6",
      lower: "0",
      upper: "8",
      boxes: [{ id: "1", correction: "-3", loss: "0.5" }],
    },
    {
      increment: "5",
      lower: "0",
      upper: "6",
      boxes: [
        { id: "1", correction: "-4", loss: "0.2" },
        { id: "2", correction: "-8", loss: "0.9" },
      ],
    },
    {
      increment: "7",
      lower: "0",
      upper: "5",
      boxes: [
        { id: "1", correction: "-6", loss: "0.3" },
        { id: "2", correction: "-9", loss: "1.1" },
      ],
    },
  ];
}

export function draftsToPayload(
  stations: StationDraft[]
): SolveRequest {
  const norm = (s: string): string => (s.trim() === "" ? "0" : s.trim());
  return {
    stations: stations.map((st) => ({
      increment: norm(st.increment),
      lower: norm(st.lower),
      upper: norm(st.upper),
      boxes: st.boxes.map((b) => ({
        id: Number(b.id),
        correction: norm(b.correction),
        loss: norm(b.loss),
      })),
    })),
  };
}

export function payloadToDrafts(payload: unknown): StationDraft[] {
  if (
    typeof payload !== "object" ||
    payload === null ||
    !("stations" in payload)
  ) {
    throw new Error("JSON 顶层必须是包含 stations 数组的对象");
  }
  const stations = (payload as { stations: unknown[] }).stations;
  if (!Array.isArray(stations)) {
    throw new Error("stations 必须是数组");
  }
  return stations.map((raw) => {
    if (typeof raw !== "object" || raw === null) {
      throw new Error("每个站点必须是对象");
    }
    const st = raw as Record<string, unknown>;
    const boxesRaw = Array.isArray(st.boxes) ? st.boxes : [];
    return {
      increment: String(st.increment ?? "0"),
      lower: String(st.lower ?? "0"),
      upper: String(st.upper ?? "0"),
      boxes: boxesRaw.map((b) => {
        const box = (b ?? {}) as Record<string, unknown>;
        return {
          id: box.id === undefined ? "" : String(box.id),
          correction: String(box.correction ?? "0"),
          loss: String(box.loss ?? "0"),
        };
      }),
    };
  });
}
