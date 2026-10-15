/** Texto da página Método, por casa. Os números vêm dos dados do build. */
import { formatInt } from "@/lib/static-api";
import { UF } from "@/lib/uf";

export type MethodContext = { generated: string; votacoes: number; semResultado: number; stats: Record<string, unknown> };
export type MethodSection = { title: string; body: string };

function num(stats: Record<string, unknown>, path: string): number {
  let value: unknown = stats;
  for (const key of path.split(".")) {
    value = value && typeof value === "object" ? (value as Record<string, unknown>)[key] : undefined;
  }
  return typeof value === "number" ? value : 0;
}

function str(stats: Record<string, unknown>, path: string): string {
  let value: unknown = stats;
  for (const key of path.split(".")) {
    value = value && typeof value === "object" ? (value as Record<string, unknown>)[key] : undefined;
  }
  return typeof value === "string" ? value : "";
}

function mes(value: string): string {
  return value ? `${value.slice(5, 7)}/${value.slice(0, 4)}` : "–";
}

function rj(ctx: MethodContext): MethodSection[] {
  const s = ctx.stats;
  return [
    {
      title: "Fontes",
      body: `A ALERJ não publica dados abertos da atividade legislativa nem o registro do painel de votação. Este site lê a lista de deputados de cada legislatura e o perfil de cada um no site alerj.rj.gov.br, a tabela mensal de presenças e as proposições nas bases Lotus Domino de alerjln1.alerj.rj.gov.br, e o Diário Oficial do Estado, Parte II (Poder Legislativo), no site da Imprensa Oficial. Nenhuma dessas fontes traz um código do deputado em comum com as outras: a ligação é feita pelo nome, com uma tabela de grafias mantida no código. Última leitura: ${ctx.generated}.`
    },
    {
      title: "Votações nominais",
      body: `Os sistemas da ALERJ guardam só o placar das votações no painel. Os nomes aparecem na ata de cada sessão, impressa no Diário Oficial: “Votaram “sim” os Senhores Deputados: …”, seguido dos que votaram “não”, das abstenções e dos totais. O site leu ${formatInt(num(s, "votacoes.edicoes_do_lidas"))} edições da Parte II desde fevereiro de 2019, achou ${formatInt(num(s, "votacoes.atas_de_sessao"))} atas de sessão plenária e ${formatInt(num(s, "votacoes.listas_nominais"))} listas nominais. Cada lista é conferida contra os totais impressos logo depois dela; ${formatInt(num(s, "votacoes.fora_por_divergir_da_contagem"))} não bateram e ficaram de fora, e ${formatInt(num(s, "votacoes.sem_contagem_impressa"))} entraram sem total impresso para conferir. Outras ${formatInt(num(s, "votacoes.so_com_totais"))} votações nominais aparecem na ata só com o placar, sem nomes, e não entram. Das ${formatInt(ctx.votacoes)} votações publicadas aqui, ${formatInt(ctx.semResultado)} ficaram sem resultado reconhecido na frase que segue os totais.`
    },
    {
      title: "Ausência nas votações",
      body: `A ata não lista quem deixou de votar. Ausente numa votação é o deputado que consta da tabela de presenças do mês da sessão e não está em nenhuma das listas; quando o mês não tem tabela (recesso de julho, janeiro), vale a do último mês publicado. Quem presidia a sessão, nomeado na ata como “O SR. PRESIDENTE (…)”, aparece como presidindo quando não votou.`
    },
    {
      title: "Presença",
      body: `A ALERJ publica uma tabela por mês com as faltas de cada deputado às sessões deliberativas e os dias das faltas. A tabela não distingue falta justificada de não justificada; todas contam como faltas aqui. Foram lidas ${formatInt(num(s, "presenca.tabelas_mensais"))} tabelas, de ${mes(str(s, "presenca.primeiro_mes"))} a ${mes(str(s, "presenca.ultimo_mes"))}, somando ${formatInt(num(s, "presenca.sessoes_deliberativas"))} sessões deliberativas. Não há tabela de agosto, mês seguinte ao recesso de julho; a tabela de cada mês sai no mês seguinte.`
    },
    {
      title: "Proposições",
      body: `Projetos de lei, de lei complementar, de decreto legislativo e de resolução, propostas de emenda à Constituição, indicações, moções e requerimentos de informação vêm das bases de proposições de cada legislatura (scpro1923 e scpro2327), lidas por busca de texto no código da proposição. O autor vem como texto; ${formatInt(num(s, "proposicoes.sem_autor_deputado"))} proposições ficaram sem autor reconhecido, quase todas do Poder Executivo, da Mesa ou de comissões.`
    },
    {
      title: "O que não dá para dizer",
      body: `Votações simbólicas, que são a maioria, não têm voto individual. Erros de digitação da ata passam para o site: um nome que a ata repete nas duas listas ou deixa de fora derruba a conferência e a votação sai. O partido de cada deputado é o do histórico de filiação do perfil na data de fim da legislatura, ou de hoje na legislatura atual.`
    },
    { title: "Código", body: "ETL em Python e site estático em Next.js, no repositório da Tomoyo; cada download tem o checksum guardado." }
  ];
}

