"use client";

import type { PresencaMes } from "@/lib/static-api";

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/** Anos nas linhas, meses nas colunas; o número é o total de faltas no mês, o fundo escurece com ele. */
export function MonthGrid({ porMes }: { porMes: Record<string, PresencaMes> }) {
  const years = [...new Set(Object.keys(porMes).map((key) => key.slice(0, 4)))].sort((a, b) => Number(b) - Number(a));
  if (years.length === 0) {
    return <p className="text-[11px] tracking-[0.18em] text-ash">SEM PRESENÇA APURADA</p>;
  }
  return (
    <div className="monthgrid" role="table" aria-label="Faltas por mês">
      <span className="head" />
      {MONTHS.map((month) => (
        <span key={month} className="head">
          {month}
        </span>
      ))}
      <span className="head">total</span>
      {years.map((year) => {
        let total = 0;
        const cells = MONTHS.map((_, index) => {
          const row = porMes[`${year}-${String(index + 1).padStart(2, "0")}`];
          if (!row) {
            return <span key={index} className="empty" title={`${MONTHS[index]} ${year}: sem apuração`}>·</span>;
          }
          total += row.total;
          const shade = Math.min(0.7, row.total * 0.14);
          return (
            <span key={index} style={{ background: `color-mix(in srgb, var(--ink) ${Math.round(shade * 100)}%, transparent)`, color: shade > 0.4 ? "var(--paper)" : undefined }} title={`${MONTHS[index]} ${year}: ${row.total} faltas, ${row.abonadas} abonadas`}>
              {row.total}
            </span>
          );
        });
        return [
          <span key={`${year}-h`} className="head num">
            {year}
          </span>,
          ...cells,
          <span key={`${year}-t`} className="num">
            {total}
          </span>
        ];
      })}
    </div>
  );
}
