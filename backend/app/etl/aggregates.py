"""Pure functions that turn the snapshot into per-deputado / per-votação aggregates.

Everything here works on plain dicts (the JSON shapes of data/snapshot.json) so it can be
unit-tested with small fixtures and reused by the static export.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

VOTO_CAST = ("sim", "nao", "abstencao")
# obstrucao: the deputy was in the plenary and his party declared obstruction (ALESP panel); it is
# neither a vote cast nor an absence, so it counts towards "em exercício" but not towards "votou".
VOTO_ALL = ("sim", "nao", "abstencao", "obstrucao", "ausente", "presidindo")
VOTO_PARTY = ("sim", "nao", "abstencao", "obstrucao")


def legislatura_of(data: str | None, legislaturas: list[dict]) -> int | None:
    if not data:
        return None
    for lg in legislaturas:
        if lg["inicio"] <= data[:10] <= lg["fim"]:
            return lg["numero"]
    return None


def lado_vencedor(contagem: dict) -> str | None:
    """'sim' / 'nao' by simple majority of the votes cast; None on a tie or without votes."""
    s, n = contagem.get("sim", 0), contagem.get("nao", 0)
    if s == n:
        return None
    return "sim" if s > n else "nao"


def party_of(deputado: dict, legislatura: int | None) -> str | None:
    if legislatura is not None:
        p = deputado.get("partidos_por_legislatura", {}).get(str(legislatura))
        if p:
            return p
    return deputado.get("partido")


def party_breakdown(votos: dict[str, str], party_by_id: dict[str, str | None]) -> dict[str, dict[str, int]]:
    """{partido: {sim, nao, abstencao}} over the votes cast; zero sides are omitted to keep the JSON small."""
    out: dict[str, Counter] = defaultdict(Counter)
    for vid, voto in votos.items():
        if voto in VOTO_PARTY:
            out[party_by_id.get(vid) or "?"][voto] += 1
    return {p: {k: c[k] for k in VOTO_PARTY if c[k]} for p, c in sorted(out.items())}


def party_majority(votos: dict[str, str], party_by_id: dict[str, str | None], partido: str | None) -> str | None:
    """Majority side (sim/nao) among the party's members who voted sim/nao; None if < 2 voted or tie."""
    if not partido:
        return None
    c = Counter(v for vid, v in votos.items() if v in ("sim", "nao") and party_by_id.get(vid) == partido)
    if c["sim"] + c["nao"] < 2 or c["sim"] == c["nao"]:
        return None
    return "sim" if c["sim"] > c["nao"] else "nao"


def _empty_votes() -> dict[str, int]:
    return {k: 0 for k in VOTO_ALL}


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def presenca_aggregates(rows: Iterable[dict]) -> dict[str, Any]:
    """rows: presencas of one deputado -> {por_ano: {ano: {faltas, abonadas, total, meses}}, por_mes: {...}}"""
    por_ano: dict[str, dict[str, int]] = {}
    por_mes: dict[str, dict[str, int]] = {}
    for r in sorted(rows, key=lambda r: (r["ano"], r["mes"])):
        y = str(r["ano"])
        a = por_ano.setdefault(y, {"faltas": 0, "abonadas": 0, "total": 0, "meses": 0})
        a["faltas"] += r["faltas"]
        a["abonadas"] += r["faltas_abonadas"]
        a["total"] += r["total_faltas"]
        a["meses"] += 1
        por_mes[f"{r['ano']}-{r['mes']:02d}"] = {"faltas": r["faltas"], "abonadas": r["faltas_abonadas"], "total": r["total_faltas"]}
    return {"por_ano": por_ano, "por_mes": por_mes}


