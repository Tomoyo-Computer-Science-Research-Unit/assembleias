"use client";

export type YearSel = number | "all";

/** Seletor compacto de ano orçamentário para o cabeçalho dos painéis; "Tudo" soma o período. */
export function YearSelect({ years, value, onChange }: { years: number[]; value: YearSel; onChange: (value: YearSel) => void }) {
  return (
    <select className="yearselect" aria-label="Ano" value={value === "all" ? "all" : String(value)} onChange={(event) => onChange(event.target.value === "all" ? "all" : Number(event.target.value))}>
      <option value="all">
        {years[0]}–{years[years.length - 1]}
      </option>
      {years.map((year) => (
        <option key={year} value={String(year)}>
          {year}
        </option>
      ))}
    </select>
  );
}

export function stepYear(years: number[], current: YearSel, step: number): YearSel {
  const options: YearSel[] = ["all", ...years];
  const index = options.indexOf(current);
  return options[(index + step + options.length) % options.length];
}
