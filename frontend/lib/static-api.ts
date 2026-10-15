/**
 * Camada de dados do site. O núcleo (`static-data.generated.json`) traz deputados com seus
 * agregados, a lista de votações nominais com contagens e a cobertura; os votos de cada votação
 * e a lista de votos e proposições de cada deputado vêm em arquivos sob demanda.
 */

import snapshot from "@/lib/static-data.generated.json";
import { CASA } from "@/lib/uf";

export type Voto = "sim" | "nao" | "abstencao" | "obstrucao" | "ausente" | "presidindo";
export type VotoTotais = Partial<Record<Voto, number>>;
export type PresencaMes = { faltas: number; abonadas: number; total: number };
export type PresencaAno = PresencaMes & { meses: number };
export type Deputado = {
  id: string;
  nome: string;
  nome_parlamentar: string | null;
  partido: string | null;
  partidos_por_legislatura: Record<string, string>;
  legislaturas: number[];
  situacao: string | null;
  foto: string | null;
  gabinete?: string | null;
  email?: string | null;
  perfil_url?: string | null;
  presenca: { por_ano: Record<string, PresencaAno>; por_mes: Record<string, PresencaMes> };
  votos: { por_legislatura: Record<string, VotoTotais>; por_ano: Record<string, VotoTotais>; total?: VotoTotais };
  participacao: number | null;
  com_maioria: number | null;
  contra_partido: number | null;
  proposicoes_por_tipo: Record<string, Record<string, number>>;
  totais?: Record<string, number>;
};
export type Contagem = { sim: number; nao: number; abstencao: number; presentes_votando: number | null };
export type Votacao = {
  id: string;
  data: string;
  hora: string | null;
  sessao: { tipo: string | null; numero: string | null; fase: string | null } | null;
  proposicao: { id: string; tipo: string; numero: string; ano: number; ementa: string; autores: string[]; autores_ids?: string[] };
  /** O que foi a voto: veto, emenda, projeto, redacao_final, substitutivo. */
  objeto?: string | null;
  resultado: string | null;
  contagem: Contagem;
  lado_vencedor: Voto | null;
  por_partido: Record<string, VotoTotais>;
  fonte: string;
  /** Assunto como o painel o imprime; usado no título quando o voto não é sobre o texto de uma proposição. */
  titulo?: string;
};
export type Legislatura = { numero: number; inicio: string; fim: string };
export type Coverage = Record<string, unknown>;
export type Source = { name: string; url: string; accessed_at?: string; count?: number };
type Core = {
  generated_at: string;
  legislaturas: Legislatura[];
  deputados: Deputado[];
  votacoes: Votacao[];
  presenca_meses: string[];
  stats: Coverage;
  sources: Source[];
};
export type VotoLinha = { votacao_id: string; voto: Voto };
export type ProposicaoLinha = { id: string; tipo: string; numero: string; ano: number; ementa: string; data: string | null };
export type DeputadoDetalhe = { votos: VotoLinha[]; proposicoes: ProposicaoLinha[] };

const DATA = snapshot as unknown as Core;

export const VOTO_LABELS: Record<Voto, string> = { sim: "Sim", nao: "Não", abstencao: "Abstenção", obstrucao: "Obstrução", ausente: "Ausente", presidindo: "Presidindo" };

/** A casa registra obstrução no painel (São Paulo); sem ela, a coluna e o filtro de obstrução não aparecem. */
export const HAS_OBSTRUCAO: boolean = DATA.votacoes.some((item) => Object.values(item.por_partido ?? {}).some((totais) => (totais.obstrucao ?? 0) > 0));
export const TIPO_LABELS: Record<string, string> = CASA.tipoLabels;

