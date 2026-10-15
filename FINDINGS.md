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
