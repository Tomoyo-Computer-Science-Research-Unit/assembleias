# Assembleias: fontes, cobertura e ressalvas

Leitura de 14 e 15/10/2026. Período: legislaturas 2019–2023 e 2023–2027 (ALERJ 12ª e 13ª, desde
01/02/2019; ALESP 19ª e 20ª, desde 15/03/2019). Todos os downloads ficam em `data/raw/` com checksum;
1 pedido por segundo por servidor (a presença da ALESP usou dois pedidos simultâneos, abaixo de 1 por
segundo no total, porque a API responde em 2–3 s).

## ALESP (São Paulo)

### Fontes

| Dado | URL | Formato | Pedidos |
|---|---|---|---|
| Lista de votações no painel | `https://www.al.sp.gov.br/alesp/votacoes-no-plenario?anoSessao=<ano>` | HTML (latin-1) | 8 |
| Relatório de cada votação | `https://www.al.sp.gov.br/repositorio/ementario/votacoes/<...>.pdf` | PDF, 1 página | 410 |
| Parlamentares desde 1995, com legislaturas | `https://legis-api-portal-prd.al.sp.gov.br/lista-presenca-parlamentar/parlamentares/` | JSON | 1 |
| Meses de mandato de cada um | `.../lista-presenca-parlamentar/mesesAnosMandatosParlamentar/<idParlamentar>` | JSON | 153 |
| Presença por sessão no mês | `.../lista-presenca-parlamentar/<matrícula>/<mês>/<ano>` | JSON | 8.811 |
| Detalhes do deputado (idAutor, filiações com datas, mandatos, foto) | `.../parlamentar-portal/detalhes/<matrícula>` | JSON | 153 |
| Deputados em exercício (sala, e-mail) | `https://www.al.sp.gov.br/repositorioDados/deputados/deputados.xml` | XML | 1 |
| Proposituras | `.../repositorioDados/processo_legislativo/proposituras.zip` (132 MB de XML) | XML zipado | 1 |
| Autores | `.../processo_legislativo/documento_autor.zip` (145 MB de XML) | XML zipado | 1 |
| Naturezas | `.../processo_legislativo/naturezasSpl.xml` | XML | 1 |

O portal de dados abertos (`/dados-abertos/`, que anuncia migração para `ckan.al.sp.gov.br`, hoje com
cadeia TLS incompleta) tem 26 conjuntos. **Não há voto nominal de plenário nos dados abertos**: o
único conjunto de votações é `comissoes_permanentes_votacoes.xml` (comissões). O voto de plenário de
cada deputado está nos relatórios PDF do painel, listados na página Votações no Plenário (desde
2006). A presença em plenário também não está nos dados abertos (o serviço `/deputadoPresenca/` do
catálogo responde 500); vem da API que alimenta a página Presença em Plenário.

### Votos

- 410 relatórios de 15/03/2019 a 21/07/2026. 383 votações publicadas (2019: 63, 2020: 85, 2021: 73,
  2022: 36, 2023: 34, 2024: 42, 2025: 38, 2026: 12). As outras 27 são eleições da Mesa e escolhas de
  método de votação, impressas como grade de opções (1, 2, a, O), sem sim/não; ficam de fora.
- Cada relatório traz os 94 assentos: marca (L líder, P presidente, G governo), nome do painel,
  partido (ou federação, desde 2022) e voto: Sim, Não, Abstenção, Obstrução, Licenciado, `---`.
  Partidos longos invadem a coluna do voto; o voto é impresso 0,75 pt abaixo e é separado por isso
  (pdfplumber, coordenadas de caractere).
- Conferência: nas 383 a lista de nomes bate com os totais impressos (sim, não, abstenção).
- Votos lidos: 15.855 sim, 4.762 não, 127 abstenções, 11.748 obstruções, 2.259 ausentes (assento
  sem voto registrado), 323 presidindo. Obstrução é um valor novo no contrato de dados (`obstrucao`):
  conta como mandato em exercício e não como voto; a coluna e o filtro só aparecem quando a casa a
  registra.
