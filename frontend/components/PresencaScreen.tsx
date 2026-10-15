"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useScreenHotkeys } from "@/components/Hotkeys";
import { EmptyState, Panel, Screen } from "@/components/ui";
import { displayName, getDeputados, presencaYears, type PresencaMes } from "@/lib/static-api";

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
type Sort = "total" | "nome";
type YearSel = number | "all";

function normalize(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

/** Faltas em plenário: por mês num ano, ou por ano no período todo. */
export function PresencaScreen() {
  const years = presencaYears();
  const all = getDeputados();
  const [year, setYear] = useState<YearSel>(years[0] ?? new Date().getFullYear());
  const [sort, setSort] = useState<Sort>("total");
  const [partido, setPartido] = useState("all");
  const [query, setQuery] = useState("");
  const partidos = useMemo(() => [...new Set(all.map((item) => item.partido).filter((item): item is string => Boolean(item)))].sort((a, b) => a.localeCompare(b, "pt-BR")), [all]);
  const columns = year === "all" ? [...years].sort((a, b) => a - b).map(String) : MONTHS;

  const rows = useMemo(() => {
    const needle = normalize(query.trim());
    return all
      .filter((deputado) => partido === "all" || deputado.partido === partido)
      .filter((deputado) => !needle || normalize(`${displayName(deputado)} ${deputado.nome}`).includes(needle))
      .map((deputado) => {
        const cells: Array<PresencaMes | null> =
          year === "all"
            ? columns.map((item) => deputado.presenca?.por_ano?.[item] ?? null)
            : MONTHS.map((_, index) => deputado.presenca?.por_mes?.[`${year}-${String(index + 1).padStart(2, "0")}`] ?? null);
        const total = cells.reduce((sum, cell) => sum + (cell?.total ?? 0), 0);
        const abonadas = cells.reduce((sum, cell) => sum + (cell?.abonadas ?? 0), 0);
        return { deputado, cells, total, abonadas, apurados: cells.filter(Boolean).length };
      })
      .filter((row) => row.apurados > 0)
      .sort((a, b) => (sort === "nome" ? displayName(a.deputado).localeCompare(displayName(b.deputado), "pt-BR") : b.total - a.total || a.deputado.nome.localeCompare(b.deputado.nome)));
  }, [all, columns, partido, query, sort, year]);

  const hotkeys = useMemo(
    () => ({
      ArrowLeft: () => setYear((current) => stepYear(years, current, 1)),
      ArrowRight: () => setYear((current) => stepYear(years, current, -1)),
      ArrowUp: () => setSort((current) => (current === "total" ? "nome" : "total")),
      ArrowDown: () => setSort((current) => (current === "total" ? "nome" : "total"))
    }),
    [years]
  );
  useScreenHotkeys(hotkeys);
  const shade = (cell: PresencaMes | null) => (cell && cell.total ? { background: `color-mix(in srgb, var(--ink) ${Math.min(60, cell.total * (year === "all" ? 3 : 12))}%, transparent)`, color: cell.total >= (year === "all" ? 15 : 4) ? "var(--paper)" : undefined } : undefined);

  return (
    <Screen columns="minmax(0, 1fr)" rows="minmax(0, 1fr)">
      <Panel
        title={
          <span>
            <b>Faltas em plenário</b> · {year === "all" ? `${years[years.length - 1]}–${years[0]}` : year}
          </span>
        }
        aside={
          <>
            <input className="yearselect w-[180px]" type="search" aria-label="Buscar deputado" placeholder="buscar nome" value={query} onChange={(event) => setQuery(event.target.value)} />
            <select className="yearselect" aria-label="Partido" value={partido} onChange={(event) => setPartido(event.target.value)}>
              <option value="all">Partidos</option>
              {partidos.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <select className="yearselect" aria-label="Ano" value={year === "all" ? "all" : String(year)} onChange={(event) => setYear(event.target.value === "all" ? "all" : Number(event.target.value))}>
              <option value="all">Todos os anos</option>
              {years.map((item) => (
                <option key={item} value={String(item)}>
                  {item}
                </option>
              ))}
            </select>
            <select className="yearselect" aria-label="Ordem" value={sort} onChange={(event) => setSort(event.target.value as Sort)}>
              <option value="total">Por faltas</option>
              <option value="nome">Por nome</option>
            </select>
          </>
        }
        flush
        fill
      >
        {rows.length === 0 ? (
          <EmptyState>SEM PRESENÇA APURADA NESTE RECORTE</EmptyState>
        ) : (
          <table className="ruled">
            <thead>
              <tr>
                <th>Deputado</th>
                <th>Partido</th>
                {columns.map((column) => (
                  <th key={column} className="right">
                    {column}
                  </th>
                ))}
                <th className="right">Total</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.deputado.id}>
                  <td className="max-w-[220px] whitespace-normal break-words">
                    <Link href={`/?v=${encodeURIComponent(row.deputado.id)}`} className="text-ink hover:underline hover:underline-offset-4">
                      {displayName(row.deputado)}
                    </Link>
                  </td>
                  <td className="faint">{row.deputado.partido}</td>
                  {row.cells.map((cell, index) => (
                    <td key={index} className={`num right ${cell === null ? "faint" : ""}`} style={shade(cell)} title={cell ? `${cell.total} faltas, ${cell.abonadas} abonadas` : "sem apuração"}>
                      {cell === null ? "·" : cell.total === 0 ? "" : cell.abonadas ? `${cell.total} (${cell.abonadas})` : cell.total}
                    </td>
                  ))}
                  <td className="num right">
                    {row.total}
                    {row.abonadas ? <span className="faint"> ({row.abonadas})</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </Screen>
  );
}

function stepYear(years: number[], current: YearSel, step: number): YearSel {
  const options: YearSel[] = ["all", ...years];
  const index = options.indexOf(current);
  return options[(index + step + options.length) % options.length];
}
