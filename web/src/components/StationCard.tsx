import { StationDraft } from "../types";
import { MAX_BOXES } from "../types";
import { NumberField } from "./NumberField";

interface Props {
  index: number;
  increment: string;
  station: StationDraft;
  errors: Map<string, string>;
  onIncrement: (v: string) => void;
  onStation: (patch: Partial<StationDraft>) => void;
  onBox: (j: number, patch: Partial<{ id: string; correction: string; loss: string }>) => void;
  onAddBox: () => void;
  onRemoveBox: (j: number) => void;
}

export function StationCard({
  index,
  increment,
  station,
  errors,
  onIncrement,
  onStation,
  onBox,
  onAddBox,
  onRemoveBox,
}: Props) {
  const i = index;
  return (
    <section className="station-card" aria-label={`第 ${i + 1} 段与站点`}>
      <header>
        <span className="station-no">站点 {i + 1}</span>
        <label className="seg-inc">
          段增量
          <NumberField
            value={increment}
            onChange={onIncrement}
            error={errors.get(`segments[${i}].increment`)}
            ariaLabel={`第 ${i + 1} 段色散增量`}
          />
        </label>
      </header>

      <div className="bounds">
        安全闭区间
        <label>
          下界
          <NumberField
            value={station.lower}
            onChange={(v) => onStation({ lower: v })}
            error={errors.get(`stations[${i}].lower`)}
            ariaLabel={`站点 ${i + 1} 区间下界`}
          />
        </label>
        <span className="range-sep">≤ 累计 ≤</span>
        <label>
          上界
          <NumberField
            value={station.upper}
            onChange={(v) => onStation({ upper: v })}
            error={errors.get(`stations[${i}].upper`)}
            ariaLabel={`站点 ${i + 1} 区间上界`}
          />
        </label>
      </div>

      <div className="boxes">
        <table>
          <thead>
            <tr>
              <th>候选盒编号</th>
              <th>修正量</th>
              <th>插损（≥0）</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {station.boxes.map((b, j) => (
              <tr key={j}>
                <td>
                  <input
                    type="text"
                    className={errors.get(`stations[${i}].boxes[${j}].id`) ? "invalid" : ""}
                    value={b.id}
                    aria-label={`站点 ${i + 1} 候选盒 ${j + 1} 编号`}
                    onChange={(e) => onBox(j, { id: e.target.value })}
                  />
                  {errors.get(`stations[${i}].boxes[${j}].id`) && (
                    <span className="field-err">
                      {errors.get(`stations[${i}].boxes[${j}].id`)}
                    </span>
                  )}
                </td>
                <td>
                  <NumberField
                    value={b.correction}
                    onChange={(v) => onBox(j, { correction: v })}
                    error={errors.get(`stations[${i}].boxes[${j}].correction`)}
                    ariaLabel={`站点 ${i + 1} 候选盒 ${j + 1} 修正量`}
                  />
                </td>
                <td>
                  <NumberField
                    value={b.loss}
                    onChange={(v) => onBox(j, { loss: v })}
                    error={errors.get(`stations[${i}].boxes[${j}].loss`)}
                    ariaLabel={`站点 ${i + 1} 候选盒 ${j + 1} 插损`}
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className="btn-mini"
                    onClick={() => onRemoveBox(j)}
                  >
                    删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button
          type="button"
          className="btn-ghost"
          disabled={station.boxes.length >= MAX_BOXES}
          onClick={onAddBox}
        >
          + 添加候选盒（{station.boxes.length}/{MAX_BOXES}）
        </button>
      </div>
    </section>
  );
}
