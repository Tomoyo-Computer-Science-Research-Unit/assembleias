const MONTH_NAMES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MONTH_LONG = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro"
];

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "–";
  }
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: digits }).format(value);
}

export function formatRate(value: number | null | undefined): string {
  return formatNumber(value, 1);
}

/** "+12,3%" / "−4,0%" with a typographic minus; "–" when unknown. */
export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "–";
  }
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: digits }).format(Math.abs(value))}%`;
}

export function formatSigned(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "–";
  }
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: digits }).format(Math.abs(value))}`;
}

export function monthShort(month: number): string {
  return MONTH_NAMES[month - 1] ?? String(month);
}

export function monthLong(month: number): string {
  return MONTH_LONG[month - 1] ?? String(month);
}

/** "jan–ago 2026" */
export function formatPeriodRange(year: number, lastMonth: number): string {
  if (lastMonth >= 12) {
    return String(year);
  }
  return lastMonth === 1 ? `jan ${year}` : `jan–${monthShort(lastMonth)} ${year}`;
}

/** "08/2026" */
export function formatMonthYear(year: number, month: number): string {
  return `${String(month).padStart(2, "0")}/${year}`;
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" }).format(new Date(value));
}

export function formatIsoDate(value: string | null, fallback = "atual"): string {
  if (!value) {
    return fallback;
  }
  const [year, month] = value.split("-").map(Number);
  return `${monthShort(month)} ${year}`;
}

export function formatBytes(value: number | null): string {
  if (value === null) {
    return "–";
  }
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(value / 1024 / 1024)} MB`;
}

/** Arrow glyph for a change; neutral when zero or unknown. */
export function deltaGlyph(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value) || value === 0) {
    return "＝";
  }
  return value > 0 ? "▲" : "▼";
}

/** Indicadores em que subir é bom (apreensões), não ruim. */
const INVERTED_INDICATORS = new Set(["apreensao_armas"]);

/**
 * Classe de cor para uma variação: "worse" quando a violência sobe, "better" quando cai.
 * Para apreensões a polaridade inverte; sem indicador, assume que subir é pior.
 */
export function deltaClass(value: number | null | undefined, indicator?: string): string {
  if (value === null || value === undefined || !Number.isFinite(value) || value === 0) {
    return "";
  }
  const up = value > 0;
  const upIsGood = indicator ? INVERTED_INDICATORS.has(indicator) : false;
  return up === upIsGood ? "better" : "worse";
}
