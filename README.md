*This project has been created as part of the 42 curriculum by c3c4d4.*

# Assembleias

## Description

Assembleias Legislativas do Rio de Janeiro (ALERJ) e de São Paulo (ALESP): votações nominais,
presença em plenário e proposições de cada deputado estadual, da Tomoyo, dentro do
g0v.tomoyo.systems. Um só frontend, um build por casa (`NEXT_PUBLIC_UF=RJ|SP`); o ETL escreve os
dados de cada casa em `frontend/data/<uf>/`. Mesma estrutura do Vereadores (repositório como-votou).

ALERJ: não há dados abertos nem registro do painel. O ETL lê a lista de deputados e os perfis em
alerj.rj.gov.br, a tabela mensal de presenças e as proposições nas bases Lotus Domino de
alerjln1.alerj.rj.gov.br e o Diário Oficial, Parte II, na Imprensa Oficial (ioerj.com.br), onde a
ata de cada sessão imprime os nomes de quem votou sim e não. A junção é por nome.

ALESP: o ETL lê a lista de votações no painel e o relatório em PDF de cada uma, a API do portal
(presença em plenário por sessão, detalhes dos deputados) e os arquivos de proposituras e autores do
portal de dados abertos. Presença, proposições e cadastro trazem o código do deputado; os
relatórios de votação, só o nome do painel.

Fontes, contagens reais e ressalvas em `FINDINGS.md`.

Sites: https://g0v.tomoyo.systems/assembleias/ (ALERJ) e https://g0v.tomoyo.systems/assembleias/sp/ (ALESP).

Telas: Deputados (`/`), Votações (`/votacoes`), Presença (`/presenca`), Partidos (`/partidos`),
Método (`/metodologia`), as mesmas nas duas casas. Teclas `1`–`5` trocam de tela, `u` troca de
casa; setas, `v`, `e`, `r` por tela.

### Layout

```text
backend/app/
  http.py                     downloads com cache (data/raw), 1 req/s, checksums; texto de PDFs grandes (TextCache)
  config.py                   caminhos por UF (data/<uf>/snapshot.json), URLs
  casas.py                    casas publicadas (frontend/data/casas.json) e o adaptador de cada uma
  models.py                   o registro de deputado que todo adaptador escreve
  names.py                    normalização e casamento de nomes (ALERJ)
  parsers/alesp.py            ALESP: lista de votações, relatório PDF do painel, presença, nomes do painel
  parsers/alerj.py            ALERJ: cartões e perfis, presença mensal (Domino), busca de proposições
  parsers/alerj_do.py         ALERJ: Diário Oficial Parte II, atas de sessão e listas nominais
  etl/export_snapshot.py      snapshot de uma casa (--uf RJ|SP), incremental
  etl/snapshot_alesp.py       o ETL da ALESP
  etl/snapshot_alerj.py       o ETL da ALERJ
  etl/export_static_frontend.py  frontend/data/<uf>: núcleo, votos por votação, votos e proposições por deputado, fotos
frontend/
  data/casas.json             casas na ordem do seletor (sigla, estado, root)
  data/<uf>/static-data.generated.json          deputados com agregados, votações com contagens, cobertura
  data/<uf>/static-votacoes/<id>.generated.json    quem votou o quê numa votação
  data/<uf>/static-deputados/<id>.generated.json   os votos e as proposições de um deputado
  data/<uf>/fotos/                                 fotos (160 px)
  scripts/use-uf.sh           copia data/<uf>/ para lib/ e public/fotos/ (roda sozinho antes de build e dev)
  scripts/build-all.sh        constrói as casas: out-all/ (ALERJ) e out-all/sp/ (ALESP)
  lib/uf.ts                   o que muda entre as casas: nomes, textos curtos, rótulos de tipos
  lib/method.ts               o texto da página Método de cada casa
deploy/build-site.sh          roda no servidor, por cron, uma vez por dia; ETL e build das casas
```

## Instructions

### Setup

