interface Props {
  value: string;
  onChange: (v: string) => void;
  error?: string;
  ariaLabel: string;
  placeholder?: string;
}

/** 行内文本数值输入；非法/服务端错误时红框并展示提示。 */
export function NumberField({
  value,
  onChange,
  error,
  ariaLabel,
  placeholder,
}: Props) {
  return (
    <span className="numfield" title={error}>
      <input
        type="text"
        inputMode="decimal"
        className={error ? "invalid" : ""}
        value={value}
        aria-label={ariaLabel}
        aria-invalid={Boolean(error)}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
      {error && <span className="field-err">{error}</span>}
    </span>
  );
}
