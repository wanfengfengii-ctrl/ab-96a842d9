import { useMemo, useRef, useState } from "react";
import { StationEditor } from "./components/StationEditor";
import {
  OptimalResult,
  InfeasibleResult,
  InvalidResult,
} from "./components/Results";
import {
  emptyStation,
  sampleLine,
  draftsToPayload,
  payloadToDrafts,
  type StationDraft,
} from "./model";
import {
  validateRequest,
  type LocalFieldError,
  type SolveResponse,
} from "./types";

type Result =
  | { kind: "optimal"; data: Extract<SolveResponse, { status: "optimal" }> }
  | {
      kind: "infeasible";
      data: Extract<SolveResponse, { status: "infeasible" }>;
    }
  | {
      kind: "invalid";
      data: Extract<SolveResponse, { status: "invalid" }>;
    };

export function App() {
  const [stations, setStations] = useState<StationDraft[]>(() =>
    sampleLine()
  );
  const [result, setResult] = useState<Result | null>(null);
  const [localErrors, setLocalErrors] = useState<LocalFieldError[]>([]);
  const [importError, setImportError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const errorsByStation = useMemo(() => {
    const m = new Map<number, LocalFieldError[]>();
    for (const e of localErrors) {
      if (e.station === 0) continue;
      const list = m.get(e.station) ?? [];
      list.push(e);
      m.set(e.station, list);
    }
    return m;
  }, [localErrors]);

  const topErrors = useMemo(
    () => localErrors.filter((e) => e.station === 0),
    [localErrors]
  );

  const clearConclusions = () => {
    // Requirement: editing clears old conclusions.
    setResult(null);
  };

  const updateStation = (i: number, next: StationDraft) => {
    setStations((prev) => prev.map((s, k) => (k === i ? next : s)));
    clearConclusions();
  };

  const addStation = () => {
    if (stations.length >= 80) return;
    setStations([...stations, emptyStation()]);
    clearConclusions();
  };

  const removeStation = (i: number) => {
    if (stations.length <= 2) return;
    setStations(stations.filter((_, k) => k !== i));
    clearConclusions();
  };

  const loadSample = () => {
    setStations(sampleLine());
    setLocalErrors([]);
    setImportError(null);
    clearConclusions();
  };

  const onImportFile = async (file: File) => {
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const drafts = payloadToDrafts(parsed);
      if (drafts.length < 2 || drafts.length > 80) {
        throw new Error("线路段数必须在 2 至 80 之间");
      }
      setStations(drafts);
      setLocalErrors([]);
      setImportError(null);
      clearConclusions();
    } catch (err) {
      setImportError(
        `导入失败：${err instanceof Error ? err.message : String(err)}`
      );
    }
  };

  const solve = async () => {
    const payload = draftsToPayload(stations);
    const errors = validateRequest(payload);
    setLocalErrors(errors);
    setImportError(null);
    if (errors.length > 0) {
      clearConclusions();
      return;
    }
    setRunning(true);
    try {
      const resp = await fetch("/api/solve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = (await resp.json()) as SolveResponse;
      if (data.status === "optimal") {
        setResult({ kind: "optimal", data });
      } else if (data.status === "infeasible") {
        setResult({ kind: "infeasible", data });
      } else {
        setLocalErrors(
          data.errors.map((e) => ({
            station: e.station ?? 0,
            field: e.field,
            message: e.message,
          }))
        );
        setResult({ kind: "invalid", data });
      }
    } catch (err) {
      setImportError(
        `调用计算服务失败：${
          err instanceof Error ? err.message : String(err)
        }`
      );
      clearConclusions();
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="page">
      <header className="app-header">
        <h1>海底光缆色散补偿盒排布工作台</h1>
        <p className="subtitle">
          精确整数动态规划 · 全局依次最小化（安装数 → 总插损 →
          末站|残差|）· 不枚举组合
        </p>
      </header>

      <div className="toolbar">
        <button type="button" onClick={addStation} disabled={stations.length >= 80}>
          + 添加站点（{stations.length}/80）
        </button>
        <button type="button" onClick={loadSample}>
          载入示例
        </button>
        <button type="button" onClick={() => fileInput.current?.click()}>
          导入 JSON
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="application/json,.json"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void onImportFile(f);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          className="primary"
          onClick={() => void solve()}
          disabled={running}
        >
          {running ? "计算中…" : "调用 API 计算"}
        </button>
      </div>

      {importError && <div className="banner bad">{importError}</div>}
      {topErrors.length > 0 && (
        <div className="banner bad">
          {topErrors.map((e, i) => (
            <div key={i}>
              <code>{e.field}</code>：{e.message}
            </div>
          ))}
        </div>
      )}

      <main className="layout">
        <div className="editors">
          {stations.map((st, i) => (
            <StationEditor
              key={i}
              station={st}
              index={i}
              errors={errorsByStation.get(i + 1) ?? []}
              onChange={(next) => updateStation(i, next)}
              onRemove={() => removeStation(i)}
              canRemove={stations.length > 2}
            />
          ))}
        </div>

        <aside className="panel">
          <h2>结论</h2>
          {result === null ? (
            <p className="hint">
              编辑线路后点击「调用 API 计算」。旧结论会在输入变化时清除。
            </p>
          ) : result.kind === "optimal" ? (
            <OptimalResult result={result.data} />
          ) : result.kind === "infeasible" ? (
            <InfeasibleResult result={result.data} />
          ) : (
            <InvalidResult result={result.data} />
          )}
        </aside>
      </main>

      <footer className="foot">
        所有数值至多三位小数，缩放 1000 倍为 −20000~20000
        整数；闭区间边界包含在内。
      </footer>
    </div>
  );
}