/** "Veto ao PL-1861/2026", "Emenda ao PL-…", "PL-…": o que estava em votação, não só a proposição. */
export function votacaoTitle(votacao: Pick<Votacao, "objeto" | "proposicao" | "titulo">): string {
  const prefix: Record<string, string> = { veto: "Veto ao", emenda: "Emenda ao", redacao_final: "Redação final do", substitutivo: "Substitutivo ao" };
  const head = prefix[votacao.objeto ?? ""];
  const onText = head !== undefined || votacao.objeto === "projeto" || !votacao.objeto;
  if (votacao.titulo && (!votacao.proposicao.id || !onText)) {
    return votacao.titulo;
  }
  return head ? `${head} ${votacao.proposicao.id}` : votacao.proposicao.id;
}

/** "Em votação": o que a votação decidia. */
export const OBJETO_LABELS: Record<string, string> = {
  veto: "veto do governador",
  emenda: "emenda",
  redacao_final: "redação final",
  substitutivo: "substitutivo",
  requerimento: "requerimento",
  eleicao: "eleição da Mesa",
  contas: "parecer sobre contas",
  parecer: "parecer"
};
export function objetoLabel(objeto: string | null | undefined): string {
  return OBJETO_LABELS[objeto ?? ""] ?? "o projeto";
}

/** Resultado lido com o objeto: num veto, "não" derruba o veto e o projeto segue. */
export function resultadoLabel(votacao: Pick<Votacao, "objeto" | "resultado">): string {
  const key = `${votacao.objeto ?? ""}:${votacao.resultado ?? ""}`;
  const labels: Record<string, string> = {
    "veto:derrubado": "veto derrubado, projeto segue",
    "veto:mantido": "veto mantido",
    "veto:rejeitado": "veto derrubado, projeto segue",
    "veto:sem_quorum": "sem quórum",
    "emenda:aprovado": "emenda aprovada",
    "emenda:rejeitado": "emenda rejeitada",
    "emenda:prejudicado": "emenda prejudicada",
    "emenda:sem_quorum": "sem quórum",
    "projeto:aprovado": "aprovado",
    "projeto:rejeitado": "rejeitado",
    "projeto:prejudicado": "prejudicado",
    "projeto:sem_quorum": "sem quórum",
    "redacao_final:aprovado": "redação final aprovada",
    "substitutivo:aprovado": "substitutivo aprovado",
    "substitutivo:rejeitado": "substitutivo rejeitado",
    "projeto:pendente": "sem quórum, volta à pauta",
    "emenda:pendente": "sem quórum, volta à pauta",
    "substitutivo:pendente": "sem quórum, volta à pauta",
    "requerimento:pendente": "sem quórum",
    "requerimento:sem_quorum": "sem quórum",
    "eleicao:eleito": "eleito"
  };
  return labels[key] ?? (votacao.resultado ? votacao.resultado.replace(/_/g, " ") : "não detectado");
}

/** Lado favorável à proposição: num veto é o "não" (contra o veto). */
export function resultadoClass(votacao: Pick<Votacao, "objeto" | "resultado">): string {
  const good = (votacao.objeto === "veto" && (votacao.resultado === "derrubado" || votacao.resultado === "rejeitado")) || (votacao.objeto !== "veto" && votacao.resultado === "aprovado");
  const bad = (votacao.objeto === "veto" && votacao.resultado === "mantido") || (votacao.objeto !== "veto" && votacao.resultado === "rejeitado");
  return good ? "voto-sim" : bad ? "voto-nao" : "faint";
}

export function getMeta() {
  return { generated_at: DATA.generated_at, legislaturas: DATA.legislaturas, stats: DATA.stats, sources: DATA.sources, presenca_meses: DATA.presenca_meses ?? [] };
}
export function getLegislaturas(): Legislatura[] {
  return DATA.legislaturas;
}
export function getDeputados(): Deputado[] {
  return DATA.deputados;
}
export function getDeputado(id: string): Deputado | undefined {
  return DATA.deputados.find((item) => item.id === id);
}
export function getVotacoes(): Votacao[] {
  return DATA.votacoes;
}
export function getVotacao(id: string): Votacao | undefined {
  return DATA.votacoes.find((item) => item.id === id);
}
export function getStats(): Coverage {
  return DATA.stats;
}
export function getSources(): Source[] {
  return DATA.sources;
}

