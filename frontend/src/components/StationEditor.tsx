import type { LocalFieldError } from "../types";
import type { StationDraft, BoxDraft } from "../model";

interface Props {
  station: StationDraft;
  index: number;
  errors: LocalFieldError[];
  onChange: (next: StationDraft) => void;
  onRemove: () => void;
  canRemove: boolean;
}

function fieldHasError(
  errors: LocalFieldError[],
  field: string
): boolean {
  return errors.some((e) => e.field === field);
}

export function StationEditor({
  station,
  index,
  errors,
  onChange,
  onRemove,
  canRemove,
}: Props) {
  const stationNo = index + 1;

  const set = (patch: Partial<StationDraft>) =>
    onChange({ ...station, ...patch });

  const setBox = (bi: number, patch: Partial<BoxDraft>) => {
    const boxes = station.boxes.map((b, k) =>
      k === bi ? { ...b, ...patch } : b
    );
    onChange({ ...station, boxes });
  };

  const addBox = () => {
    if (station.boxes.length >= 12) return;
    onChange({
      ...station,
      boxes: [
        ...station.boxes,
        { id: "", correction: "0", loss: "0" },
      ],
    });
  };

  const removeBox = (bi: number) =>
    onChange({
      ...station,
      boxes: station.boxes.filter((_, k) => k !== bi),
    });

  const cls = (field: string) =>
    fieldHasError(errors, field) ? "num bad" : "num";

  return (
    <section className="station">
      <header className="station-head">
        <h3>站点 {stationNo}</h3>
        <button
          type="button"
          className="link danger"
          onClick={onRemove}
          disabled={!canRemove}
          title="删除此站"
        >
          删除站
        </button>
      </header>

      <div className="grid3">
        <label>
          段色散增量
          <input
            className={cls("increment")}
            value={station.increment}
            inputMode="decimal"
            onChange={(e) => set({ increment: e.target.value })}
          />
        </label>
        <label>
          区间下界
          <input
            className={cls("lower")}
            value={station.lower}
            inputMode="decimal"
            onChange={(e) => set({ lower: e.target.value })}
          />
        </label>
        <label>
          区间上界
          <input
            className={cls("upper")}
            value={station.upper}
            inputMode="decimal"
            onChange={(e) => set({ upper: e.target.value })}
          />
        </label>
      </div>

      <div className="boxes">
        <div className="boxes-head">
          <span>候选盒（{station.boxes.length}/12）</span>
          <button
            type="button"
            className="link"
            onClick={addBox}
            disabled={station.boxes.length >= 12}
          >
            + 添加候选盒
          </button>
        </div>

        {station.boxes.length === 0 && (
          <p className="hint">本站可不装盒；如需要则添加候选盒。</p>
        )}

        {station.boxes.map((box, bi) => (
          <div className="box-row" key={bi}>
            <label>
              编号
              <input
                className={fieldHasError(errors, `boxes[${bi}].id`)
                  ? "num bad small"
                  : "num small"}
                value={box.id}
                inputMode="numeric"
                onChange={(e) =>
                  setBox(bi, { id: e.target.value })
                }
              />
            </label>
            <label>
              修正量
              <input
                className={fieldHasError(
                  errors,
                  `boxes[${bi}].correction`
                )
                  ? "num bad"
                  : "num"}
                value={box.correction}
                inputMode="decimal"
                onChange={(e) =>
                  setBox(bi, { correction: e.target.value })
                }
              />
            </label>
            <label>
              插损（≥0）
              <input
                className={fieldHasError(errors, `boxes[${bi}].loss`)
                  ? "num bad"
                  : "num"}
                value={box.loss}
                inputMode="decimal"
                onChange={(e) => setBox(bi, { loss: e.target.value })}
              />
            </label>
            <button
              type="button"
              className="link danger"
              onClick={() => removeBox(bi)}
            >
              移除
            </button>
          </div>
        ))}
      </div>

      {errors.length > 0 && (
        <ul className="errlist">
          {errors.map((e, k) => (
            <li key={k}>
              <code>{e.field}</code>：{e.message}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
