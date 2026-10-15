"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { BarList } from "@/components/BarList";
import { useScreenHotkeys } from "@/components/Hotkeys";
import { EmptyState, Panel, Screen, Stat } from "@/components/ui";
import { currentLegislatura, displayName, formatInt, formatPct, getDeputados, getVotacoes, votacaoTitle, type Deputado, type Votacao } from "@/lib/static-api";

type Partido = {
  sigla: string;
  membros: Deputado[];
  coesao: number | null;
  votacoesComVoto: number;
  faltas: number;
  participacao: number | null;
  comMaioria: number | null;
  menosCoesas: Array<{ votacao: Votacao; unanimidade: number; placar: string }>;
};

function partyOf(deputado: Deputado, leg: string): string | null {
  return deputado.partidos_por_legislatura?.[leg] ?? deputado.partido;
}

function mean(values: Array<number | null | undefined>): number | null {
  const valid = values.filter((value): value is number => value !== null && value !== undefined && Number.isFinite(value));
  return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : null;
}

export function PartidosScreen() {
  const leg = currentLegislatura();
  const legKey = String(leg.numero);
  const legStart = Number(leg.inicio.slice(0, 4));
  const partidos = useMemo<Partido[]>(() => {
    const byParty = new Map<string, Deputado[]>();
    for (const deputado of getDeputados()) {
      if (!deputado.legislaturas.includes(leg.numero)) {
        continue;
      }
      const sigla = partyOf(deputado, legKey);
      if (!sigla) {
        continue;
      }
      byParty.set(sigla, [...(byParty.get(sigla) ?? []), deputado]);
    }
    const votacoes = getVotacoes().filter((item) => Number(item.data.slice(0, 4)) >= legStart);
    return [...byParty.entries()]
      .map(([sigla, membros]) => {
        const scores: Array<{ votacao: Votacao; unanimidade: number; placar: string }> = [];
        for (const votacao of votacoes) {
          const totais = votacao.por_partido?.[sigla];
          if (!totais) {
            continue;
          }
          const sim = totais.sim ?? 0;
          const nao = totais.nao ?? 0;
          const abst = totais.abstencao ?? 0;
          const total = sim + nao + abst;
          if (total < 2) {
            continue;
          }
          scores.push({ votacao, unanimidade: Math.max(sim, nao, abst) / total, placar: `${sim}–${nao}${abst ? `–${abst}` : ""}` });
        }
        const faltas = membros.reduce((sum, deputado) => {
          return (
            sum +
            Object.entries(deputado.presenca?.por_ano ?? {})
              .filter(([year]) => Number(year) >= legStart)
              .reduce((inner, [, row]) => inner + (row?.total ?? 0), 0)
          );
        }, 0);
        return {
          sigla,
          membros: membros.sort((a, b) => displayName(a).localeCompare(displayName(b), "pt-BR")),
          coesao: mean(scores.map((score) => score.unanimidade)),
          votacoesComVoto: scores.length,
          faltas,
          participacao: mean(membros.map((deputado) => deputado.participacao)),
          comMaioria: mean(membros.map((deputado) => deputado.com_maioria)),
          menosCoesas: scores.sort((a, b) => a.unanimidade - b.unanimidade).slice(0, 8)
        };
      })
      .sort((a, b) => b.membros.length - a.membros.length || a.sigla.localeCompare(b.sigla));
  }, [leg.numero, legKey, legStart]);

  const [selectedSigla, setSelectedSigla] = useState(partidos[0]?.sigla ?? "");
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    const sigla = new URLSearchParams(window.location.search).get("p");
    if (sigla && partidos.some((item) => item.sigla === sigla)) {
      setSelectedSigla(sigla);
    }
    setHydrated(true);
  }, [partidos]);
  useEffect(() => {
    if (hydrated) {
      window.history.replaceState(null, "", `${window.location.pathname}?p=${encodeURIComponent(selectedSigla)}`);
    }
  }, [hydrated, selectedSigla]);

  const selected = partidos.find((item) => item.sigla === selectedSigla) ?? partidos[0];
  const index = Math.max(0, partidos.findIndex((item) => item.sigla === selected?.sigla));
  const hotkeys = useMemo(
    () => ({
      ArrowUp: () => setSelectedSigla(partidos[(index - 1 + partidos.length) % partidos.length]?.sigla ?? selectedSigla),
      ArrowDown: () => setSelectedSigla(partidos[(index + 1) % partidos.length]?.sigla ?? selectedSigla)
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [index, partidos, selectedSigla]
  );
  useScreenHotkeys(hotkeys);

  if (!selected) {
    return <EmptyState>SEM PARTIDOS</EmptyState>;
  }

  return (
    <Screen columns="300px minmax(0, 1fr) minmax(0, 1fr)" rows="auto minmax(0, 1fr)">
      <Panel title={<b>Partidos</b>} flush fill style={{ gridRow: "1 / span 2" }}>
        <ul className="menu" role="listbox" aria-label="Partidos">
          {partidos.map((partido) => (
            <li key={partido.sigla} role="presentation">
              <button type="button" role="option" aria-selected={partido.sigla === selected.sigla} onClick={() => setSelectedSigla(partido.sigla)}>
                <span>
                  {partido.sigla}
                  <span className="faint ml-1.5 text-[10px] tracking-[0.08em]">{partido.membros.length}</span>
                </span>
                <span className="num">{formatPct(partido.coesao)}</span>
              </button>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title={<b>{selected.sigla}</b>} style={{ gridColumn: "2 / span 2" }}>
        <div className="grid grid-cols-2 gap-x-8">
          <div>
            <Stat label="Deputados na legislatura" value={formatInt(selected.membros.length)} />
            <Stat label="Coesão nas votações nominais" value={formatPct(selected.coesao)} sub={`${formatInt(selected.votacoesComVoto)} votações`} />
            <Stat label="Votaram com a maioria do plenário" value={formatPct(selected.comMaioria)} sub="média" />
          </div>
          <div>
            <Stat label="Participação nas votações" value={formatPct(selected.participacao)} sub="média" />
            <Stat label="Faltas em plenário na legislatura" value={formatInt(selected.faltas)} sub="soma" />
          </div>
        </div>
      </Panel>

      <Panel title={<b>Deputados</b>} flush fill>
        <BarList
          rows={selected.membros.map((deputado) => ({
            key: deputado.id,
            label: displayName(deputado),
            sub: deputado.situacao === "em_exercicio" ? undefined : deputado.situacao?.replace(/_/g, " "),
            value: deputado.com_maioria ?? 0,
            href: `/?v=${encodeURIComponent(deputado.id)}`
          }))}
          max={1}
          format={(value) => formatPct(value)}
        />
      </Panel>
      <Panel title={<b>Votações em que o partido se dividiu</b>} flush fill>
        {selected.menosCoesas.length === 0 ? (
          <EmptyState>SEM VOTAÇÕES COM DOIS OU MAIS VOTANTES</EmptyState>
        ) : (
          <table className="ruled ruled--tight">
            <thead>
              <tr>
                <th>Em votação</th>
                <th>Data</th>
                <th className="right">Placar</th>
                <th className="right">Coesão</th>
              </tr>
            </thead>
            <tbody>
              {selected.menosCoesas.map(({ votacao, unanimidade, placar }) => (
                <tr key={votacao.id}>
                  <td>
                    <Link href={`/votacoes?v=${encodeURIComponent(votacao.id)}`} className="text-ink hover:underline hover:underline-offset-4">
                      {votacaoTitle(votacao)}
                    </Link>
                  </td>
                  <td className="num">{votacao.data.split("-").reverse().join("/")}</td>
                  <td className="num right">{placar}</td>
                  <td className="num right faint">{formatPct(unanimidade)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </Screen>
  );
}