/** Anos com presença apurada, do mais recente ao mais antigo. */
export function presencaYears(): number[] {
  const years = new Set<number>();
  for (const deputado of DATA.deputados) {
    for (const key of Object.keys(deputado.presenca?.por_ano ?? {})) {
      years.add(Number(key));
    }
  }
  return [...years].sort((a, b) => b - a);
}

export function currentLegislatura(): Legislatura {
  return DATA.legislaturas[DATA.legislaturas.length - 1];
}

export function displayName(deputado: Pick<Deputado, "nome" | "nome_parlamentar">): string {
  return deputado.nome_parlamentar || deputado.nome;
}

export function sumVotos(totais: VotoTotais | undefined): number {
  return totais ? Object.values(totais).reduce((sum, value) => sum + (value ?? 0), 0) : 0;
}

export function formatPct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "–";
  }
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value * 100)}%`;
}

export function formatInt(value: number | null | undefined): string {
  return value === null || value === undefined ? "–" : new Intl.NumberFormat("pt-BR").format(value);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "–";
  }
  const [year, month, day] = value.split("-");
  return `${day}/${month}/${year}`;
}

export function fileId(id: string): string {
  return id.replace(/[:/]/g, "-");
}

/** Mesma lógica do ETL: Deputado(a) Fulano -> Fulano em caixa normal. */
export function cleanAuthor(value: string): string {
  return value
    .replace(/^DEPUTAD[OA]\s+/i, "")
    .toLowerCase()
    .replace(/(^|\s)(\S)/g, (match) => match.toUpperCase())
    .replace(/\b(De|Da|Do|Das|Dos|E)\b/g, (match) => match.toLowerCase());
}

// --- Arquivos sob demanda ------------------------------------------------------------------

const votosCache = new Map<string, Record<string, Voto>>();
const detalheCache = new Map<string, DeputadoDetalhe>();

export type VotacaoDetalhe = Votacao & { votos: Record<string, Voto>; resultado_frase?: string | null; presidente?: string | null; roster_mes?: string | null };
const detalheVotacaoCache = new Map<string, VotacaoDetalhe | null>();

/** Arquivo da votação: votos por deputado e a ementa completa (o núcleo só leva um resumo). */
export async function loadVotacao(votacaoId: string): Promise<VotacaoDetalhe | null> {
  if (detalheVotacaoCache.has(votacaoId)) {
    return detalheVotacaoCache.get(votacaoId) ?? null;
  }
  try {
    const module = (await import(`@/lib/static-votacoes/${fileId(votacaoId)}.generated.json`)) as { default?: VotacaoDetalhe };
    const detalhe = (module.default ?? module) as VotacaoDetalhe;
    detalheVotacaoCache.set(votacaoId, detalhe);
    return detalhe;
  } catch {
    detalheVotacaoCache.set(votacaoId, null);
    return null;
  }
}

export async function loadVotos(votacaoId: string): Promise<Record<string, Voto>> {
  const cached = votosCache.get(votacaoId);
  if (cached) {
    return cached;
  }
  const detalhe = await loadVotacao(votacaoId);
  const votos = detalhe?.votos ?? {};
  votosCache.set(votacaoId, votos);
  return votos;
}

export async function loadDeputado(id: string): Promise<DeputadoDetalhe> {
  const cached = detalheCache.get(id);
  if (cached) {
    return cached;
  }
  try {
    const module = (await import(`@/lib/static-deputados/${fileId(id)}.generated.json`)) as { default?: DeputadoDetalhe };
    const detalhe = (module.default ?? module) as DeputadoDetalhe;
    detalheCache.set(id, detalhe);
    return detalhe;
  } catch {
    const empty = { votos: [], proposicoes: [] };
    detalheCache.set(id, empty);
    return empty;
  }
}
