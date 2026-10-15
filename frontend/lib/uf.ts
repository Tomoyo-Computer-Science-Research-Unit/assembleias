/**
 * O que muda de uma Assembleia para outra: nomes, textos curtos e rótulos dos tipos de proposição.
 * As telas, os painéis e os componentes são os mesmos; cada build carrega os dados de uma casa
 * (NEXT_PUBLIC_UF, "RJ" padrão) e só este módulo sabe qual é.
 */

import casasFile from "@/data/casas.json";

/** Sigla da UF; uma Assembleia por UF. */
export type Uf = string;
export type Casa = { uf: Uf; slug: string; sigla: string; estado: string; nome: string; root: boolean; href: string };

const LIST = (casasFile as { casas: Array<{ uf: string; slug: string; sigla: string; estado: string; root?: boolean }> }).casas;
const ROOT_CASA = LIST.find((item) => item.root) ?? LIST[0];
const wanted = (process.env.NEXT_PUBLIC_UF ?? ROOT_CASA.uf).toUpperCase();
const CURRENT = LIST.find((item) => item.uf.toUpperCase() === wanted) ?? ROOT_CASA;

export const UF: Uf = CURRENT.uf.toUpperCase();

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

/** Raiz comum das casas: "/assembleias" em produção, "" nos testes. A casa raiz mora nela; as demais em <raiz>/<slug>. */
export const SITE_ROOT = CURRENT.root ? BASE_PATH : BASE_PATH.replace(new RegExp(`/${CURRENT.slug}$`), "");

/** Assembleias publicadas, na ordem de frontend/data/casas.json. O rótulo do seletor é "ALERJ · Rio de Janeiro". */
export const CASAS: Casa[] = LIST.map((item) => ({
  uf: item.uf.toUpperCase(),
  slug: item.slug,
  sigla: item.sigla,
  estado: item.estado,
  nome: `${item.sigla} · ${item.estado}`,
  root: Boolean(item.root),
  href: item.root ? `${SITE_ROOT}/` : `${SITE_ROOT}/${item.slug}/`
}));

/** Mesma tela noutra casa (a seleção de deputado ou votação não se transfere). */
export function casaHref(casa: Casa, pathname: string): string {
  const rest = pathname.replace(/^\/+|\/+$/g, "");
  return rest ? `${casa.href}${rest}/` : casa.href;
}

/** A próxima casa da lista (tecla u). */
export function nextCasaHref(pathname: string): string {
  const index = CASAS.findIndex((item) => item.uf === UF);
  return casaHref(CASAS[(index + 1) % CASAS.length], pathname);
}

type CasaConfig = {
  estado: string;
  camara: string;
  /** Rótulo curto da barra de status. */
  camaraCurta: string;
  description: string;
  keywords: string[];
  /** Botão que abre a fonte de uma votação. */
  fonteVotacao: string;
  tipoLabels: Record<string, string>;
};

const RJ: CasaConfig = {
  estado: "Rio de Janeiro",
  camara: "Assembleia Legislativa do Estado do Rio de Janeiro",
  camaraCurta: "ALERJ",
  description:
    "Assembleia Legislativa do Estado do Rio de Janeiro: votações nominais, presença em plenário e proposições de cada deputado estadual, extraídas dos sistemas públicos da ALERJ.",
  keywords: ["Rio de Janeiro", "ALERJ", "Assembleia Legislativa", "deputados estaduais", "votações nominais", "presença", "dados públicos"],
  fonteVotacao: "Fonte",
  tipoLabels: {
    PL: "Projeto de lei",
    PLC: "Projeto de lei complementar",
    PDL: "Projeto de decreto legislativo",
    PR: "Projeto de resolução",
    PEC: "Proposta de emenda constitucional",
    IND: "Indicação",
    REQ: "Requerimento",
    MOC: "Moção",
    EMD: "Emenda"
  }
};

const SP: CasaConfig = {
  estado: "São Paulo",
  camara: "Assembleia Legislativa do Estado de São Paulo",
  camaraCurta: "ALESP",
  description:
    "Assembleia Legislativa do Estado de São Paulo: votações nominais, presença em plenário e proposições de cada deputado estadual, a partir dos relatórios do painel de votação e dos dados abertos da ALESP.",
  keywords: ["São Paulo", "ALESP", "Assembleia Legislativa", "deputados estaduais", "votações nominais", "presença", "dados abertos"],
  fonteVotacao: "Painel",
  tipoLabels: {
    PL: "Projeto de lei",
    PLC: "Projeto de lei complementar",
    PDL: "Projeto de decreto legislativo",
    PR: "Projeto de resolução",
    PEC: "Proposta de emenda à Constituição",
    IND: "Indicação",
    REQ: "Requerimento",
    RI: "Requerimento de informação",
    MOC: "Moção"
  }
};

/** Textos de cada casa; uma casa nova em casas.json precisa da sua entrada aqui. */
const TEXTS: Record<string, CasaConfig> = { RJ, SP };

export const CASA: CasaConfig = TEXTS[UF] ?? RJ;