- 142 relatórios não imprimem resultado; 138 deles têm total abaixo de 48 (maioria dos 94) e contam
  como sem quórum; 4 ficam sem resultado. Só 2 votações são de veto, ambas sem quórum.
- Nomes: o painel imprime o nome curto ("LUIZ C. MARCOLINO", "PAULA B. FEMINISTA"; em 2019, "LULA"
  dentro do nome de deputados do PT). Casamento por palavras, iniciais e abreviações dentro da
  legislatura, mais 5 apelidos conferidos na biografia do próprio deputado (Fabiana Barroso → Fabiana
  Bolsonaro, Marcio Giudicio → Marcio da Farmácia, Bancada/Mandata Ativista → Monica Seixas, Luiz
  Fernando Lula da Silva → Luiz Fernando T. Ferreira). Todos os nomes casaram. Patrícia Bezerra (19ª)
  não consta da API de parlamentares: entra só com o nome do painel, sem presença nem proposições.
- Partido na votação: a filiação do cadastro na data (o painel imprime a federação).

### Presença

- 8.811 meses de mandato consultados, 2.284 vazios; 161.500 marcas de sessão; 1.703 sessões
  (1.684 deliberativas), de 03/2019 a 08/2026.
- Marcas: Presente 75.769; Sessão não Deliberativa 56.844; Justificada 9.754; Ausência em Sessão
  Extraordinária 5.487; Dispensado(a) 4.037; Licença-Saúde 3.376; Em Comissão de Representação 1.806;
  Afastamento para cargo em comissão 1.783; Licença de interesse particular 1.398; Não Justificada 470;
  as demais com menos de 250.
- Regra do site: faltas = Não Justificada + Ausência em Sessão Extraordinária (5.957 no período);
  abonadas = justificadas, licenças e ausências a serviço da Casa (21.011); não contam sessões não
  deliberativas, afastamentos e punição de perda temporária do mandato. A ausência em sessão
  extraordinária é a maior parte das faltas; a ALESP a marca à parte da falta não justificada. Se a
  regra mudar, é uma linha em `parsers/alesp.py::presenca_status`.
- O portal não devolve sessões de abril a julho de 2020, de abril a agosto de 2021 e da maior parte
  dos janeiros e julhos.

### Proposições

104.521 desde 2019, com código de autor: indicações 86.468, PL 8.452, requerimentos de informação
5.612, moções 2.805, PLC 512, PDL 390, PR 224, PEC 58. Requerimentos comuns (16.728) ficam de fora.
664 sem autor deputado (Governador, Mesa, Tribunal de Justiça, comissões). O `IdAutor` dos dados
abertos é o `idAutor` da API de detalhes; um código de autor fora do cadastro (Alexandre Pereira,
313 proposições) casa pelo nome. Os arquivos por deputado (`static-deputados/`) somam 31 MB por causa
das indicações.

### Cadastro

154 deputados (153 da API mais 1 só do painel), 94 em exercício, 153 com foto.

## ALERJ (Rio de Janeiro)

### Fontes

