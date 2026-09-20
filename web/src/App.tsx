import { useMemo, useState } from "react";
import {
  ApiResponse,
  FieldError,
  LineDraft,
  MAX_SEGMENTS,
  MIN_SEGMENTS,
} from "./types";
import {
  clientChecks,
  emptyBox,
  emptyLine,
  exampleLine,
  exportLine,
  importLine,
} from "./lineio";
import { StationCard } from "./components/StationCard";
import { ResultPanel } from "./components/ResultPanel";

type Busy =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "network"; message: string };

export default function App() {
  const [line, setLine] = useState<LineDraft>(() => exampleLine());
  const [result, setResult] = useState<ApiResponse | null>(null);
  const [busy, setBusy] = useState<Busy>({ kind: "idle" });
  const [importText, setImportText] = useState("");
  const [importErr, setImportErr] = useState<string | null>(null);
  const [serverErrors, setServerErrors] = useState<FieldError[]>([]);

  const localErrors = useMemo(() => clientChecks(line), [line]);

  // 服务端字段错误合并进红框提示（按 field 精确匹配）。
  const errors = useMemo(() => {
    const m = new Map(localErrors);
    for (const e of serverErrors) m.set(e.field, e.message);
    return m;
  }, [localErrors, serverErrors]);

  /** 任何编辑都清除旧结论与旧错误，避免展示过期结果。 */
  function clearConclusion() {
    setResult(null);
    setServerErrors([]);
  }

  function mutate(fn: (draft: LineDraft) => void) {
    setLine((prev) => {
      const next: LineDraft = structuredClone(prev);
      fn(next);
      return next;
    });
    clearConclusion();
  }

  function replace(next: LineDraft) {
    setLine(next);
    clearConclusion();
  }

  function resize(n: number) {
    if (n < MIN_SEGMENTS || n > MAX_SEGMENTS) return;
    mutate((d) => {
      const cur = d.segments.length;
      if (n > cur) {
        const add = emptyLine(n);
        d.segments.push(...add.segments.slice(cur));
        d.stations.push(...add.stations.slice(cur));
      } else {
        d.segments.length = n;
        d.stations.length = n;
      }
    });
  }

  async function calculate() {
    setBusy({ kind: "loading" });
    setResult(null);
    setServerErrors([]);
    try {
      const resp = await fetch("/api/solve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(line),
      });
      const data = (await resp.json()) as ApiResponse;
      if (data.status === "invalid") {
        setServerErrors(data.errors);
      }
      setResult(data);
      setBusy({ kind: "idle" });
    } catch (e) {
      setBusy({ kind: "network", message: (e as Error).message });
    }
  }

  function handleImport() {
    try {
      const next = importLine(importText);
      replace(next);
      setImportErr(null);
      setImportText("");
    } catch (e) {
      setImportErr((e as Error).message);
    }
  }

  function handleExport() {
    const blob = new Blob([exportLine(line)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "line.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  const n = line.segments.length;

  return (
    <div className="app">
      <header className="topbar">
        <h1>海底光缆色散补偿盒排布工作台</h1>
        <span className="subtitle">
          精确整数动态规划 · 依次最小化 安装数 → 总插损 → 末站|残差|
        </span>
      </header>

      <div className="toolbar panel">
        <label>
          段数（{MIN_SEGMENTS}–{MAX_SEGMENTS}）
          <input
            type="number"
            min={MIN_SEGMENTS}
            max={MAX_SEGMENTS}
            value={n}
            onChange={(e) => resize(Number(e.target.value))}
          />
        </label>
        <button type="button" className="btn" onClick={() => replace(emptyLine(n))}>
          清空为零初值
        </button>
        <button type="button" className="btn" onClick={() => replace(exampleLine())}>
          载入示例
        </button>
        <button type="button" className="btn" onClick={handleExport}>
          导出 JSON
        </button>
        <div className="import-box">
          <textarea
            placeholder='粘贴 JSON：{"segments":[...],"stations":[...]}'
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            rows={1}
          />
          <button type="button" className="btn" onClick={handleImport}>
            导入
          </button>
        </div>
        {importErr && <span className="import-err">{importErr}</span>}
      </div>

      <div className="compute-bar">
        <button
          type="button"
          className="btn-primary"
          disabled={busy.kind === "loading"}
          onClick={calculate}
        >
          {busy.kind === "loading" ? "计算中…" : "调用 API 计算最优排布"}
        </button>
        {busy.kind === "network" && (
          <span className="import-err">网络错误：{busy.message}</span>
        )}
        <span className="muted small">
          共 {n} 段 / {n} 站；每站不装或选一盒；所有比较使用缩放后的精确整数。
        </span>
      </div>

      <div className="cards">
        {line.stations.map((st, i) => (
          <StationCard
            key={i}
            index={i}
            increment={line.segments[i].increment}
            station={st}
            errors={errors}
            onIncrement={(v) =>
              mutate((d) => {
                d.segments[i].increment = v;
              })
            }
            onStation={(patch) =>
              mutate((d) => {
                Object.assign(d.stations[i], patch);
              })
            }
            onBox={(j, patch) =>
              mutate((d) => {
                Object.assign(d.stations[i].boxes[j], patch);
              })
            }
            onAddBox={() =>
              mutate((d) => {
                if (d.stations[i].boxes.length < 12)
                  d.stations[i].boxes.push(emptyBox());
              })
            }
            onRemoveBox={(j) =>
              mutate((d) => {
                d.stations[i].boxes.splice(j, 1);
              })
            }
          />
        ))}
      </div>

      {result && <ResultPanel result={result} />}
    </div>
  );
}
