/** 缩放整数（毫单位）与展示字符串互转，全程不产生二进制浮点误差。 */

/** 把 *1000 的整数还原为最多三位小数的字符串。 */
export function formatScaled(value: number): string {
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  const whole = Math.floor(abs / 1000);
  const frac = abs % 1000;
  if (frac === 0) return `${sign}${whole}`;
  return `${sign}${whole}.${String(frac).padStart(3, "0").replace(/0+$/, "")}`;
}

/**
 * 轻量客户端校验：仅用于即时提示，服务端校验才是最终依据。
 * 返回归一化字符串（去空格）；不合法返回 null。
 */
export function normalizeDecimal(raw: string): string | null {
  const s = raw.trim();
  if (!/^[+-]?(\d+\.\d+|\.\d+|\d+)$/.test(s)) return null;
  const [, frac = ""] = s.split(".");
  if (frac.length > 3) return null;
  return s;
}

/** 把三位小数字符串精确换算为整数（乘 1000），用于区间提示。 */
export function toScaled(raw: string): number | null {
  const s = normalizeDecimal(raw);
  if (s === null) return null;
  const neg = s.startsWith("-");
  const body = s.replace(/^[+-]/, "");
  const [i, f = ""] = body.split(".");
  const n = Number(i) * 1000 + Number(f.padEnd(3, "0"));
  return neg ? -n : n;
}
