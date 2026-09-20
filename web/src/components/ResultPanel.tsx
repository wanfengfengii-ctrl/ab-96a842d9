import { ApiResponse } from "../types";
import { formatScaled } from "../decimal";

interface Props {
  result: ApiResponse;
}

export function ResultPanel({ result }: Props) {
  if (result.status === "invalid") {
    return (
      <div className="panel result invalid" role="alert">
        <h2>输入有误（{result.errors.length} 项）</h2>
        <p className="muted">
          已按“站点 → 字段”定位，请修正后重新计算。对应输入框已标红。
        </p>
        <ul className="err-list">
          {result.errors.map((e, idx) => (
            <li key={idx}>
              <code>{e.field}</code>
              <span>{e.message}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (result.status === "infeasible") {
    return (
      <div className="panel result infeasible" role="alert">
        <h2>无合法方案</h2>
        <p>
          首个可达状态集合变空的是
          <strong> 第 {result.infeasible_station} 号站点</strong>。
        </p>
        <p className="muted">
          即：此前各站仍存在可行选择，但无论第 {result.infeasible_station}{" "}
          站装哪一个候选盒（或不装），累计值都无法落入其安全闭区间。
          逐站贪心回零正是在此类站点上会提前走入死路。
        </p>
      </div>
    );
  }

  const { objective, witnesses, unique } = result;
  return (
    <div className="panel result optimal">
      <h2>计算结果</h2>
      <div className="obj-grid">
        <div>
          <span className="obj-label">① 安装盒数</span>
          <span className="obj-value">{objective.boxes_installed}</span>
        </div>
        <div>
          <span className="obj-label">② 总插损</span>
          <span className="obj-value">
            {formatScaled(objective.total_loss)}
          </span>
        </div>
        <div>
          <span className="obj-label">③ 末站 |残差|</span>
          <span className="obj-value">
            {formatScaled(objective.final_abs_residual)}
          </span>
        </div>
      </div>

      <h3>{unique ? "唯一最优选盒序列" : "并列最优 — 按编号序列排序的前两份见证"}</h3>
      <div className={witnesses.length > 1 ? "witness-grid" : ""}>
        {witnesses.map((w, wi) => (
          <div className="witness" key={wi}>
            <div className="witness-title">
              {witnesses.length > 1 ? `见证 ${wi + 1}` : "完整序列"}
            </div>
            <table className="seq-table">
              <thead>
                <tr>
                  <th>站点</th>
                  <th>选择</th>
                  <th>修正量</th>
                  <th>插损</th>
                  <th>站后累计</th>
                </tr>
              </thead>
              <tbody>
                {w.sequence.map((s) => (
                  <tr key={s.station}>
                    <td>{s.station}</td>
                    <td>{s.choice ? s.choice.id : <em>不装</em>}</td>
                    <td>
                      {s.choice ? formatScaled(s.choice.correction) : "—"}
                    </td>
                    <td>{s.choice ? formatScaled(s.choice.loss) : "—"}</td>
                    <td className="cum">{formatScaled(s.cumulative)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