```bash
cd backend && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m app.etl.export_snapshot --uf RJ --all      # ~2 h na primeira vez (Diário Oficial desde 2019), depois minutos
.venv/bin/python -m app.etl.export_static_frontend --uf RJ     # frontend/data/rj
.venv/bin/python -m app.etl.export_snapshot --uf SP --all      # ~3 h na primeira vez (presença mês a mês), depois minutos
.venv/bin/python -m app.etl.export_static_frontend --uf SP     # frontend/data/sp
cd ../frontend && npm ci && npm run dev                        # ALERJ; NEXT_PUBLIC_UF=SP npm run dev para a ALESP
```

Gates: `cd backend && .venv/bin/python -m pytest -q -W error`;
`cd frontend && npm run typecheck && npm run build:all && npm run test:visual` (Playwright serve as
duas casas juntas, ALERJ na raiz e ALESP em `/sp/`).

Build de produção de uma casa só: `NEXT_PUBLIC_UF=RJ NEXT_PUBLIC_BASE_PATH=/assembleias npm run build`
ou `NEXT_PUBLIC_UF=SP NEXT_PUBLIC_BASE_PATH=/assembleias/sp npm run build`. As duas de uma vez, como no
servidor: `ROOT=/assembleias sh scripts/build-all.sh`.

### Deploy

O site vive em `g0v.tomoyo.systems/assembleias`, no nginx estático do g0v. O cron roda
`/root/g0v/build-assembleias.sh` (cópia de `deploy/build-site.sh`, que se atualiza sozinha) todo dia:
puxa `main`, relê o que muda nas duas casas, regenera os dados e, se algo mudou, constrói as duas e
publica a ALERJ em `/root/g0v/site/assembleias/` (rsync com `--exclude=/sp/`) e a ALESP em
`/root/g0v/site/assembleias/sp/`. Se o ETL de uma casa falha, ela segue com os dados commitados.
A primeira rodada no servidor baixa o Diário Oficial e a presença da ALESP desde 2019 (horas);
copiar `data/raw/` de uma máquina que já rodou o ETL evita isso.

## Resources

- ALERJ: a lista de deputados e os perfis em alerj.rj.gov.br; a tabela mensal de presenças e as
  proposições nas bases Lotus Domino de alerjln1.alerj.rj.gov.br; o Diário Oficial, Parte II, na
  Imprensa Oficial (ioerj.com.br), onde a ata de cada sessão imprime quem votou sim e não.
- ALESP: a lista de votações no painel e o relatório em PDF de cada uma; a API do portal (presença em
  plenário por sessão, detalhes dos deputados); os arquivos de proposituras e autores do portal de
  dados abertos.
- `FINDINGS.md`: fontes com URLs, contagens reais, ressalvas e o levantamento das outras 25 casas.
- Repositório como-votou (Vereadores): mesma estrutura de backend e frontend.

AI was used to scaffold the ETL (downloader with cache, text cache for the Diário Oficial, snapshot and export scripts), to write the parsers of the ALERJ pages, the Diário Oficial and the ALESP PDF reports and APIs, and the frontend shell; the result was reviewed against the sources listed above and tested with the fixtures in `backend/tests/fixtures` and the Playwright tests in `frontend/tests`.

## Limitations

Trabalho em andamento. Casas prontas: ALERJ (12ª e 13ª legislaturas, desde 01/02/2019) e ALESP (19ª
e 20ª legislaturas, desde 15/03/2019). As outras 25 casas (24 Assembleias estaduais e a Câmara
Legislativa do DF) foram só levantadas (fontes, sistemas, cobertura e prioridade em `FINDINGS.md`,
seção "Outras assembleias") e ainda não entram no site.

- Nas duas casas, as votações simbólicas, a maioria, não têm voto individual.
- ALERJ: não há dados abertos nem registro do painel; a junção dos votos aos deputados é por nome.
- ALESP: os relatórios de votação trazem só o nome do painel; presença, proposições e cadastro trazem
  o código do deputado.
- Detalhes, contagens reais e ressalvas em `FINDINGS.md`.
