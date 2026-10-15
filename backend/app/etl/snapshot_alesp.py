"""Assembleia Legislativa do Estado de São Paulo -> data/sp/snapshot.json.

    python -m app.etl.export_snapshot --uf SP --all       # daily: 2019 on, refresh what can change
    python -m app.etl.export_snapshot --uf SP --offline   # rebuild from data/raw only

Sources (details and counts in FINDINGS.md, section "ALESP"):
  votes      /alesp/votacoes-no-plenario?anoSessao=<ano> lists every plenary vote taken on the electronic
             panel; each links a PDF report with all 94 seats, party and vote, printed totals and result
  presence   legis-api-portal-prd /lista-presenca-parlamentar/<matrícula>/<mês>/<ano>: one line per
             plenary session with the deputy's mark (the portal's "Presença em Plenário" page)
  roster     /lista-presenca-parlamentar/parlamentares/ (everyone since 1995, with legislatures) and
             /parlamentar-portal/detalhes/<matrícula> (author id, affiliations, mandates, photo)
  bills      repositorioDados proposituras.zip, documento_autor.zip, naturezasSpl.xml (open data)
Votes carry only the name printed on the panel; they are joined to the roster by name within the
legislature of the vote (aliases in PANEL_ALIASES). Presence and bills carry ids.
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from .. import config
from ..http import Downloader
from ..models import Deputado
from ..parsers.alesp import (RelatorioVotacao, VotacaoRef, norm_name, objeto_of, parse_vote_pdf, parse_votacoes_index,
                             party_on, presenca_status, proposicao_of, resultado_of, title_name)
from .aggregates import lado_vencedor, legislatura_of

UF = "SP"
LEGISLATURAS = [
    {"numero": 19, "inicio": "2019-03-15", "fim": "2023-03-14"},
    {"numero": 20, "inicio": "2023-03-15", "fim": "2027-03-14"},
]
# Natureza (naturezasSpl.xml sgNatureza, trimmed) -> type code used by the site.
TIPOS = {"PL": "PL", "PLC": "PLC", "PDL": "PDL", "PR": "PR", "PEC": "PEC", "Indicação": "IND", "Moção": "MOC", "RI": "RI"}
# Majority of the 94 seats: below it the plenary cannot deliberate (Regimento Interno).
QUORUM = 48
PRESENCA_REFRESH_MONTHS = 2
# Panel name (normalised) -> roster name (normalised), only where the token rules in PanelNames fail.
# Each one checked against the deputy's own page on the portal (biography or earlier names).
PANEL_ALIASES: dict[str, str] = {
    "FABIANA BARROSO": "FABIANA BOLSONARO",                         # name on the panel in 2023
    "MARCIO GIUDICIO": "MARCIO DA FARMACIA",                        # civil name
    "MONICA DA BANCADA ATIVISTA": "MONICA SEIXAS DO MOVIMENTO PRETAS",   # collective mandate, 2019
    "MONICA DA MANDATA ATIVISTA": "MONICA SEIXAS DO MOVIMENTO PRETAS",
    "LUIZ FERNANDO LULA DA SILVA": "LUIZ FERNANDO T FERREIRA",      # 2019: "Lula" in PT names
}
# A panel name that matches nobody and appears in at least this many votes becomes a deputy of its own
# (the portal's list misses a few people who held a seat).
MIN_VOTOS_SEM_CADASTRO = 3


def log(*a: object) -> None:
    print(*a, file=sys.stderr, flush=True)


def did(matricula: object) -> str:
    return f"alesp:{int(matricula)}"


# --- loaders ---------------------------------------------------------------------------------------

def load_roster(dl: Downloader, refresh: bool) -> tuple[list[dict], dict[str, dict]]:
    """Everyone with a mandate in the 19th or 20th legislature, with the portal's details."""
    rows = dl.fetch(f"{config.ALESP_API}/lista-presenca-parlamentar/parlamentares/", refresh=refresh).json()
    legs = {lg["numero"] for lg in LEGISLATURAS}
    rows = [r for r in rows if set(r.get("listaLegislaturas") or []) & legs]
    det: dict[str, dict] = {}
    for r in rows:
        try:
            det[str(r["nuMatricula"])] = dl.fetch(f"{config.ALESP_API}/parlamentar-portal/detalhes/{r['nuMatricula']}",
                                                  refresh=refresh and bool(r.get("isEmExercicio"))).json()
        except Exception as e:
            log(f"  detalhes {r['nuMatricula']}: {e!r}")
    return rows, det