| Dado | URL | Formato | Pedidos |
|---|---|---|---|
| Deputados por legislatura | `POST https://www.alerj.rj.gov.br/Deputados/QuemSao` (legislatura=19 ou 20, situacaoDeputado=1 ou 2) | HTML | 4 |
| Perfil (nome, e-mail, histórico de partidos com datas) | `https://www.alerj.rj.gov.br/Deputados/PerfilDeputado/<id>` | HTML | 138 |
| Fotos | `https://www.alerj.rj.gov.br/Uploads/PerfilDeputado/Imagem/...` | JPG | 138 |
| Presença mensal | `http://alerjln1.alerj.rj.gov.br/ordemdia.nsf/85ef985c696ead9083256cf50081437a` (view presint em JSON) e cada documento `?OpenDocument` | Domino JSON + HTML latin-1 | ~80 + 75 |
| Proposições | `http://alerjln1.alerj.rj.gov.br/scpro1923.nsf` e `scpro2327.nsf`: `<view>?SearchView&Query=FIELD prop_cod_prop CONTAINS <prefixo>*&SearchMax=0` | HTML | ~550 |
| Diário Oficial, calendário | `https://www.ioerj.com.br/portal/modules/conteudoonline/do_seleciona_data.php` | HTML | 1 |
| Edições do dia | `.../do_seleciona_edicao.php?data=<base64 AAAAMMDD>` | HTML | 1.887 |
| PDF da Parte II (Poder Legislativo) | `.../mostra_edicao.php?k=<GUID[:12]>P<GUID[12:]>` (GUID = base64 triplo do token da edição) | PDF, 1–3 MB | 2.273 |

A ALERJ não tem dados abertos nem página de painel. Seus sistemas (taqalerj.nsf, scpro*.nsf)
guardam só o placar das votações nominais. **Os nomes de quem votou sim e não estão só nas atas de
sessão publicadas no Diário Oficial, Parte II**: "Votaram “sim” os Senhores Deputados: …". O texto
dos PDFs é extraído com pdfium (ordem de leitura correta nas três colunas) e guardado comprimido em
`data/raw/www.ioerj.com.br/pdftext/` só para as edições com ata; o PDF não é guardado. A base
alerjln1 só responde por http; URLs com `Start=`/`Count=` derrubam a conexão, então as visões são
lidas com `StartKey` + `Expand`, e o JSON do Domino tem escapes inválidos que o parser remove.
www.alerj.rj.gov.br derruba conexões após rajadas; o ETL espera e repete.

### Votos

- 2.273 edições da Parte II de 01/02/2019 a 14/10/2026; 915 com ata de sessão plenária; 1.715 atas
  (22 repetidas em outra edição).