def enrich_votacoes(votacoes: list[dict], deputados: list[dict], legislaturas: list[dict]) -> list[dict]:
    """Add legislatura, lado_vencedor and por_partido to each votação (returns new dicts, votos kept)."""
    by_id = {v["id"]: v for v in deputados}
    out = []
    for vt in votacoes:
        leg = vt.get("legislatura") or legislatura_of(vt.get("data"), legislaturas)
        # SP prints each voter's party on the vote itself ("partidos"); use it when present.
        printed = vt.get("partidos") or {}
        party_by_id = {vid: printed.get(vid) or (party_of(by_id[vid], leg) if vid in by_id else None) for vid in vt["votos"]}
        e = dict(vt)
        e["legislatura"] = leg
        e["lado_vencedor"] = lado_vencedor(vt["contagem"])
        e["por_partido"] = party_breakdown(vt["votos"], party_by_id)
        e["_party_by_id"] = party_by_id
        out.append(e)
    return out


def deputado_aggregates(deputados: list[dict], votacoes: list[dict], presencas: list[dict],
                        proposicoes: list[dict], legislaturas: list[dict]) -> dict[str, dict[str, Any]]:
    """Per-deputado block for the frontend. ``votacoes`` must come from enrich_votacoes()."""
    agg: dict[str, dict[str, Any]] = {}
    for v in deputados:
        agg[v["id"]] = {
            "presenca": {"por_ano": {}, "por_mes": {}},
            "votos": {"por_legislatura": {}, "por_ano": {}, "total": _empty_votes()},
            "participacao": None, "com_maioria": None, "contra_partido": None,
            "_votou": 0, "_em_exercicio": 0, "_maioria_num": 0, "_maioria_den": 0, "_partido_num": 0, "_partido_den": 0,
            "proposicoes_por_tipo": {}, "proposicoes_total": 0, "votacoes_registradas": 0,
        }
    rows_by_id: dict[str, list[dict]] = defaultdict(list)
    for r in presencas:
        if r.get("deputado_id"):
            rows_by_id[r["deputado_id"]].append(r)
    for vid, rows in rows_by_id.items():
        if vid in agg:
            agg[vid]["presenca"] = presenca_aggregates(rows)

    for vt in votacoes:
        leg = str(vt.get("legislatura") or legislatura_of(vt.get("data"), legislaturas) or "?")
        ano = (vt.get("data") or "????")[:4]
        winner = vt.get("lado_vencedor") or lado_vencedor(vt["contagem"])
        party_by_id = vt.get("_party_by_id") or {}
        for vid, voto in vt["votos"].items():
            a = agg.get(vid)
            if a is None or voto not in VOTO_ALL:
                continue
            a["votos"]["total"][voto] += 1
            a["votos"]["por_legislatura"].setdefault(leg, _empty_votes())[voto] += 1
            a["votos"]["por_ano"].setdefault(ano, _empty_votes())[voto] += 1
            a["votacoes_registradas"] += 1
            if voto in VOTO_CAST:
                a["_votou"] += 1
                a["_em_exercicio"] += 1
            elif voto in ("ausente", "obstrucao"):
                a["_em_exercicio"] += 1
            if voto in ("sim", "nao") and winner in ("sim", "nao"):
                a["_maioria_den"] += 1
                a["_maioria_num"] += int(voto == winner)
            if voto in ("sim", "nao"):
                pm = party_majority(vt["votos"], party_by_id, party_by_id.get(vid))
                if pm is not None:
                    a["_partido_den"] += 1
                    a["_partido_num"] += int(voto != pm)

    for p in proposicoes:
        for vid in p.get("autores_ids", []):
            a = agg.get(vid)
            if a is None:
                continue
            a["proposicoes_por_tipo"].setdefault(p["tipo"], {})
            a["proposicoes_por_tipo"][p["tipo"]][str(p["ano"])] = a["proposicoes_por_tipo"][p["tipo"]].get(str(p["ano"]), 0) + 1
            a["proposicoes_total"] += 1

    for a in agg.values():
        a["participacao"] = _rate(a["_votou"], a["_em_exercicio"])
        a["com_maioria"] = _rate(a["_maioria_num"], a["_maioria_den"])
        a["contra_partido"] = a["_partido_num"]                       # count (the frontend prints it as an integer)
        a["contra_partido_taxa"] = _rate(a["_partido_num"], a["_partido_den"])
        a["contra_partido_base"] = a["_partido_den"]
        a["votos_cast"] = a["_votou"]
        for k in [k for k in a if k.startswith("_")]:
            del a[k]
    return agg
