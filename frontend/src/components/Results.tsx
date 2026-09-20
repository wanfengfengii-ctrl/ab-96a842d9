import type {
  OptimalResponse,
  InfeasibleResponse,
  InvalidResponse,
} from "../types";
import { formatMilli } from "../types";

export function OptimalResult({ result }: { result: OptimalResponse }) {
  const { summary, witnesses, stations } = result;
  return (
    <div className="result ok">
      <h3>✅ 全局最优排布方案</h3>
      <div className="summary">
        <div>
          <span className="metric-label">安装盒数</span>
          <strong>{summary.installed_count}</strong>
        </div>
        <div>
          <span className="metric-label">总插损</span>
          <strong>
            {formatMilli(summary.total_insertion_loss_milli_db)} dB
          </strong>
        </div>
        <div>
          <span className="metric-label">末站 |残差|</span>
          <strong>
            {formatMilli(summary.final_abs_residual_milli)}
          </strong>
        </div>
      </div>

      <ol className="choice-list">
        {stations.map((c) => (
          <li key={c.station}>
            <span className="st-no">第 {c.station} 站</span>
            {c.installed ? (
              <span className="badge box">安装盒 #{c.box_id}</span>
            ) : (
              <span className="badge empty">不装盒</span>
            )}
          </li>
        ))}
      </ol>

      {summary.tie && (
        <div className="tie">
          <h4>存在并列最优：按各站编号序列排序的前两份见证</h4>
          {witnesses.map((w, i) => (
            <div key={i} className="witness">
              <span className="witness-tag">
                见证 {i + 1}
              </span>
              <code>
                [
                {w
                  .map((x) => (x === null ? "∅" : `#${x}`))
                  .join(", ")}
                ]
              </code>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function InfeasibleResult({
  result,
}: {
  result: InfeasibleResponse;
}) {
  return (
    <div className="result infeasible">
      <h3>⛔ 不存在全局合法方案</h3>
      <p>
        <strong>第 {result.failed_station} 站</strong>{" "}
        处理后，可达状态集合第一次变为空：
      </p>
      <p className="detail">{result.message}</p>
      <p className="hint">
        说明无论此前各站如何选择，累计色散都无法落入本站安全闭区间；
        逐站贪心回零无法挽回，需调整本站区间或候选盒配置。
      </p>
    </div>
  );
}

export function InvalidResult({
  result,
}: {
  result: InvalidResponse;
}) {
  const byStation = new Map<number | null, typeof result.errors>();
  for (const e of result.errors) {
    const list = byStation.get(e.station) ?? [];
    list.push(e);
    byStation.set(e.station, list);
  }
  const top = byStation.get(null) ?? [];
  const stationNos = [...byStation.keys()]
    .filter((k): k is number => k !== null)
    .sort((a, b) => a - b);

  return (
    <div className="result invalid">
      <h3>⚠️ 输入有误</h3>
      {top.length > 0 && (
        <ul className="errlist">
          {top.map((e, i) => (
            <li key={i}>
              <code>{e.field}</code>：{e.message}
            </li>
          ))}
        </ul>
      )}
      <ul className="errlist">
        {stationNos.map((no) => (
          <li key={no}>
            <strong>第 {no} 站：</strong>
            <ul>
              {(byStation.get(no) ?? []).map((e, i) => (
                <li key={i}>
                  <code>{e.field}</code>：{e.message}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}