- 375 listas nominais com nomes. Cada lista é conferida contra os totais impressos logo depois dela,
  em vários formatos ("Totais: Votos “Sim”: 45", "Total de votos “não”: 39", "Totais de votos
  “sim”, 15; votos “não”, 39"). 236 conferem, 15 não têm total impresso e entram, **104 divergem e
  ficam de fora**. As divergências vêm do próprio Diário: lista com um nome a mais ou a menos que o
  total (ata de 23/09/2025: 40 nomes no "não" para 39 votos; ata de 26/03/2019: 50 para 49), deputado
  nas duas listas, total falado diferente do impresso.
- 251 votações publicadas: 2019: 95, 2020: 57, 2021: 24, 2022: 40, 2023: 10, 2024: 3, 2025: 19,
  2026: 3. Outras 61 votações nominais aparecem na ata só com o placar ("Votaram 60 Deputados: 57
  “sim” e 3 “não”"), sem nomes, e não entram.
- Votos: 8.608 sim, 3.962 não, 266 abstenções, 4.686 ausentes, 3 presidindo. Ausente = deputado da
  tabela de presença do mês (ou do último mês publicado) que não está em lista nenhuma; o presidente
  da sessão costuma constar das listas.
- Objeto: projeto 104, veto 78, emenda ou destaque 53, substitutivo 11, redação final 5. Resultado
  lido na frase seguinte ("Está rejeitado o Veto" → veto derrubado): aprovado 103, rejeitado 40, veto
  derrubado 36, veto mantido 29, prejudicado 1, sem resultado reconhecido 42.
- Proposição: a anunciada por último ("Anuncia-se a discussão … PROJETO DE LEI Nº …"); 30 votações
  sem proposição reconhecida (título "Votação nominal, <n>ª Sessão …"). Para projetos anteriores a
  2019 a ementa e o autor vêm do texto do anúncio.
- Nomes: o Diário traz nomes espaçados ("Léo Vi e i r a"), quebras de página no meio de palavras
  ("Ber- … PODER LEGISLATIVO … nardo") e vírgulas faltando ("Marcelo Dino Márcio Gualberto"); o
  parser corrige os dois primeiros e o casamento separa o terceiro. Restam 9 grafias sem casamento
  (ex.: "TH Joia", "Flavio Sefarini"), 1 a 3 ocorrências cada. 4 apelidos no código.

### Presença

75 tabelas mensais (02/2019 a 06/2026; janeiro não tem tabela, julho só em 2020), 5.231 linhas,
1.548 sessões deliberativas, 832 faltas. A tabela traz faltas e dias de falta por deputado, sem
distinguir justificadas; todas contam como faltas.

### Proposições

41.896 desde 2019: indicações 16.106, PL 14.956, moções 5.670, PR 4.522, requerimentos de
informação 305, PLC 136, PEC 111, PDL 90. Autor em texto, casado por nome; 373 sem deputado
reconhecido (Poder Executivo, Judiciário, comissões e "MARINA", nome que existe nas duas
legislaturas).

### Cadastro

138 deputados (12ª: 69 em exercício ao fim mais 25 que exerceram; 13ª: 70 mais 21), todos com foto.
O nome exibido é o do cartão (nome parlamentar); o perfil às vezes traz o nome civil. Partido: o do
histórico de filiação na data de fim da legislatura (ou hoje, na atual).

## O que não existe

- ALERJ: registro do painel por deputado (só placar), presença por sessão (só a tabela mensal),
  código de deputado comum às fontes.
- ALESP: voto de plenário e presença em dados abertos (só PDF e API do portal).
- Nas duas: votações simbólicas, a maioria, não têm voto individual.

## Custo da primeira rodada

ALESP ~9.600 pedidos (~2 h, quase tudo presença); ALERJ ~5.200 pedidos (~2 h, quase tudo Diário
Oficial, ~4 GB baixados, ~150 MB de texto guardado). As rodadas diárias relêem listas, meses recentes
e edições novas (minutos). No servidor, copiar `data/raw/` de uma máquina que já rodou evita a
primeira rodada longa.

## Outras assembleias

Levantamento de 16/10/2026 das casas que ainda não estão no projeto. São **25 casas**, não 26:
24 Assembleias estaduais (27 UFs menos RJ e SP, menos o DF) mais a Câmara Legislativa do DF. Sondagem ao vivo
com curl, 1 pedido por segundo, poucas chamadas por casa; nada foi baixado para `data/raw/`. Contagens são
`total_entries` das APIs no dia. "n/v" = não verificado. Legenda das colunas: **V** voto nominal por deputado
em plenário, **P** presença por sessão ou mês, **A** proposições com autoria.

### Tabela

| UF | Casa e URL | Sistema | V | P | A | Cobertura e exemplo que funcionou |
|---|---|---|---|---|---|---|
| AC | ALEAC `sapl.al.ac.leg.br` | SAPL (API REST, JSON) | parcial: 709 votos em 572 registros | sim: 3.356 presenças de sessão, 1.041 da ordem do dia | sim: 19.341 matérias, 18.755 autorias | sessões 2000-05 a 2026-10; votos até 2026. `/api/sessao/votoparlamentar/?page_size=1` |
| AL | ALE-AL `sapl.al.al.leg.br` | SAPL | 2.003 votos em 217 registros | só 20 da ordem do dia | sim: 15.579 / 15.515 | sessões 2014-02 a **2019-12-13**: instância parada, sistema atual n/v |
| AM | ALEAM `sapl.al.am.leg.br` (site `aleam.am.gov.br` não resolve) | SAPL | **sim: 132.199 votos em 6.582 registros** | sim: 26.617 + 7.401 | sim: 79.224 / 79.547 | sessões 2015-02 a 2026-10; último registro de votação 16/09/2026. `/api/sessao/registrovotacao/?page_size=1` |
| AP | ALEAP `al.ap.leg.br`, `elegis.al.ap.leg.br` | eLegis em implantação (aviso na página: dados em migração) + portal antigo | n/v | n/v | n/v (HTML) | Dados abertos só administrativos (licitações, contratos, remuneração; CSV/PDF). Pautas e atas em HTML |
| BA | ALBA `al.ba.gov.br` | n/v | n/v | n/v | n/v | Resolve DNS (200.187.0.224) mas conexão expira em 20 s e 30 s, de dois pedidos. Pode ser bloqueio de IP; testar de outra rede |
| CE | ALECE `transparencia.al.ce.gov.br/consultas-gerais/votacao-nominal` | Portal de transparência próprio (Laravel) | **sim, por votação: PDF + XLSX**, 31ª legislatura (02/2023 a 07/2026), 60 linhas na lista | n/v | só em texto na coluna matéria ("Autoria da Mesa Diretora") | O XLSX é um relatório formatado ("RELATÓRIO DE VOTAÇÃO": Sim, Não, Abstenção, Deputados, Partidos), não uma tabela. O download dá 403 sem `Referer` da própria página. Exemplo: `/uploads/votacao_nominal_materia_csv/LsiCA1ugMvcXaT7NqVX6IChXPu9wBok6mNgagP5D.xlsx` |
| DF | CLDF `dados.cl.df.gov.br`, `ple.cl.df.gov.br` | CKAN + API pública do PLE | não: "Painel de Votação" é um Power BI incorporado | n/v | **sim**: CKAN `proposicoes` com JSON e CSV por ano (1991 a 2020) e API PLE até 2025 | `POST https://ple.cl.df.gov.br/pleservico/api/public/proposicao/filter?page=0&size=1` com `{"ano":2025}` devolve `autoria: "Deputado Wellington Luiz"` (texto), `dataLeitura`. Os arquivos CKAN redirecionam (302) para URL S3 assinada de 1 h. Há `indicadores-legislativos` em XLSX semestral |
| ES | ALES `al.es.gov.br` | Sistema próprio (ASP.NET) | n/v | página "Frequência no Plenário" existe; sem tabela no HTML inicial, provavelmente carregada por JS | n/v (`/Proposicao`, pesquisa em formulário) | `/Transparencia/DadosAbertos` lista só despesas (favorecido, elemento, empenho) |
| GO | ALEGO `portal.al.go.leg.br` | n/v | n/v | n/v | n/v | O nome não resolve daqui (`al.go.leg.br`, `portal.al.go.leg.br`, `transparencia.al.go.leg.br`); o site aparece em busca. Repetir |
| MA | ALEMA `al.ma.leg.br`, `sistemas.al.ma.leg.br/transparencia` | SAPL legado (Zope, `sapl.al.ma.leg.br:8080/sapl`) + transparência em JSF | n/v | n/v | n/v | `sapl.al.ma.leg.br/api/...` devolve a SPA Angular (HTML), não JSON. Pautas e atas de sessão em páginas de transparência |
| MG | ALMG `dadosabertos.almg.gov.br` | API própria v2 (Swagger em `/api/ajuda/swagger/endpoints/lastest`, JSON, sem chave) | **não**: o detalhe da reunião traz pauta e resultado, sem voto por deputado | não há endpoint no Swagger (só reuniões de comissão e participação em comissão) | **sim**, só proposições em tramitação: autor em texto ("Deputada Beatriz Cerqueira  PT") | `/api/v2/proposicoes/pesquisa/direcionada?tipo=PL&ano=2024&formato=json&p=1` (1.212 PL de 2024); `/api/v2/plenario/reunioes/pesquisa?ini=20240401&fim=20240430&formato=json`; `/api/v2/legislaturas/{n}/deputados/em_exercicio`. O parâmetro de paginação é `p`; sem `tipo` o servidor responde "Parâmetro de paginação inválido" |
| MS | ALEMS `al.ms.gov.br`, `sgpl.consulta.al.ms.gov.br/sgpl-publico`, `transparencia2.al.ms.gov.br` | SGPL próprio (SPA, "Validando acesso...") | n/v | n/v | n/v | A SPA tem backend JSON provável, não descoberto |
| MT | ALMT `api.al.mt.gov.br` | API própria com OAuth2 (`/api/v1/ssl/sessao-plenaria`, `.../proposicao-votada`, `.../ordem-dia`, `/parlamentar`, `/legislatura`) | provável (endpoint `proposicao-votada`), n/v | n/v | n/v | `401 access_denied: OAuth2 authentication required`; credenciais "fornecidas pela instituição". O SAPL `sapl.al.mt.leg.br` está vazio (5 sessões, 1 matéria). Pedir credencial por LAI |
| PA | ALEPA `alepa.pa.gov.br/Legislativo/VotacoesNominais` | Sistema próprio (ASP.NET MVC, DevExpress) | formulário Ano e Mês, tabela HTML | n/v | n/v (Proposições, Pautas, Resumo do Plenário e Atas em HTML) | Out/2026 respondeu "Nenhuma votação nominal foi encontrada no mês informado"; um mês com votação não foi testado |
| PB | ALPB `sapl.al.pb.leg.br` | SAPL | **sim: 17.148 votos em 56.539 registros** (há registros de teste: "TESTE REQUIMENTO", 2018) | sim: 15.683 + 13.387 | sim: 151.359 matérias, 142.623 autorias | sessões 2013-08 a 2026-10; voto de 2025 (Veto 366/2025) |
| PE | ALEPE `dadosabertos.alepe.pe.gov.br` | API própria v1 (JSON ou CSV com `?formato=`) + `proposicoes.alepe.pe.gov.br` | não | não | não na API | A API só tem `parlamentares`, `cargos`, `lotacoes`, `servidores`, `remuneracao`, `licitacoes`, `contratos`. Proposições e reuniões plenárias só em páginas (n/v) |
| PI | ALEPI `sapl.al.pi.leg.br` | SAPL | sim: 3.314 votos em 4.500 registros | sim: 10.097 + 6.081 | sim: 21.421 / 21.967 | sessões 2008-02 a 2026-10; votos de 2026 (PLC 7/2026) |
| PR | ALEP `transparencia.assembleia.pr.leg.br`, `webservices.assembleia.pr.leg.br/api/public` | API JHipster (só `http://`; `https` dá 403) + portal de transparência | páginas "Controle de votação" (formulário, 1 tabela) n/v | página "Presença em plenário" (formulário) n/v | API `proposicao/campos` responde (tipos PRO, PLC, PDL...); `proposicao/filtrar` devolveu 400 com a chamada que tentei | Documentação em `/servicos/dados-abertos`: só proposição e norma legal. A rota `/deputado/campos` dá 404 |
| RN | ALRN `al.rn.leg.br` | n/v | n/v | n/v | n/v | Resolve (201.20.70.164) mas conexão expira; `sapl.al.rn.leg.br` não resolve |
| RO | ALERO `sapl.al.ro.leg.br` | SAPL | **sim: 44.379 votos em 15.923 registros** | sim: 25.248 + 23.554 | sim: 57.115 / 57.055 | sessões 2012-02 a 2026-10; voto de 2026 (PLC 205/2026) |
| RR | ALERR `sapl.al.rr.leg.br` | SAPL | não (0 registros) | quase não (24 e 48) | sim: 19.237 matérias, 24.149 autorias | sessões 2021-08 a 2026-10 |
| RS | ALERGS `al.rs.gov.br`, `proweb.procergs.com.br`, `epro.al.rs.gov.br` | Proweb/ePro (Procergs) + portal DNN | "Planilhas de Votação" por proposição, formato n/v | n/v | n/v (`pesquisa_proposicao.asp`, formulário) | `dadosabertos.al.rs.gov.br` não resolve. Pesquisa de planilhas anterior a 2007 em página separada |
| SC | ALESC `portalelegis.alesc.sc.gov.br` | e-Legis próprio, HTML renderizado no servidor | n/v: as páginas de Ordem do Dia que vi não mostram resultado nem voto | **sim, por sessão**: `/sessoes-plenarias/<id>/presenca` lista cada deputado e a situação ("Ausência justificada") | sim: `/sessoes-plenarias/<id>/ordem-do-dia` traz "PL./0158/2025 ... Autoria Deputada Paulinha" | Lista de sessões paginada (`/sessoes-plenarias?page=N`); exemplo: 96ª Sessão Ordinária, 15/10/2026, id `5ae25`. Sem API; o id é um hash curto |
| SE | ALESE `al.se.leg.br` | WordPress, sem sistema legislativo exposto | n/v | n/v | n/v | Só "Atas das Sessões Legislativas" e áudios |
| TO | ALETO `sapl.al.to.leg.br` | SAPL | não (0) | não (0) | sim: 14.533 matérias, 14.540 autorias | sessões 2020-02 a 2026-05 |

SAPL, para o leitor genérico: `https://sapl.al.<uf>.leg.br/api/{sessao/sessaoplenaria, sessao/registrovotacao,
sessao/votoparlamentar, sessao/sessaoplenariapresenca, sessao/presencaordemdia, materia/materialegislativa,
materia/autoria, parlamentares/parlamentar}/?page_size=N`, JSON paginado (`pagination.total_entries`), sem chave.
As instâncias redirecionam o `next` para `http://`. `votoparlamentar.voto` assume Sim, Não, Abstenção, Não Votou.
Os 8 hosts SAPL com dados são AC, AL, AM, PB, PI, RO, RR, TO; os testados que não resolvem foram AP, MS, RN, SE, GO, BA,
CE, ES e PA com o padrão `sapl.al.<uf>.leg.br`; MA e MT estão no quadro acima.

### Prioridade

1. **Um leitor SAPL genérico liga cinco casas com voto, presença e autoria**: AM, RO, PB, PI, AC, nesta ordem
   de volume (AM e RO têm ainda 2026 em curso; PB tem lixo de teste de 2018 a filtrar; AC tem poucos votos nominais).
   O mesmo leitor liga RR e TO só para proposições, e AL só como histórico até 2019.
   Limite do SAPL: `votoparlamentar` só existe para votação nominal registrada no painel; votação simbólica não tem
   voto individual, como em ALERJ e ALESP. Falta conferir, casa a casa, se o painel é usado em todas as sessões.
2. **Leitor próprio, API estável e só proposições**: DF (CKAN + API do PLE, autoria em texto), MG (API v2, autor em texto,
   sem voto nominal), PR (API em http, rota `filtrar` por descobrir). PE tem API, mas sem dado legislativo.
3. **Leitor próprio por raspagem, com voto ou presença**: CE (XLSX por votação desde 2023, único fora do SAPL
   com voto por deputado em arquivo), PA (HTML mensal, a testar em mês com votação), SC (presença por sessão e
   autoria em HTML; sem voto à vista).
4. **Só PDF, ata ou diário, ou site sem dado estruturado**: AP (em migração), MA, MS (SPA a investigar), ES, RS
   (planilhas), SE.
5. **Não verificado**: BA e RN (expira a conexão daqui), GO (DNS), MT (existe API, exige credencial).

Ressalva geral: a existência de um endpoint não prova cobertura. Em cada casa ligada, repetir o que se fez
para ALERJ e ALESP: conferir os totais de cada votação contra o placar e contar sessões sem registro.