def load_presenca(dl: Downloader, rows: list[dict], from_ym: tuple[int, int], refresh: bool,
                  refresh_from: tuple[int, int] | None) -> tuple[list[dict], dict]:
    """One line per (deputy, plenary session) from the portal's API."""
    today = date.today()
    newest = [(today.year, today.month)]
    for _ in range(PRESENCA_REFRESH_MONTHS - 1):
        y, m = newest[-1]
        newest.append((y, m - 1) if m > 1 else (y - 1, 12))
    out: list[dict] = []
    stats = {"pedidos": 0, "meses_vazios": 0, "erros": []}
    for r in rows:
        mat, idp = r["nuMatricula"], r["idParlamentar"]
        try:
            meses = dl.fetch(f"{config.ALESP_API}/lista-presenca-parlamentar/mesesAnosMandatosParlamentar/{idp}",
                             refresh=refresh and bool(r.get("isEmExercicio"))).json()
        except Exception as e:
            stats["erros"].append({"matricula": mat, "erro": repr(e)[:160]})
            continue
        for am in meses:
            y, m = (int(x) for x in am.split("/"))
            if (y, m) < from_ym or (y, m) > (today.year, today.month):
                continue
            rf = refresh and ((y, m) in newest or (refresh_from is not None and (y, m) >= refresh_from))
            try:
                lista = dl.fetch(f"{config.ALESP_API}/lista-presenca-parlamentar/{mat}/{m}/{y}", refresh=rf).json()
            except Exception as e:
                stats["erros"].append({"matricula": mat, "mes": f"{y}-{m:02d}", "erro": repr(e)[:160]})
                continue
            stats["pedidos"] += 1
            if not lista:
                stats["meses_vazios"] += 1
            for s in lista:
                dd, mm, yy = s["data"].split("/")
                out.append({"matricula": mat, "sessao_id": s.get("idSessaoPlenaria"), "sessao": s.get("tituloSessaoPlenaria"),
                            "data": f"{yy}-{mm}-{dd}", "situacao": s.get("situacao") or ""})
    return out, stats


