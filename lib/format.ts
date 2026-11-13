const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function money(value: number, currency = "GBP", opts: { sign?: boolean } = {}): string {
  const formatted = new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(value));
  if (value < 0) return `-${formatted}`;
  return opts.sign && value > 0 ? `+${formatted}` : formatted;
}

export function compactMoney(value: number, currency = "GBP"): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

/** "2026-08-05" -> "5 Aug" */
export function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${Number(d)} ${MONTHS[Number(m) - 1]}`;
}

/** "2026-08-05" -> "5 Aug 2026" */
export function longDate(iso: string): string {
  const [y] = iso.split("-");
  return `${shortDate(iso)} ${y}`;
}

/** "2026-08" -> "Aug 2026" */
export function monthLabel(month: string): string {
  const [y, m] = month.split("-");
  return `${MONTHS[Number(m) - 1]} ${y}`;
}

export function toolLabel(name: string): string {
  return name.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}
