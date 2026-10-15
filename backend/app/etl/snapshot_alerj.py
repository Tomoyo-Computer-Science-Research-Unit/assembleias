"""Assembleia Legislativa do Estado do Rio de Janeiro -> data/rj/snapshot.json.

    python -m app.etl.export_snapshot --uf RJ --all       # daily: 2019 on, refresh what can change
    python -m app.etl.export_snapshot --uf RJ --offline   # rebuild from data/raw only

Sources (details and counts in FINDINGS.md, section "ALERJ"):
  roster     www.alerj.rj.gov.br/Deputados/QuemSao (POST per legislature, in office / held the seat) and
             /Deputados/PerfilDeputado/<id> (name, e-mail, party history with dates); the site's numeric
             id is the deputy id here
  presence   alerjln1 ordemdia.nsf, view "presint": one table a month with each deputy's absences
             from deliberative sessions and the days missed
  bills      alerjln1 scpro1923.nsf (12ª) and scpro2327.nsf (13ª): Domino full-text search by bill code
  votes      Diário Oficial Parte II (ioerj.com.br): the record of each plenary session prints the names
             of who voted "sim", "não" and abstained in each panel vote, with the totals
ALERJ's own systems print only vote totals, and no source shares an id with the roster: presence,
bills and votes are joined to it by name (aliases in names.ALIASES_ALERJ).
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

from .. import config
from ..http import Downloader, TextCache
from ..models import Deputado
from ..names import NameResolver, norm, slug
from ..parsers.alerj import (MESES, Perfil, TIPO_COD, domino_json, fold, parse_perfil, parse_presenca, parse_quemsao,
                             parse_search_rows, party_on, prop_from_code, view_rows)
from ..parsers.alerj_do import (IOERJ, AtaDO, calendar_dates, edition_url, has_plenary_record, parse_records, parte_ii_guids,
                                pdf_url)
from .aggregates import lado_vencedor, legislatura_of

UF = "RJ"
LEGISLATURAS = [
    {"numero": 12, "inicio": "2019-02-01", "fim": "2023-01-31", "site": 19, "scpro": "scpro1923.nsf"},
    {"numero": 13, "inicio": "2023-02-01", "fim": "2027-01-31", "site": 20, "scpro": "scpro2327.nsf"},
]
ALERJ = "https://www.alerj.rj.gov.br"
LN1 = "http://alerjln1.alerj.rj.gov.br"
PRESINT = f"{LN1}/ordemdia.nsf/85ef985c696ead9083256cf50081437a"
# Domino view of each bill type (same UNIDs in both legislature databases).
VIEWS = {"PL": "18c1dd68f96be3e7832566ec0018d833", "PEC": "e156baa31cae7158832566ec0018d83c",
         "PLC": "34c4e2da9b17c0d3832566ec0018d830", "PDL": "b3156862637ed3b7832566ec0018d82d",
         "PR": "10d6d451b00fd42b832566ec0018d836", "IND": "90576c979f5b30d3832566ec0018d81e",
         "MOC": "ce9c3f177ad4aec7832566ec0018d824", "REQINF": "bc28bd5455f59815832566ec0018d83f"}
COD_TIPO = {v: k for k, v in TIPO_COD.items()}
SEARCH_CAP = 990          # a full-text search returns at most 1000 rows; at this many, split the prefix
DO_REFRESH_DAYS = 7
PRESENCA_REFRESH_MONTHS = 3

# Spellings in the Diário Oficial, the presence tables and the bill authors -> the roster's name
# (normalised). Each pair seen in the sources; the right side is the name on alerj.rj.gov.br.
ALIASES_ALERJ: dict[str, str] = {
    "marcelo do seu dino": "marcelo dino",        # name in the 12th legislature, same deputy (id 435)
    "professor josemar": "prof josemar",
    "felipe poubel": "filippe poubel",
    "marcus miller": "marcos muller",
    "poubel": "filippe poubel",
}


def log(*a: object) -> None:
    print(*a, file=sys.stderr, flush=True)


def title_name(nome: str) -> str:
    small = {"de", "da", "do", "das", "dos", "e"}
    out = []
    for k, w in enumerate(nome.lower().split()):
        if w in small and k:
            out.append(w)
        elif w in ("bnh", "mst", "psol") or (len(w) <= 3 and w.isalpha() and not any(c in "aeiouáéíóú" for c in w)):
            out.append(w.upper())
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


def did(i: int | str) -> str:
    return f"alerj:{int(i)}"


def fetch(dl: Downloader, url: str, *, data: dict | None = None, refresh: bool = False, tries: int = 4):
    """www.alerj.rj.gov.br drops connections after bursts; wait and retry instead of failing the run."""
    for k in range(tries):
        try:
            return dl.fetch(url, data=data, refresh=refresh)
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500:
                raise
            if k == tries - 1:
                raise
            log(f"  retry {url}: {e!r}")
            time.sleep(20 * (k + 1))


# --- roster ---------------------------------------------------------------------------------------------

def load_roster(dl: Downloader, refresh: bool) -> tuple[dict[int, dict], dict[int, Perfil]]:
    cards: dict[int, dict] = {}
    for lg in LEGISLATURAS:
        for sit in ("1", "2"):
            page = fetch(dl, f"{ALERJ}/Deputados/QuemSao", data={"legislatura": str(lg["site"]), "situacaoDeputado": sit,
                                                                 "partido": "", "nomedeputado": ""},
                         refresh=refresh and lg is LEGISLATURAS[-1]).text()
            for c in parse_quemsao(page):
                e = cards.setdefault(c.id, {"nome": c.nome, "legs": {}, "foto": c.foto, "atual": False})
                e["legs"][lg["numero"]] = c.partido
                e["foto"] = e["foto"] or c.foto
                if lg is LEGISLATURAS[-1] and sit == "1":
                    e["atual"] = True
                    e["foto"] = c.foto or e["foto"]
    perfis: dict[int, Perfil] = {}
    for i, e in cards.items():
        try:
            perfis[i] = parse_perfil(fetch(dl, f"{ALERJ}/Deputados/PerfilDeputado/{i}", refresh=refresh and e["atual"]).text())
        except Exception as ex:
            log(f"  perfil {i}: {ex!r}")
    return cards, perfis


def save_photo(dl: Downloader, url: str, key: str, photos: Path) -> str | None:
    try:
        f = fetch(dl, url)
    except Exception as e:
        log(f"  foto {key}: {e!r}")
        return None
    photos.mkdir(parents=True, exist_ok=True)
    dst = photos / f"{key}.jpg"
    if not dst.exists() or dst.read_bytes() != f.path.read_bytes():
        dst.write_bytes(f.path.read_bytes())
    return f"photos/{dst.name}"


# --- presence -------------------------------------------------------------------------------------------

def load_presenca(dl: Downloader, from_year: int, refresh: bool) -> tuple[list[dict], list[dict]]:
    """Every monthly absence table published from ``from_year`` on (the view lists years, then months)."""
    today = date.today()
    top = view_rows(domino_json(fetch(dl, f"{PRESINT}?ReadViewEntries&OutputFormat=JSON&CollapseView", refresh=refresh).text("utf-8")))
    years = {int(r["values"].get("$7")): r["position"] for r in top if r["values"].get("$7") and "." not in r["position"]}
    tables: list[dict] = []
    docs: list[dict] = []
    for y in sorted(years):
        if y < from_year:
            continue
        pos = years[y]
        rf = refresh and y >= today.year - (1 if today.month <= PRESENCA_REFRESH_MONTHS else 0)
        months = view_rows(domino_json(fetch(dl, f"{PRESINT}?ReadViewEntries&OutputFormat=JSON&CollapseView&StartKey={y}&KeyType=number&Expand={pos}",
                                             refresh=rf).text("utf-8")))
        for m in months:
            if not m["position"].startswith(f"{pos}.") or m["position"].count(".") != 1:
                continue
            rows = view_rows(domino_json(fetch(dl, f"{PRESINT}?ReadViewEntries&OutputFormat=JSON&CollapseView&StartKey={y}&KeyType=number&Expand={m['position']}",
                                               refresh=rf).text("utf-8")))
            for r in rows:
                if r["unid"] and r["position"].startswith(m["position"] + "."):
                    docs.append({"ano_pub": y, "unid": r["unid"], "titulo": str(r["values"].get("$10") or "").strip(),
                                 "data_pub": str(r["values"].get("DataD") or "")[:8]})
    for d in docs:
        pub = d["data_pub"]
        pub_iso = f"{pub[:4]}-{pub[4:6]}-{pub[6:8]}" if len(pub) == 8 else None
        recent = pub_iso is not None and pub_iso >= (today - timedelta(days=31 * PRESENCA_REFRESH_MONTHS)).isoformat()
        url = f"{PRESINT}/{d['unid']}?OpenDocument"
        try:
            page = fetch(dl, url, refresh=refresh and recent).text("latin-1")
        except Exception as e:
            log(f"  presença {d['unid']}: {e!r}")
            continue
        t = parse_presenca(page)
        mes = MESES.get(fold(t.mes_nome).lower()) or MESES.get(fold(d["titulo"].split()[-1]).lower() if d["titulo"] else "", 0)
        if not mes or not pub_iso:
            continue
        ano = int(pub_iso[:4]) - (1 if mes > int(pub_iso[5:7]) else 0)
        tables.append({"ano": ano, "mes": mes, "publicado": pub_iso, "url": url, "linhas": t.linhas,
                       "sessoes": t.sessoes_total, "ordinarias": t.sessoes_ordinarias, "extraordinarias": t.sessoes_extraordinarias})
    # A month published twice (a correction): keep the latest publication.
    best: dict[tuple[int, int], dict] = {}
    for tb in tables:
        k = (tb["ano"], tb["mes"])
        if k not in best or tb["publicado"] > best[k]["publicado"]:
            best[k] = tb
    return sorted(best.values(), key=lambda t: (t["ano"], t["mes"])), docs


# --- bills -----------------------------------------------------------------------------------------------

def search_prefix(dl: Downloader, db: str, view: str, prefix: str, refresh: bool, depth: int = 0) -> list[dict]:
    url = f"{LN1}/{db}/{view}?SearchView&Query=FIELD%20prop_cod_prop%20CONTAINS%20{prefix}*&SearchMax=0"
    rows = parse_search_rows(fetch(dl, url, refresh=refresh).text("utf-8"))
    if len(rows) < SEARCH_CAP or depth >= 4:
        return rows
    out: list[dict] = []
    for d in "0123456789":
        out.extend(search_prefix(dl, db, view, prefix + d, refresh, depth + 1))
    return out


def load_proposicoes(dl: Downloader, from_year: int, refresh: bool) -> tuple[list[dict], dict[str, int]]:
    today = date.today()
    rows: dict[str, dict] = {}
    counts: Counter = Counter()
    for lg in LEGISLATURAS:
        y0, y1 = int(lg["inicio"][:4]), min(int(lg["fim"][:4]), today.year)
        for tipo, view in VIEWS.items():
            for y in range(max(y0, from_year), y1 + 1):
                if lg is LEGISLATURAS[0] and y == int(lg["fim"][:4]):
                    pass          # January of the last year still belongs to the old legislature's database
                rf = refresh and lg is LEGISLATURAS[-1] and y >= today.year - 1
                try:
                    found = search_prefix(dl, lg["scpro"], view, f"{y}{COD_TIPO[tipo]}", rf)
                except Exception as e:
                    log(f"  {lg['scpro']} {tipo} {y}: {e!r}")
                    continue
                for r in found:
                    p = prop_from_code(r["cod"])
                    if p is None or p[0] != tipo:
                        continue
                    t, n, a = p
                    pid = f"{t}-{n}/{a}"
                    if pid in rows:
                        continue
                    counts[f"{a}/{t}"] += 1
                    rows[pid] = {"id": pid, "tipo": t, "numero": str(n), "ano": a, "ementa": r["ementa"], "data": r["data"],
                                 "autores": r["autores"], "autores_raw": ", ".join(r["autores"]), "codigo": r["cod"],
                                 "url": f"{LN1}{r['url']}"}
    return list(rows.values()), dict(sorted(counts.items()))


# --- Diário Oficial --------------------------------------------------------------------------------------

def load_do(dl: Downloader, first_day: str, refresh: bool) -> tuple[list[dict], dict]:
    """Text of every Parte II edition from ``first_day`` on that holds a plenary record (PDF text cached)."""
    cache = TextCache(dl)
    days = [d for d in calendar_dates(fetch(dl, f"{IOERJ}/do_seleciona_data.php", refresh=refresh).text("latin-1")) if d >= first_day]
    recent = (date.today() - timedelta(days=DO_REFRESH_DAYS)).isoformat()
    out: list[dict] = []
    stats = {"datas": len(days), "edicoes": 0, "com_registro": 0, "erros": []}
    for n, day in enumerate(days):
        try:
            guids = parte_ii_guids(fetch(dl, edition_url(day), refresh=refresh and day >= recent).text("latin-1"))
        except Exception as e:
            stats["erros"].append({"data": day, "erro": repr(e)[:160]})
            continue
        for k, guid in enumerate(guids):
            url = pdf_url(guid)
            try:
                text, meta = cache.fetch(url, keep=has_plenary_record)
            except Exception as e:
                stats["erros"].append({"data": day, "url": url, "erro": repr(e)[:160]})
                log(f"  DO {day}: {e!r}")
                continue
            stats["edicoes"] += 1
            if text:
                stats["com_registro"] += 1
                out.append({"data": day, "parte": k, "url": url, "text": text, "sha256": meta["sha256"]})
        if n % 200 == 0:
            log(f"  DO {day}: {stats['edicoes']} editions, {stats['com_registro']} with a plenary record, {dl.requests_made} requests")
    return out, stats


def objeto_of(materia: str | None, frase: str | None, anuncio: str | None = None) -> str:
    """What was put to the vote: the announcement says veto or redação final; the line before the vote
    ("Em votação o Destaque ...") and the result sentence say emenda, substitutivo or requerimento."""
    near = f"{materia or ''} {frase or ''}".upper()
    head = (anuncio or "").upper()[:200]
    if re.search(r"\bVETOS?\b", near) or re.search(r"\bVETO\b", head):
        return "veto"
    if re.search(r"\bDESTAQUE|\bEMENDA\b|\bEMENDAS\b", near) and not re.search(r"PROPOSTA DE EMENDA|EMENDA CONSTITUCIONAL", near):
        return "emenda"
    if "REDAÇÃO FINAL" in near or "REDACAO FINAL" in near or "REDAÇÃO FINAL" in head:
        return "redacao_final"
    if "SUBSTITUTIVO" in near:
        return "substitutivo"
    if re.search(r"\bREQUERIMENTO", near):
        return "requerimento"
    return "projeto"


def resultado_of(frase: str | None, objeto: str) -> str | None:
    s = (frase or "").lower()
    if not s:
        return None
    if "mantid" in s:
        return "mantido" if objeto == "veto" else "rejeitado"
    if "rejeitad" in s or "derrubad" in s:
        return "derrubado" if objeto == "veto" else "rejeitado"
    if "aprovad" in s:
        return "aprovado"
    if "prejudicad" in s:
        return "prejudicado"
    return None


def roster_for_date(day: str, ex: dict[tuple[int, int], set[str]]) -> tuple[set[str], str | None]:
    """Deputies in office on ``day``: the presence table of that month, else the latest earlier one."""
    y, m = int(day[:4]), int(day[5:7])
    keys = sorted(k for k in ex if k <= (y, m) and ex[k])
    if not keys:
        return set(), None
    k = keys[-1]
    return ex[k], f"{k[0]}-{k[1]:02d}"


def build_votacoes(editions: list[dict], resolver: NameResolver, ex: dict[tuple[int, int], set[str]],
                   props: dict[str, dict]) -> tuple[list[dict], dict, list[dict]]:
    stats: dict = {"atas": 0, "atas_repetidas": 0, "listas_nominais": 0, "conferidas": 0, "sem_contagem_impressa": 0,
                   "divergentes": [], "so_totais": 0, "fora_da_legislatura": 0, "por_ano": {}, "nomes_nao_casados": Counter(),
                   "sem_resultado": 0, "presidente_identificado": 0}
    seen_atas: set[tuple] = set()
    seen_votes: set[tuple] = set()
    atas_out: list[dict] = []
    out: list[dict] = []
    for ed in sorted(editions, key=lambda e: (e["data"], e["parte"])):
        for ata in parse_records(ed["text"]):
            key = (ata.data, ata.tipo, ata.numero)
            if key in seen_atas:
                stats["atas_repetidas"] += 1
                continue
            seen_atas.add(key)
            leg = legislatura_of(ata.data, LEGISLATURAS)
            if leg is None:
                continue
            stats["atas"] += 1
            stats["so_totais"] += len(ata.so_totais)
            atas_out.append({"data": ata.data, "tipo": ata.tipo, "numero": ata.numero, "presentes": len(ata.presentes),
                             "presentes_impresso": ata.presentes_impresso, "votos": len(ata.votos), "so_totais": len(ata.so_totais),
                             "fonte": ed["url"], "publicado": ed["data"]})
            for k, v in enumerate(ata.votos):
                stats["listas_nominais"] += 1
                votos: dict[str, str] = {}
                # Names per side as the list reads, after splitting run-ons ("Marcelo Dino Márcio Gualberto").
                names_count = {"sim": 0, "nao": 0, "abstencao": 0}
                for lado in ("sim", "nao", "abstencao"):
                    for nome in getattr(v, lado):
                        ids = resolver.resolve(nome)
                        names_count[lado] += max(1, len(ids))
                        if not ids:
                            stats["nomes_nao_casados"][nome] += 1
                        for i in ids:
                            votos[i] = lado
                contagem = {s: sum(1 for x in votos.values() if x == s) for s in ("sim", "nao", "abstencao")}
                contagem["presentes_votando"] = sum(contagem.values())
                printed = {s: v.impresso[s] for s in ("sim", "nao", "abstencao") if s in v.impresso}
                if not printed:
                    stats["sem_contagem_impressa"] += 1
                diverge = [s for s, n in printed.items() if n != names_count[s] and not (n == 0 and names_count[s] == 0)]
                vid = f"alerj:{ata.data}-{ata.tipo[:3].lower()}-{ata.numero}-{k}"
                if diverge:
                    stats["divergentes"].append({"id": vid, "data": ata.data, "impresso": printed, "nomes": names_count})
                    continue
                sig = (ata.data, ata.tipo, ata.numero, frozenset(v.sim), frozenset(v.nao))
                if sig in seen_votes:
                    continue
                seen_votes.add(sig)
                if printed:
                    stats["conferidas"] += 1
                presidente = None
                if v.presidente:
                    pids = resolver.resolve(v.presidente, count_unmatched=False)
                    presidente = pids[0] if len(pids) == 1 else None
                if presidente:
                    stats["presidente_identificado"] += 1
                    votos.setdefault(presidente, "presidindo")
                roster, roster_mes = roster_for_date(ata.data, ex)
                for i in roster:
                    votos.setdefault(i, "ausente")
                objeto = objeto_of(v.materia, v.resultado_frase, v.anuncio)
                resultado = resultado_of(v.resultado_frase, objeto)
                if resultado is None:
                    stats["sem_resultado"] += 1
                prop: dict = {"id": None, "tipo": None, "numero": None, "ano": None, "ementa": None, "autores": [], "autores_ids": []}
                if v.proposicao:
                    t, n, a = v.proposicao
                    pid = f"{t}-{n}/{a}"
                    base = props.get(pid, {})
                    prop = {"id": pid, "tipo": t, "numero": str(n), "ano": a, "ementa": base.get("ementa"),
                            "autores": list(base.get("autores", [])), "autores_ids": list(base.get("autores_ids", []))}
                    if not prop["ementa"] and v.anuncio:
                        # bills from before 2019: the announcement carries author and ementa
                        m = re.search(r"DE AUTORIA D[OAE]S?\s+(.+?),\s+QUE\s+(.+?)(?:\(|$)", v.anuncio)
                        if m:
                            prop["ementa"] = m.group(2).strip(" .")
                            prop["autores"] = prop["autores"] or [x.strip() for x in re.split(r",| E ", re.sub(r"^(?:DEPUTAD[OA]S?|SENHOR(?:ES)?)\s+", "", m.group(1))) if x.strip()]
                            prop["autores_ids"] = prop["autores_ids"] or [i for x in prop["autores"] for i in resolver.resolve(x, count_unmatched=False)]
                pa = stats["por_ano"].setdefault(ata.data[:4], {"nominais": 0})
                pa["nominais"] += 1
                out.append({
                    "id": vid, "data": ata.data, "hora": None, "legislatura": leg,
                    "sessao": {"tipo": f"Sessão {ata.tipo}", "numero": f"{ata.numero}ª Sessão {ata.tipo}", "fase": None},
                    "titulo": None if prop["id"] else f"Votação nominal, {ata.numero}ª Sessão {ata.tipo}", "proposicao": prop, "objeto": objeto, "resultado": resultado,
                    "resultado_frase": v.resultado_frase, "lado_vencedor": lado_vencedor(contagem), "contagem": contagem,
                    "impresso": v.impresso, "presidente": presidente, "presidente_nome": v.presidente, "roster_mes": roster_mes,
                    "votos": votos, "fonte": ed["url"],
                })
    stats["nomes_nao_casados"] = dict(stats["nomes_nao_casados"].most_common())
    return out, stats, atas_out


# --- main ------------------------------------------------------------------------------------------------

def run(args) -> int:
    refresh = not (args.offline or args.no_refresh)
    dl = Downloader(offline=args.offline)
    from_year = args.from_year
    today = date.today().isoformat()

    log("RJ: deputados ...")
    cards, perfis = load_roster(dl, refresh)
    log(f"  {len(cards)} deputados in the 12th and 13th legislatures, {len(perfis)} profiles")
    names_for: dict[str, list[str]] = {}
    nomes: dict[str, str] = {}
    for i, c in cards.items():
        p = perfis.get(i)
        # The card prints the parliamentary name; the profile heading is sometimes the civil name.
        nome = title_name(c["nome"])
        nomes[did(i)] = nome
        names_for[did(i)] = [x for x in (nome, p.nome if p else None) if x]
    resolver = NameResolver([{"id": i, "nome": ns[0], "nome_parlamentar": ns[-1]} for i, ns in names_for.items()], aliases=ALIASES_ALERJ)

    log("RJ: presença ...")
    tables, pres_docs = load_presenca(dl, args.presenca_from, refresh)
    presencas: list[dict] = []
    presenca_unmatched: Counter = Counter()
    ex: dict[tuple[int, int], set[str]] = defaultdict(set)
    for tb in tables:
        if f"{tb['ano']}-{tb['mes']:02d}" < LEGISLATURAS[0]["inicio"][:7]:
            continue
        for l in tb["linhas"]:
            ids = resolver.resolve(l["nome"], count_unmatched=False)
            if len(ids) != 1:
                presenca_unmatched[l["nome"]] += 1
                continue
            i = ids[0]
            ex[(tb["ano"], tb["mes"])].add(i)
            sess = tb["sessoes"]
            presencas.append({"ano": tb["ano"], "mes": tb["mes"], "deputado_nome": l["nome"], "deputado_id": i,
                              "faltas": l["faltas"], "faltas_abonadas": 0, "total_faltas": l["faltas"],
                              "sessoes": sess, "presencas": (sess - l["faltas"]) if sess is not None else None,
                              "dias": l["dias"]})
    log(f"  {len(tables)} monthly tables, {len(presencas)} rows, {len(presenca_unmatched)} names not matched: {dict(presenca_unmatched.most_common(10))}")

    log("RJ: proposições ...")
    prop_rows, prop_counts = load_proposicoes(dl, from_year, refresh)
    author_unmatched: Counter = Counter()
    for p in prop_rows:
        ids: list[str] = []
        for a in p["autores"]:
            r = resolver.resolve(a, count_unmatched=False)
            if not r:
                author_unmatched[a] += 1
            for i in r:
                if i not in ids:
                    ids.append(i)
        p["autores_ids"] = ids
        p["autores_outros"] = False
    log(f"  {len(prop_rows)} proposições; {len(author_unmatched)} author names not matched: {dict(author_unmatched.most_common(10))}")
    props = {p["id"]: p for p in prop_rows}

    log("RJ: Diário Oficial ...")
    editions, dostats = load_do(dl, LEGISLATURAS[0]["inicio"], refresh)
    log(f"  {dostats['edicoes']} Parte II editions, {dostats['com_registro']} with a plenary record, {len(dostats['erros'])} errors")
    votacoes, vstats, atas = build_votacoes(editions, resolver, ex, props)
    vstats["do"] = dostats
    log(f"  {vstats['atas']} session records, {vstats['listas_nominais']} named roll calls, {len(votacoes)} kept,"
        f" {len(vstats['divergentes'])} not matching the printed totals, {vstats['so_totais']} with totals only;"
        f" names not matched: {dict(list(vstats['nomes_nao_casados'].items())[:15])}")

    # --- deputados ---------------------------------------------------------------------------------------
    photos = config.photos_dir(UF)
    deputados: list[Deputado] = []
    for i, c in cards.items():
        p = perfis.get(i)
        legs = sorted(c["legs"])
        ppl: dict[str, str] = {}
        for leg in legs:
            lg = next(x for x in LEGISLATURAS if x["numero"] == leg)
            party = party_on(p.partidos, min(lg["fim"], today)) if p else None
            ppl[str(leg)] = party or c["legs"][leg] or ""
            if not ppl[str(leg)]:
                del ppl[str(leg)]
        partido = ppl.get(str(legs[-1])) if legs else None
        foto = save_photo(dl, c["foto"], str(i), photos) if c.get("foto") else None
        deputados.append(Deputado(
            id=did(i), nome=nomes[did(i)], nome_parlamentar=nomes[did(i)], partido=partido, legislaturas=legs,
            partidos_por_legislatura=ppl, situacao="em_exercicio" if c["atual"] else "fora_de_exercicio", foto=foto,
            telefone=p.telefone if p else None, email=p.email if p else None, perfil_url=f"{ALERJ}/Deputados/PerfilDeputado/{i}"))

    meses = sorted({(t["ano"], t["mes"]) for t in tables})
    snapshot = {
        "uf": UF,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "legislatures": [{k: lg[k] for k in ("numero", "inicio", "fim")} for lg in LEGISLATURAS],
        "deputados": [asdict(v) for v in sorted(deputados, key=lambda v: v.nome)],
        "votacoes": votacoes,
        "presencas": presencas,
        "proposicoes": sorted(prop_rows, key=lambda r: (r["tipo"], -r["ano"], int(r["numero"]))),
        "atas": atas,
        "stats": {
            "votacoes": vstats,
            "presenca": {"tabelas": len(tables), "documentos": len(pres_docs),
                         "meses": [f"{a}-{m:02d}" for a, m in meses],
                         "sessoes_deliberativas": sum(t["sessoes"] or 0 for t in tables
                                                      if f"{t['ano']}-{t['mes']:02d}" >= LEGISLATURAS[0]["inicio"][:7])},
            "proposicoes": {"total": len(prop_rows), "por_tipo_ano": prop_counts,
                            "unmatched_authors": dict(author_unmatched.most_common()), "com_outros": 0},
            "deputados": {"em_exercicio": sum(1 for v in deputados if v.situacao == "em_exercicio"),
                          "com_foto": sum(1 for v in deputados if v.foto)},
            "presenca_unmatched": sorted(presenca_unmatched),
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