def monthly_presence(linhas: list[dict], nomes: dict[str, str]) -> list[dict]:
    """Session marks -> one row per deputy per month (the shape every casa writes).

    faltas = "Não Justificada" plus "Ausência em Sessão Extraordinária"; faltas_abonadas = "Justificada"
    and licenças; sessions marked "Sessão não Deliberativa" do not count.
    """
    acc: dict[tuple[str, int, int], Counter] = defaultdict(Counter)
    for l in linhas:
        st = presenca_status(l["situacao"])
        if st == "nao_deliberativa":
            continue
        i = did(l["matricula"])
        c = acc[(i, int(l["data"][:4]), int(l["data"][5:7]))]
        c["sessoes"] += 1
        c[st] += 1
    rows = []
    for (i, y, m), c in sorted(acc.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        faltas = c["falta"] + c["extraordinaria"]
        abon = c["justificada"] + c["licenca"]
        rows.append({"ano": y, "mes": m, "deputado_nome": nomes.get(i, i), "deputado_id": i,
                     "faltas": faltas, "faltas_abonadas": abon, "total_faltas": faltas + abon,
                     "sessoes": c["sessoes"], "presencas": c["presente"], "nao_justificadas": c["falta"],
                     "ausencias_extraordinarias": c["extraordinaria"], "justificadas": c["justificada"],
                     "licencas": c["licenca"], "outras": c["outro"]})
    return rows


def load_vote_refs(dl: Downloader, from_year: int, refresh: bool) -> list[VotacaoRef]:
    now = date.today()
    refs: list[VotacaoRef] = []
    for y in range(from_year, now.year + 1):
        rf = refresh and (y == now.year or (y == now.year - 1 and now.month <= 2))
        f = dl.fetch(f"{config.ALESP}/alesp/votacoes-no-plenario?anoSessao={y}", refresh=rf)
        refs.extend(parse_votacoes_index(f.text("latin-1")))
    return refs


def _xml_from_zip(data: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name = next(n for n in z.namelist() if n.endswith(".xml"))
        return z.read(name)


def load_proposicoes(dl: Downloader, from_year: int, refresh: bool) -> tuple[list[dict], dict[str, dict], dict]:
    """Bills from the open data files. Returns (rows kept, every document by IdDocumento, counts)."""
    nat = {}
    for n in ET.fromstring(dl.fetch(f"{config.ALESP_DADOS}/processo_legislativo/naturezasSpl.xml", refresh=refresh).path.read_bytes()):
        nat[n.findtext("idNatureza")] = (n.findtext("sgNatureza") or "").strip()
    docs: dict[str, dict] = {}
    raw = _xml_from_zip(dl.fetch(f"{config.ALESP_DADOS}/processo_legislativo/proposituras.zip", refresh=refresh).path.read_bytes())
    for _, el in ET.iterparse(io.BytesIO(raw)):
        if el.tag != "propositura":
            continue
        ano = int(el.findtext("AnoLegislativo") or 0)
        sg = nat.get(el.findtext("IdNatureza") or "", "")
        docs[el.findtext("IdDocumento")] = {
            "ano": ano, "natureza": sg, "numero": (el.findtext("NroLegislativo") or "").strip(),
            "ementa": re.sub(r"\s+", " ", el.findtext("Ementa") or "").strip(),
            "data": (el.findtext("DtPublicacao") or el.findtext("DtEntradaSistema") or "")[:10] or None}
        el.clear()
    del raw
    autores: dict[str, list[tuple[str, str]]] = defaultdict(list)
    raw = _xml_from_zip(dl.fetch(f"{config.ALESP_DADOS}/processo_legislativo/documento_autor.zip", refresh=refresh).path.read_bytes())
    for _, el in ET.iterparse(io.BytesIO(raw)):
        if el.tag != "DocumentoAutor":
            continue
        d = el.findtext("IdDocumento")
        if d in docs:
            autores[d].append((el.findtext("IdAutor") or "", (el.findtext("NomeAutor") or "").strip()))
        el.clear()
    del raw
    rows: list[dict] = []
    counts: Counter = Counter()
    for iddoc, d in docs.items():
        d["autores"] = autores.get(iddoc, [])
        tipo = TIPOS.get(d["natureza"])
        if tipo is None or d["ano"] < from_year or not d["numero"]:
            continue
        counts[f"{d['ano']}/{tipo}"] += 1
        rows.append({"id": f"{tipo}-{int(d['numero']) if d['numero'].isdigit() else d['numero']}/{d['ano']}", "tipo": tipo,
                     "numero": str(int(d["numero"])) if d["numero"].isdigit() else d["numero"], "ano": d["ano"],
                     "ementa": d["ementa"], "data": d["data"], "autores": [a[1] for a in d["autores"]],
                     "autores_raw": ", ".join(a[1] for a in d["autores"]), "_autores": [a[0] for a in d["autores"]],
                     "id_documento": iddoc})
    return rows, docs, dict(sorted(counts.items()))


def save_photo(dl: Downloader, url: str, key: str, photos: Path) -> str | None:
    try:
        f = dl.fetch(url)
    except Exception as e:
        log(f"  foto {key}: {e!r}")
        return None
    photos.mkdir(parents=True, exist_ok=True)
    ext = Path(url.split("?")[0]).suffix.lower().lstrip(".") or "jpg"
    dst = photos / f"{key}.{'jpg' if ext == 'jpeg' else ext}"
    if not dst.exists() or dst.read_bytes() != f.path.read_bytes():
        dst.write_bytes(f.path.read_bytes())
    return f"photos/{dst.name}"


# --- names on the panel -----------------------------------------------------------------------------

_DROP = {"LULA"}          # in 2019 several PT deputies printed "Lula" inside their panel names


def _tokens(s: str) -> list[str]:
    return [t for t in norm_name(s).split() if t not in _DROP]


def _tok_match(a: str, b: str) -> bool:
    """Same word, an initial ("C" ~ "CLAUDIO") or an abbreviation ("PROF" ~ "PROFESSORA")."""
    if a == b:
        return True
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return (len(short) == 1 or len(short) >= 3) and long_.startswith(short)


def _covers(small: list[str], big: list[str]) -> bool:
    """Every token of ``small`` matches a distinct token of ``big`` in order (initials match words)."""
    j = 0
    for t in small:
        while j < len(big) and not _tok_match(t, big[j]):
            j += 1
        if j == len(big):
            return False
        j += 1
    return True


class PanelNames:
    """Match the names printed on the panel to the roster, among the deputies of the vote's legislature."""

    def __init__(self, deputados: dict[str, dict]):
        self.dep = deputados              # id -> {"nomes": [...], "legs": set}
        self.unmatched: Counter = Counter()
        self._cache: dict[tuple[str, int | None], str | None] = {}

    def match(self, nome: str, leg: int | None) -> str | None:
        key = (nome, leg)
        if key in self._cache:
            return self._cache[key]
        n = norm_name(nome)
        n = PANEL_ALIASES.get(n, n)
        toks = _tokens(n)
        pool = [i for i, d in self.dep.items() if leg is None or leg in d["legs"]] or list(self.dep)
        hit = [i for i in pool if any(norm_name(x) == n for x in self.dep[i]["nomes"])]
        if len(hit) != 1:
            hit = [i for i in pool if any(" ".join(_tokens(x)) == " ".join(toks) for x in self.dep[i]["nomes"])]
        if len(hit) != 1:
            hit = [i for i in pool if any(_covers(toks, _tokens(x)) or _covers(_tokens(x), toks) for x in self.dep[i]["nomes"])]
        out = hit[0] if len(hit) == 1 else None
        if out is None:
            import difflib
            names = {norm_name(x): i for i in pool for x in self.dep[i]["nomes"]}
            close = difflib.get_close_matches(n, list(names), n=2, cutoff=0.86)
            if len(close) == 1 or (len(close) == 2 and names[close[0]] == names[close[1]]):
                out = names[close[0]]
        if out is None:
            self.unmatched[f"{nome} ({leg})"] += 1
        self._cache[key] = out
        return out


# --- votes -------------------------------------------------------------------------------------------

def build_votacoes(refs: list[VotacaoRef], reports: dict[str, RelatorioVotacao], names: PanelNames,
                   docs: dict[str, dict], prop_by_id: dict[str, dict], author_ids: dict[str, str],
                   party_at=None) -> tuple[list[dict], dict]:
    """``party_at(id, date)``: the deputy's party on that day from the registry; the panel prints the
    federation (FED PT/PC DO B/PV) instead of the party since 2022, so the registry wins when it knows."""
    stats: dict = {"listadas": len(refs), "lidas": 0, "falhas": [], "impresso_discrepancies": [], "nomes_sem_cadastro": 0,
                   "votos_desconhecidos": Counter(), "sem_resultado_impresso": 0, "sem_quorum_inferido": 0,
                   "presidente_identificado": 0, "por_ano": {}, "escolhas": []}
    out: list[dict] = []
    seen: set[str] = set()
    for ref in refs:
        rel = reports.get(ref.pdf_url)
        if rel is None:
            continue
        if not rel.linhas:
            # Elections of the Mesa and choices of voting method print a four-column grid of options
            # (1, 2, a, O) instead of sim/não; they are listed apart, not read as votes.
            stats["escolhas"].append({"data": ref.data, "titulo": ref.titulo, "url": ref.pdf_url})
            continue
        data = rel.data or ref.data
        leg = legislatura_of(data, LEGISLATURAS)
        if leg is None:
            continue
        vid = "alesp:" + re.sub(r"[^A-Za-z0-9]+", "-", ref.pdf_url.rsplit("/", 1)[-1].removesuffix(".pdf").removesuffix("-PDF")).strip("-")
        if vid in seen:
            continue
        seen.add(vid)
        stats["lidas"] += 1
        votos: dict[str, str] = {}
        partidos: dict[str, str | None] = {}
        presidente = None
        presidente_nome = None
        for l in rel.linhas:
            i = names.match(l.nome, leg)
            if i is None:
                stats["nomes_sem_cadastro"] += 1
                continue
            v = l.voto
            if l.marca == "P":
                presidente, presidente_nome = i, title_name(l.nome)
            if v == "licenciado":
                continue
            if v == "sem_voto":
                v = "presidindo" if l.marca == "P" else "ausente"
            elif v == "branco":
                v = "branco"
            elif v not in ("sim", "nao", "abstencao", "obstrucao"):
                stats["votos_desconhecidos"][v] += 1
                continue
            votos[i] = v
            partidos[i] = (party_at(i, data) if party_at else None) or l.partido or None
        if presidente:
            stats["presidente_identificado"] += 1
        contagem = {k: sum(1 for x in votos.values() if x == k) for k in ("sim", "nao", "abstencao")}
        contagem["presentes_votando"] = contagem["sim"] + contagem["nao"] + contagem["abstencao"] + sum(1 for x in votos.values() if x == "branco")
        for side in ("sim", "nao", "abstencao"):
            if rel.impresso.get(side) is not None and rel.impresso[side] != contagem[side]:
                stats["impresso_discrepancies"].append({"id": vid, "data": data, "titulo": ref.titulo, "lado": side,
                                                        "impresso": rel.impresso[side], "nomes": contagem[side]})
        resultado = resultado_of(rel.resultado_raw)
        frase = rel.resultado_raw
        if resultado is None:
            stats["sem_resultado_impresso"] += 1
            total = rel.impresso.get("total")
            if total is not None and total < QUORUM:
                resultado = "sem_quorum"
                stats["sem_quorum_inferido"] += 1
                frase = f"sem resultado impresso; {total} votos registrados, abaixo do quórum de {QUORUM}"
        titulo = rel.titulo or ref.titulo
        objeto = objeto_of(titulo)
        prop: dict = {"id": None, "tipo": None, "numero": None, "ano": None, "ementa": ref.ementa, "autores": [], "autores_ids": []}
        doc = docs.get(ref.propositura_id or "")
        parsed = proposicao_of(titulo) or proposicao_of(ref.titulo)
        if doc and TIPOS.get(doc["natureza"]) and doc["numero"].isdigit():
            t = TIPOS[doc["natureza"]]
            parsed = (t, int(doc["numero"]), doc["ano"])
        if parsed:
            t, n, a = parsed
            pid = f"{t}-{n}/{a}"
            base = prop_by_id.get(pid)
            auts = (doc or {}).get("autores") or []
            prop = {"id": pid, "tipo": t, "numero": str(n), "ano": a,
                    "ementa": ref.ementa or (base or {}).get("ementa") or (doc or {}).get("ementa"),
                    "autores": [x[1] for x in auts] or list((base or {}).get("autores", [])),
                    "autores_ids": [author_ids[x[0]] for x in auts if x[0] in author_ids] or list((base or {}).get("autores_ids", []))}
        pa = stats["por_ano"].setdefault(data[:4], {"nominais": 0, "sem_resultado": 0})
        pa["nominais"] += 1
        if resultado is None:
            pa["sem_resultado"] += 1
        out.append({
            "id": vid, "data": data, "hora": rel.hora, "legislatura": leg,
            "sessao": {"tipo": None, "numero": rel.sessao or ref.sessao_nome or None, "fase": None},
            "titulo": titulo, "proposicao": prop, "objeto": objeto, "resultado": resultado,
            "resultado_frase": " · ".join(x for x in (frase, rel.pedido) if x),
            "lado_vencedor": lado_vencedor(contagem), "contagem": contagem, "impresso": rel.impresso,
            "presidente": presidente, "presidente_nome": presidente_nome, "roster_mes": None,
            "votos": votos, "partidos": partidos, "partidos_obstrucao": rel.partidos_obstrucao,
            "fonte": ref.pdf_url,
        })
    stats["votos_desconhecidos"] = dict(stats["votos_desconhecidos"])
    return out, stats


# --- main --------------------------------------------------------------------------------------------

def run(args) -> int:
    refresh = not (args.offline or args.no_refresh)
    dl = Downloader(offline=args.offline)
    from_year = args.from_year
    log("SP: deputados ...")
    rows, det = load_roster(dl, refresh)
    log(f"  {len(rows)} deputados with a mandate in legislatures {[lg['numero'] for lg in LEGISLATURAS]}, {len(det)} detail pages")
    xml_deps = {}
    try:
        for d in ET.fromstring(dl.fetch(f"{config.ALESP_DADOS}/deputados/deputados.xml", refresh=refresh).path.read_bytes()):
            xml_deps[d.findtext("Matricula")] = {k: (d.findtext(k) or "").strip() for k in ("NomeParlamentar", "Email", "Telefone", "Sala", "Andar")}
    except Exception as e:
        log(f"  deputados.xml: {e!r}")

    legs_by_id: dict[str, set[int]] = {}
    nomes: dict[str, str] = {}
    author_ids: dict[str, str] = {}
    panel_pool: dict[str, dict] = {}
    for r in rows:
        mat = str(r["nuMatricula"])
        i = did(mat)
        d = det.get(mat, {})
        legs = {lg["numero"] for lg in LEGISLATURAS} & set(r.get("listaLegislaturas") or [])
        legs_by_id[i] = legs
        nome = xml_deps.get(mat, {}).get("NomeParlamentar") or title_name(d.get("txNomeParlamentar") or r["txNomeParlamentar"])
        nomes[i] = nome
        if d.get("idAutor"):
            author_ids[str(d["idAutor"])] = i
        panel_pool[i] = {"nomes": [x for x in {r["txNomeParlamentar"], d.get("txNomeParlamentar") or "", d.get("txNomePlenario") or "", nome} if x],
                         "legs": legs}

    log("SP: proposições ...")
    prop_rows, docs, raw_counts = load_proposicoes(dl, from_year, refresh)
    unmatched_authors: Counter = Counter()
    for p in prop_rows:
        p["autores_ids"] = [author_ids[a] for a in p.pop("_autores") if a in author_ids]
        p["autores_outros"] = False
        if not p["autores_ids"]:
            for a in p["autores"]:
                unmatched_authors[a] += 1
    log(f"  {len(prop_rows)} proposições ({', '.join(sorted(set(TIPOS.values())))}) from {from_year}")
    prop_by_id = {p["id"]: p for p in prop_rows}

    log("SP: votações ...")
    refs = load_vote_refs(dl, from_year, refresh)
    if args.max_docs:
        refs = refs[: args.max_docs]
    reports: dict[str, RelatorioVotacao] = {}
    falhas = []
    for ref in refs:
        if ref.data < LEGISLATURAS[0]["inicio"]:
            continue
        try:
            f = dl.fetch(ref.pdf_url)
            reports[ref.pdf_url] = parse_vote_pdf(f.path)
        except Exception as e:
            falhas.append({"url": ref.pdf_url, "data": ref.data, "erro": repr(e)[:200]})
            log(f"  FAILED {ref.data} {ref.pdf_url}: {e!r}")
    # Panel names nobody matches, seen in several votes: a deputy the portal's list misses.
    probe = PanelNames(panel_pool)
    orphans: dict[str, dict] = {}
    for ref in refs:
        rel = reports.get(ref.pdf_url)
        if rel is None:
            continue
        data = rel.data or ref.data
        leg = legislatura_of(data, LEGISLATURAS)
        for l in rel.linhas:
            if leg is not None and probe.match(l.nome, leg) is None:
                o = orphans.setdefault(norm_name(l.nome), {"nome": l.nome, "votos": 0, "legs": set(), "partido": None, "ultima": ""})
                o["votos"] += 1
                o["legs"].add(leg)
                if data >= o["ultima"]:
                    o["ultima"], o["partido"] = data, l.partido or o["partido"]
    extra: list[dict] = []
    for key, o in orphans.items():
        if o["votos"] >= MIN_VOTOS_SEM_CADASTRO:
            i = "alesp:nome-" + key.lower().replace(" ", "-")
            panel_pool[i] = {"nomes": [o["nome"]], "legs": o["legs"]}
            extra.append({"id": i, **o})
    names = PanelNames(panel_pool)
    def party_at(i: str, day: str) -> str | None:
        mat = i.split(":")[1]
        return party_on((det.get(mat) or {}).get("listaFiliacoes") or [], day) if mat.isdigit() else None

    votacoes, vstats = build_votacoes(refs, reports, names, docs, prop_by_id, author_ids, party_at)
    vstats["falhas"] = falhas
    vstats["unmatched_names"] = dict(names.unmatched.most_common())
    log(f"  {len(votacoes)} votações nominais; {len(vstats['impresso_discrepancies'])} printed-count differences;"
        f" {sum(names.unmatched.values())} unmatched panel names: {dict(names.unmatched.most_common(12))}")

    log("SP: presença ...")
    rf_from = None
    if args.presenca_refresh_from:
        y, m = args.presenca_refresh_from.split("-")[:2]
        rf_from = (int(y), int(m))
    start = max((args.presenca_from, 1), (int(LEGISLATURAS[0]["inicio"][:4]), int(LEGISLATURAS[0]["inicio"][5:7])))
    linhas, pstats = load_presenca(dl, rows, start, refresh, rf_from)
    log(f"  {len(linhas)} session marks, {pstats['pedidos']} months read, {pstats['meses_vazios']} empty, {len(pstats['erros'])} errors")
    presencas = monthly_presence(linhas, nomes)


    # --- deputados -----------------------------------------------------------------------------------
    voted_party: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    for vt in votacoes:
        for i, p in vt["partidos"].items():
            if p:
                k = str(vt["legislatura"])
                if k not in voted_party[i] or voted_party[i][k][0] <= vt["data"]:
                    voted_party[i][k] = (vt["data"], p)
    photos = config.photos_dir(UF)
    deputados: list[Deputado] = []
    today = date.today().isoformat()
    for r in rows:
        mat = str(r["nuMatricula"])
        i = did(mat)
        d = det.get(mat, {})
        legs = sorted(legs_by_id[i])
        ppl: dict[str, str] = {}
        for leg in legs:
            lg = next(x for x in LEGISLATURAS if x["numero"] == leg)
            p = party_on(d.get("listaFiliacoes") or [], min(lg["fim"], today))
            if not p:
                p = (voted_party[i].get(str(leg)) or (None, None))[1]
                if p and p.startswith("FED "):      # a federation, not a party
                    p = None
            if p:
                ppl[str(leg)] = p
        partido = ppl.get(str(legs[-1])) if legs else None
        if r.get("isEmExercicio") and not partido and r.get("txPartido"):
            partido = r["txPartido"]
            ppl[str(LEGISLATURAS[-1]["numero"])] = partido
        bio = d.get("biografia") or {}
        foto = None
        if bio.get("txFotoGrande"):
            foto = save_photo(dl, f"{config.ALESP_FOTOS}/{bio['txFotoGrande'].lstrip('/')}", mat, photos)
        x = xml_deps.get(mat, {})
        deputados.append(Deputado(
            id=i, nome=nomes[i], nome_parlamentar=nomes[i], partido=partido, legislaturas=legs, partidos_por_legislatura=ppl,
            situacao="em_exercicio" if r.get("isEmExercicio") else "fora_de_exercicio", foto=foto,
            gabinete=(f"Sala {x['Sala']}, {x['Andar']}" if x.get("Sala") else None), telefone=x.get("Telefone") or None,
            email=x.get("Email") or None, perfil_url=f"{config.ALESP}/deputado/?matricula={mat}"))

    for o in extra:
        deputados.append(Deputado(
            id=o["id"], nome=title_name(o["nome"]), nome_parlamentar=title_name(o["nome"]), partido=o["partido"],
            legislaturas=sorted(o["legs"]), partidos_por_legislatura={str(max(o["legs"])): o["partido"]} if o["partido"] else {},
            situacao="fora_de_exercicio", foto=None, perfil_url=None))
    log(f"  {len(deputados)} deputados ({len(extra)} known only from the panel: {[o['nome'] for o in extra]})")

    snapshot = {
        "uf": UF,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "legislatures": LEGISLATURAS,
        "deputados": [asdict(v) for v in sorted(deputados, key=lambda v: v.nome)],
        "votacoes": votacoes,
        "presencas": presencas,
        "proposicoes": sorted(prop_rows, key=lambda r: (r["tipo"], -r["ano"], r["numero"].zfill(6))),
        "stats": {
            "votacoes": vstats,
            "presenca": {**pstats, "marcas": dict(Counter(l["situacao"] for l in linhas)),
                         "sessoes": len({l["sessao_id"] for l in linhas}),
                         "sessoes_deliberativas": len({l["sessao_id"] for l in linhas if presenca_status(l["situacao"]) != "nao_deliberativa"}),
                         "ultima_sessao": max((l["data"] for l in linhas), default=None)},
            "proposicoes": {"total": len(prop_rows), "por_tipo_ano": raw_counts,
                            "unmatched_authors": dict(unmatched_authors.most_common()), "com_outros": 0},
            "deputados": {"em_exercicio": sum(1 for v in deputados if v.situacao == "em_exercicio"),
                          "com_foto": sum(1 for v in deputados if v.foto)},
            "presenca_unmatched": [],
            "requests_made": dl.requests_made,
            "args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        },
        "sources": [{"name": k, "url": f.url, "accessed_at": f.accessed_at, "checksum": f"sha256:{f.sha256}"}
                    for k, f in dl.sources.items()],
    }
    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1))
    log(f"wrote {out} ({out.stat().st_size/1e6:.1f} MB); {dl.requests_made} network requests")
    return 0
