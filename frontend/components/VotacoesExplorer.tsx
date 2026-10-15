"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useScreenHotkeys } from "@/components/Hotkeys";
import { EmptyState, Panel, Screen, Stat } from "@/components/ui";
import { YearSelect, stepYear, type YearSel } from "@/components/YearSelect";
import { HAS_OBSTRUCAO, VOTO_LABELS, cleanAuthor, displayName, formatDate, getDeputados, getVotacoes, loadVotacao, objetoLabel, resultadoClass, resultadoLabel, votacaoTitle, type VotacaoDetalhe, type Voto } from "@/lib/static-api";
import { CASA } from "@/lib/uf";

const SHORT_LABELS: Partial<Record<Voto, string>> = { abstencao: "Abst.", obstrucao: "Obstr." };

type ResultFilter = "todos" | "aprovado" | "rejeitado" | "outros";
const RESULTS: Array<{ value: ResultFilter; label: string }> = [
  { value: "todos", label: "Todos" },
  { value: "aprovado", label: "Aprovados" },
  { value: "rejeitado", label: "Rejeitados" },
  { value: "outros", label: "Outros" }
];

export function VotacoesExplorer() {
  const all = useMemo(() => [...getVotacoes()].sort((a, b) => (a.data < b.data ? 1 : a.data > b.data ? -1 : 0)), []);
  const deputados = useMemo(() => new Map(getDeputados().map((item) => [item.id, item])), []);
  const years = useMemo(() => [...new Set(all.map((item) => Number(item.data.slice(0, 4))))].sort((a, b) => b - a), [all]);
  const [year, setYear] = useState<YearSel>("all");
  const [result, setResult] = useState<ResultFilter>("todos");
  const [selectedId, setSelectedId] = useState(all[0]?.id ?? "");
  const [detalhe, setDetalhe] = useState<VotacaoDetalhe | null>(null);
  const votos = detalhe?.votos ?? null;
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("v");
    if (id && all.some((item) => item.id === id)) {
      setSelectedId(id);
    }
    setHydrated(true);
  }, [all]);
  useEffect(() => {
    if (hydrated) {
      window.history.replaceState(null, "", `${window.location.pathname}?v=${encodeURIComponent(selectedId)}`);
    }
  }, [hydrated, selectedId]);

  const list = useMemo(
    () =>
      all.filter((item) => {
        if (year !== "all" && Number(item.data.slice(0, 4)) !== year) {
          return false;
        }
        if (result === "aprovado" || result === "rejeitado") {
          return item.resultado === result;
        }
        if (result === "outros") {
          return item.resultado !== "aprovado" && item.resultado !== "rejeitado";
        }
        return true;
      }),
    [all, result, year]
  );
  const selected = all.find((item) => item.id === selectedId) ?? all[0];
  const index = Math.max(0, list.findIndex((item) => item.id === selected?.id));

  useEffect(() => {
    let alive = true;
    setDetalhe(null);
    if (!selected) {
      return;
    }
    loadVotacao(selected.id).then((data) => {
      if (alive) {
        setDetalhe(data);
      }
    });
    return () => {
      alive = false;
    };
  }, [selected]);

  const hotkeys = useMemo(
    () => ({
      ArrowUp: () => setSelectedId(list[(index - 1 + list.length) % list.length]?.id ?? selectedId),
      ArrowDown: () => setSelectedId(list[(index + 1) % list.length]?.id ?? selectedId),
      ArrowLeft: () => setYear((current) => stepYear([...years].reverse(), current, -1)),
      ArrowRight: () => setYear((current) => stepYear([...years].reverse(), current, 1)),
      r: () => setResult((current) => RESULTS[(RESULTS.findIndex((item) => item.value === current) + 1) % RESULTS.length].value)
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [index, list, selectedId, years]
  );
  useScreenHotkeys(hotkeys);

  if (!selected) {
    return <EmptyState>SEM VOTAÇÕES</EmptyState>;
  }

  const partidos = Object.entries(selected.por_partido ?? {})
    .map(([partido, totais]) => ({ partido, sim: totais.sim ?? 0, nao: totais.nao ?? 0, abstencao: totais.abstencao ?? 0, obstrucao: totais.obstrucao ?? 0 }))
    .sort((a, b) => b.sim + b.nao + b.abstencao + b.obstrucao - (a.sim + a.nao + a.abstencao + a.obstrucao));
  const colunas: Voto[] = HAS_OBSTRUCAO ? ["sim", "nao", "abstencao", "obstrucao", "ausente"] : ["sim", "nao", "abstencao", "ausente"];
  const grupos: Array<{ voto: Voto; ids: string[] }> = colunas.map((voto) => ({
    voto,
    ids: Object.entries(votos ?? {})
      .filter(([, value]) => value === voto || (voto === "ausente" && value === "presidindo"))
      .map(([id]) => id)
      .sort((a, b) => displayName(deputados.get(a) ?? { nome: a, nome_parlamentar: null }).localeCompare(displayName(deputados.get(b) ?? { nome: b, nome_parlamentar: null }), "pt-BR"))
  }));

  return (
    <Screen columns="360px minmax(0, 1fr)" rows="auto minmax(0, 1fr)">
      <Panel
        title={<b>Votações</b>}
        aside={
          <>
            <YearSelect years={[...years].reverse()} value={year} onChange={setYear} />
            <select className="yearselect" aria-label="Resultado" value={result} onChange={(event) => setResult(event.target.value as ResultFilter)}>
              {RESULTS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </>
        }
        flush
        fill
        style={{ gridRow: "1 / span 2" }}
      >
        <ul className="menu" role="listbox" aria-label="Votações">
          {list.map((item) => (
            <li key={item.id} role="presentation">
              <button type="button" role="option" aria-selected={item.id === selected.id} onClick={() => setSelectedId(item.id)}>
                <span className="whitespace-normal break-words">
                  {votacaoTitle(item)}
                  <span className="faint ml-1.5 text-[10px] tracking-[0.08em]">{formatDate(item.data)}</span>
                </span>
                <span className="num">
                  <span className={resultadoClass(item)}>{item.contagem.sim}–{item.contagem.nao}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel
        title={
          <span>
            <b>{votacaoTitle(selected)}</b> · {formatDate(selected.data)}
            {selected.sessao?.numero ? ` · ${selected.sessao.numero}` : ""}
          </span>
        }
        aside={
          <a href={selected.fonte} target="_blank" rel="noreferrer" className="btn !h-7 !px-2 text-[10px]">
            {CASA.fonteVotacao}
          </a>
        }
      >
        <div className="grid grid-cols-[minmax(0,1fr)_260px] gap-8">
          <div>
            <p className="serif text-[15px] leading-6 text-ink">{(detalhe?.proposicao.ementa ?? selected.proposicao.ementa).toLowerCase().replace(/^\w/, (c) => c.toUpperCase())}</p>
            <p className="mt-2 text-[11px] tracking-[0.08em] text-ash">
              {selected.proposicao.autores.map(cleanAuthor).join(", ")}
              {selected.sessao?.tipo ? ` · ${selected.sessao.tipo}` : ""}
              {selected.sessao?.fase ? ` · ${selected.sessao.fase}` : ""}
            </p>
            {detalhe?.resultado_frase ? <p className="mt-2 text-[12px] leading-5 text-sumi">“{detalhe.resultado_frase.replace(/^O SR\. PRESIDENTE \([^)]*\)\s*[–-]\s*/, "").replace(/^A SRA\. PRESIDENTE \([^)]*\)\s*[–-]\s*/, "")}”</p> : null}
          </div>
          <div>
            <Stat label="Resultado" value={<span className={resultadoClass(selected)}>{resultadoLabel(selected)}</span>} />
            <Stat label="Em votação" value={objetoLabel(selected.objeto)} />
            <Stat label="Sim" value={selected.contagem.sim} />
            <Stat label="Não" value={selected.contagem.nao} />
            <Stat label="Abstenções" value={selected.contagem.abstencao} />
            <Stat label="Presentes e votando" value={selected.contagem.presentes_votando ?? "–"} />
          </div>
        </div>
      </Panel>

      <div className={`grid min-h-0 gap-2 ${HAS_OBSTRUCAO ? "grid-cols-[330px_minmax(0,1fr)]" : "grid-cols-[300px_minmax(0,1fr)]"}`}>
        <Panel title={<b>Por partido</b>} flush fill>
          <table className="ruled ruled--tight">
            <thead>
              <tr>
                <th>Partido</th>
                <th className="right">Sim</th>
                <th className="right">Não</th>
                <th className="right">Abst.</th>
                {HAS_OBSTRUCAO ? <th className="right">Obstr.</th> : null}
              </tr>
            </thead>
            <tbody>
              {partidos.map((row) => (
                <tr key={row.partido}>
                  <td>{row.partido}</td>
                  <td className="num right voto-sim">{row.sim || ""}</td>
                  <td className="num right voto-nao">{row.nao || ""}</td>
                  <td className="num right faint">{row.abstencao || ""}</td>
                  {HAS_OBSTRUCAO ? <td className="num right faint">{row.obstrucao || ""}</td> : null}
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel title={<b>Votos</b>} flush fill>
          {!votos ? (
            <EmptyState>CARREGANDO</EmptyState>
          ) : (
            <div className="grid min-h-full divide-x divide-line" style={{ gridTemplateColumns: grupos.map((grupo) => `minmax(${grupos.length > 4 ? 84 : 120}px, ${Math.max(1, Math.min(grupo.ids.length, 12))}fr)`).join(" ") }}>
              {grupos.map((grupo) => (
                <div key={grupo.voto}>
                  <div className={`sticky top-0 border-b border-line bg-paper px-3 py-1.5 text-[10px] uppercase ${grupos.length > 4 ? "tracking-[0.08em]" : "whitespace-nowrap tracking-[0.18em]"} ${grupo.voto === "sim" ? "voto-sim" : grupo.voto === "nao" ? "voto-nao" : "text-ash"}`}>
                    {grupo.voto === "ausente" ? "Ausentes" : grupos.length > 4 ? SHORT_LABELS[grupo.voto] ?? VOTO_LABELS[grupo.voto] : VOTO_LABELS[grupo.voto]} · {grupo.ids.length}
                  </div>
                  <ul className="text-[11.5px] leading-5">
                    {grupo.ids.map((id) => {
                      const deputado = deputados.get(id);
                      return (
                        <li key={id} className="whitespace-normal px-3">
                          <Link href={`/?v=${encodeURIComponent(id)}`} className="text-ink hover:underline hover:underline-offset-4">
                            {deputado ? displayName(deputado) : id}
                          </Link>
                          <span className="ml-1.5 text-[10px] tracking-[0.08em] text-ash">
                            {deputado?.partido}
                            {votos[id] === "presidindo" ? " · presidindo" : ""}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </Screen>
  );
}