function sp(ctx: MethodContext): MethodSection[] {
  const s = ctx.stats;
  return [
    {
      title: "Fontes",
      body: `A ALESP publica dados abertos de proposições e autores e mantém, no portal, a lista das votações feitas no painel eletrônico e a presença em plenário de cada deputado. Este site lê a página Votações no Plenário, o relatório em PDF de cada votação, a API do portal que alimenta a página Presença em Plenário e os detalhes de cada deputado (filiações, mandatos, foto), e os arquivos proposituras e documento_autor do portal de dados abertos. Presença, proposições e cadastro trazem o código do deputado; os relatórios de votação trazem só o nome impresso no painel. Última leitura: ${ctx.generated}.`
    },
    {
      title: "Votações nominais",
      body: `Cada relatório de verificação de votação traz os 94 assentos com partido e voto: sim, não, abstenção, obstrução, licenciado ou nenhum registro, e os totais. Foram lidas ${formatInt(ctx.votacoes)} votações de março de 2019 até a última leitura. Outras ${formatInt(num(s, "votacoes.escolhas_fora"))} da mesma lista são eleições da Mesa e escolhas de método de votação, impressas como grade de opções (1, 2, a) e não como sim ou não; ficam de fora. O nome do painel é ligado ao cadastro dentro da legislatura da votação, por palavras e iniciais (“LUIZ C. MARCOLINO”), com uma tabela de apelidos para nomes antigos. ${num(s, "votacoes.impresso_discrepancies") ? `Em ${formatInt(num(s, "votacoes.impresso_discrepancies"))} casos a contagem impressa difere da lista de nomes; a contagem do site é a da lista.` : "Em todas elas a lista de nomes bate com a contagem impressa."} Quando o relatório não imprime resultado e o total fica abaixo de ${formatInt(48)} votos, a votação conta como sem quórum (${formatInt(num(s, "votacoes.sem_quorum_inferido"))} casos).`
    },
    {
      title: "Obstrução e ausência",
      body: `Obstrução é a marca do painel para o deputado de partido em obstrução: está no plenário, não vota e não conta para o quórum. No site ela conta como mandato em exercício e não como voto, e não entra na conta de votos contra o partido. Ausente é o assento sem voto registrado, exceto o do presidente da sessão, marcado “P” no relatório, que aparece como presidindo. Licenciado não conta.`
    },
    {
      title: "Presença",
      body: `A presença vem sessão a sessão, como o portal a mostra: presente, falta não justificada, falta justificada, ausência em sessão extraordinária e sessão não deliberativa. Faltas do mês são as não justificadas mais as ausências em sessões extraordinárias; abonadas são as justificadas e licenças; sessões não deliberativas não contam. Foram consultados ${formatInt(num(s, "presenca.meses_consultados"))} meses de mandato, de ${mes(str(s, "presenca.primeiro_mes"))} a ${mes(str(s, "presenca.ultimo_mes"))}, em ${formatInt(num(s, "presenca.sessoes"))} sessões. O portal não traz dados de alguns meses (abril e maio de 2020, durante as sessões remotas); esses meses ficam vazios.`
    },
    {
      title: "Proposições",
      body: `Projetos de lei, de lei complementar, de decreto legislativo e de resolução, propostas de emenda à Constituição, indicações, moções e requerimentos de informação vêm dos dados abertos, com o código de cada autor, a partir de 2019. Os requerimentos comuns, perto de dois mil por ano, ficam de fora.`
    },
    {
      title: "O que não dá para dizer",
      body: `Votações simbólicas não têm voto individual; os relatórios existem só para votações no painel. O partido numa votação é o da filiação do deputado naquele dia, segundo o cadastro da ALESP; desde 2022 o painel imprime a federação no lugar do partido. Na lista de deputados vale a filiação na data de fim da legislatura, ou de hoje na atual. Alguns deputados não constam do cadastro do portal e aparecem só com o nome do painel, sem presença nem proposições.`
    },
    { title: "Código", body: "ETL em Python e site estático em Next.js, no repositório da Tomoyo; cada download tem o checksum guardado." }
  ];
}

export function methodSections(ctx: MethodContext): MethodSection[] {
  const builders: Record<string, (ctx: MethodContext) => MethodSection[]> = { RJ: rj, SP: sp };
  return (builders[UF] ?? rj)(ctx);
}
