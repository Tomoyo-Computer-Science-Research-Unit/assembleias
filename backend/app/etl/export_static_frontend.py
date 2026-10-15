"""Turn data/<uf>/snapshot.json into the static files the frontend reads.

    python -m app.etl.export_static_frontend [--uf RJ|SP] [--snapshot ...] [--out frontend/data/<uf>] [--fotos frontend/data/<uf>/fotos]

The frontend build copies frontend/data/<uf>/ into frontend/lib/ and public/fotos/ (scripts/use-uf.sh).
Writes, under --out:
  static-data.generated.json             everything the list/overview pages need (no per-deputado votes);
                                         shape = types in frontend/lib/static-api.ts
  static-votacoes/<votacao>.generated.json   {votos: {deputado_id: voto}} (":" in ids becomes "-")
  static-deputados/<casa-N>.generated.json   {votos: [...], proposicoes: [...]} newest first
and copies the photos to --fotos (downscaled to 160 px wide).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .. import config
from ..casas import casa_ufs
from .aggregates import enrich_votacoes, deputado_aggregates

EMENTA_MAX = 240
FOTO_MAX_W = 160


def log(*a: object) -> None:
    print(*a, file=sys.stderr, flush=True)


def fs_id(s: str) -> str:
    """Filesystem-safe id: 'cvd:390' -> 'cvd-390', '<unid>:0' -> '<unid>-0'."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", s)


def short(s: str | None, n: int = EMENTA_MAX) -> str | None:
    if s is None:
        return None
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def dump(path: Path, obj: object) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    path.write_text(data)
    return len(data.encode())


def copy_photo(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
        with Image.open(src) as im:
            im = im.convert("RGB")
            if im.width > FOTO_MAX_W:
                im = im.resize((FOTO_MAX_W, round(im.height * FOTO_MAX_W / im.width)), Image.LANCZOS)
            im.save(dst, "JPEG", quality=82, optimize=True)
    except ImportError:
        shutil.copyfile(src, dst)


SOURCE_KINDS_SP = [
    ("Votações no Plenário: lista anual (ALESP)", r"/alesp/votacoes-no-plenario"),
    ("Relatórios de verificação de votação (PDF, ALESP)", r"/ementario/votacoes/"),
    ("Presença em Plenário: lista de parlamentares (API do portal)", r"/lista-presenca-parlamentar/parlamentares/"),
    ("Presença em Plenário: meses de mandato (API do portal)", r"/mesesAnosMandatosParlamentar/"),
    ("Presença em Plenário: sessões do mês (API do portal)", r"/lista-presenca-parlamentar/\d+/\d+/\d+"),
    ("Deputados: detalhes, filiações e mandatos (API do portal)", r"/parlamentar-portal/detalhes/"),
    ("Dados abertos: deputados.xml", r"/repositorioDados/deputados/deputados\.xml"),
    ("Dados abertos: proposituras", r"/proposituras\.zip"),
    ("Dados abertos: autores das proposituras", r"/documento_autor\.zip"),
    ("Dados abertos: naturezas dos documentos", r"/naturezasSpl\.xml"),
    ("Fotos dos deputados (ALESP)", r"/legis/biografia/fotos/"),
]


def summarize_sources(sources: list[dict], uf: str = "RJ") -> list[dict]:
    kinds = SOURCE_KINDS.get(uf, [])
    out = []
    for name, pat in kinds:
        rows = [s for s in sources if re.search(pat, s["url"], re.I)]
        if rows:
            out.append({"name": name, "url": rows[0]["url"], "accessed_at": max(r["accessed_at"] for r in rows),
                        "first_accessed_at": min(r["accessed_at"] for r in rows), "count": len(rows)})
    return out


def build(snapshot: dict) -> tuple[dict, dict[str, dict], dict[str, dict]]:
    """Return (static_data, per_votacao_files, per_deputado_files) as python objects."""
    uf = snapshot.get("uf") or ""
    legs = snapshot["legislatures"]
    deputados = snapshot["deputados"]
    votacoes = enrich_votacoes(sorted(snapshot["votacoes"], key=lambda v: (v["data"] or "", v["id"]), reverse=True), deputados, legs)
    presencas = snapshot["presencas"]
    proposicoes = snapshot["proposicoes"]
    agg = deputado_aggregates(deputados, votacoes, presencas, proposicoes, legs)
    vstats = snapshot["stats"]["votacoes"]

    # --- per-deputado files -------------------------------------------------------------------
    votos_by_v: dict[str, list[dict]] = defaultdict(list)
    for vt in votacoes:  # already newest first
        for vid, voto in vt["votos"].items():
            votos_by_v[vid].append({"votacao_id": vt["id"], "voto": voto})   # shape: static-api.ts VotoLinha
    props_by_v: dict[str, list[dict]] = defaultdict(list)
    for p in sorted(proposicoes, key=lambda p: (p["data"] or "", p["id"]), reverse=True):
        for vid in p.get("autores_ids", []):
            # Only what the site shows: the ALESP alone has ~100k proposições since 2019 (86k indicações).
            props_by_v[vid].append({"id": p["id"], "tipo": p["tipo"], "numero": p["numero"], "ano": p["ano"],
                                    "ementa": p["ementa"], "data": p["data"]})
    per_deputado = {v["id"]: {"id": v["id"], "votos": votos_by_v.get(v["id"], []), "proposicoes": props_by_v.get(v["id"], [])}
                    for v in deputados}

    # --- static-data -------------------------------------------------------------------------
    vrows = []
    for v in sorted(deputados, key=lambda v: v["nome"]):
        a = agg[v["id"]]
        vrows.append({
            "id": v["id"], "nome": v["nome"], "nome_parlamentar": v["nome_parlamentar"], "partido": v["partido"],
            "partidos_por_legislatura": v["partidos_por_legislatura"], "legislaturas": v["legislaturas"],
            "situacao": v["situacao"], "foto": ("fotos/" + Path(v["foto"]).name) if v.get("foto") else None,
            "gabinete": v.get("gabinete"), "telefone": v.get("telefone"), "email": v.get("email"),
            "perfil_url": v.get("perfil_url"),
            "presenca": a["presenca"], "votos": a["votos"], "participacao": a["participacao"],
            "com_maioria": a["com_maioria"], "contra_partido": a["contra_partido"],
            "contra_partido_taxa": a["contra_partido_taxa"], "contra_partido_base": a["contra_partido_base"],
            "proposicoes_por_tipo": a["proposicoes_por_tipo"],
            "totais": {"proposicoes": a["proposicoes_total"], "votos_cast": a["votos_cast"],
                       "votacoes_registradas": a["votacoes_registradas"]},
        })
    vt_rows = []
    per_votacao = {}
    for vt in votacoes:
        p = vt["proposicao"]
        vt_rows.append({   # shape of frontend/lib/static-api.ts `Votacao`; per-deputado votes are NOT here
            "id": vt["id"], "data": vt["data"], "hora": vt["hora"], "legislatura": vt["legislatura"], "sessao": vt["sessao"],
            "proposicao": {"id": p.get("id") or "", "tipo": p.get("tipo") or "", "numero": p.get("numero") or "",
                           "ano": p.get("ano"), "ementa": p.get("ementa") or "",
                           "autores": p.get("autores", []), "autores_ids": p.get("autores_ids", [])},
            "objeto": vt.get("objeto"), "resultado": vt["resultado"], "contagem": vt["contagem"],
            "lado_vencedor": vt["lado_vencedor"], "por_partido": vt["por_partido"], "presidente": vt.get("presidente"),
            "ausentes": sum(1 for x in vt["votos"].values() if x == "ausente"), "fonte": vt["fonte"],
            **({"titulo": vt["titulo"]} if vt.get("titulo") else {}),
        })
        per_votacao[vt["id"]] = {"id": vt["id"], "data": vt["data"], "hora": vt["hora"], "sessao": vt["sessao"],
                                 "proposicao": p, "objeto": vt.get("objeto"), "resultado": vt["resultado"],
                                 "resultado_frase": vt.get("resultado_frase"), "contagem": vt["contagem"],
                                 "lado_vencedor": vt["lado_vencedor"], "por_partido": vt["por_partido"],
                                 "presidente": vt.get("presidente"), "roster_mes": vt.get("roster_mes"),
                                 "votos": vt["votos"], "fonte": vt["fonte"],
                                 **{k: vt[k] for k in ("titulo", "presentes_painel", "impresso", "sem_voto_presentes") if k in vt}}

    meses = sorted({f"{r['ano']}-{r['mes']:02d}" for r in presencas})
    prop_por_tipo: Counter = Counter(p["tipo"] for p in proposicoes)
    prop_por_ano: dict[str, Counter] = defaultdict(Counter)
    for p in proposicoes:
        prop_por_ano[str(p["ano"])][p["tipo"]] += 1
    nomes = sorted(set(vstats.get("unmatched_names", {})) | set(snapshot["stats"].get("proposicoes", {}).get("unmatched_authors", {}))
                   | set(snapshot["stats"].get("presenca_unmatched", [])))
    por_ano_vot: dict[str, Counter] = defaultdict(Counter)
    for vt in votacoes:
        por_ano_vot[vt["data"][:4]]["votacoes"] += 1
        por_ano_vot[vt["data"][:4]][f"resultado_{vt['resultado'] or 'indefinido'}"] += 1
    stats = {
            "votacoes": {"candidatos": vstats.get("candidates_in_range"), "lidos": vstats.get("docs_fetched"),
                         "com_votacao": vstats.get("docs_with_roll_call"), "total": len(votacoes),
                         "sem_resultado": sum(1 for vt in votacoes if not vt["resultado"]),
                         "sem_presidente": sum(1 for vt in votacoes if not vt.get("presidente")),
                         "contagem_mismatches": vstats.get("contagem_mismatches"),
                         "impresso_discrepancies": len(vstats.get("impresso_discrepancies", [])),
                         "docs_failed": len(vstats.get("docs_failed", [])),
                         "por_ano": {y: dict(vstats.get("por_ano", {}).get(y, {}), **por_ano_vot.get(y, {}))
                                     for y in sorted(set(vstats.get("por_ano", {})) | set(por_ano_vot))}},
            "presenca": {"meses_com_dado": len(meses), "primeiro_mes": meses[0] if meses else None,
                         "ultimo_mes": meses[-1] if meses else None, "linhas": len(presencas)},
            "proposicoes": {"total": len(proposicoes), "por_tipo": dict(prop_por_tipo),
                            "por_ano": {y: dict(c) for y, c in sorted(prop_por_ano.items())},
                            "sem_autor_casado": sum(1 for p in proposicoes if not p.get("autores_ids")
                                                    and any(not _inst(a) for a in p["autores"]))},
            "nomes_nao_casados": nomes,
    }
    if uf in STATS_BUILDERS:      # each casa reports the coverage counts its sources allow
        stats = STATS_BUILDERS[uf](snapshot, votacoes, presencas, proposicoes, meses, prop_por_tipo, prop_por_ano, por_ano_vot)
    static = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "snapshot_generated_at": snapshot["generated_at"],
        "legislaturas": legs,
        "deputados": vrows,
        "votacoes": vt_rows,
        "presenca_meses": meses,
        "stats": stats,
        "sources": summarize_sources(snapshot["sources"], uf),
    }
    return static, per_votacao, per_deputado


def sp_stats(snapshot: dict, votacoes: list[dict], presencas: list[dict], proposicoes: list[dict], meses: list[str],
             prop_por_tipo: Counter, prop_por_ano: dict, por_ano_vot: dict) -> dict:
    """Coverage block for the ALESP: same top-level keys for every casa, with the counts its sources allow."""
    vs = snapshot["stats"]["votacoes"]
    ps = snapshot["stats"]["presenca"]
    votos = Counter(x for vt in votacoes for x in vt["votos"].values())
    return {
        "votacoes": {"total": len(votacoes), "listadas_pela_alesp": vs.get("listadas"),
                     "relatorios_com_falha": len(vs.get("falhas", [])),
                     "escolhas_fora": len(vs.get("escolhas", [])),
                     "sem_resultado_impresso": vs.get("sem_resultado_impresso", 0),
                     "sem_quorum_inferido": vs.get("sem_quorum_inferido", 0),
                     "sem_resultado": sum(1 for vt in votacoes if not vt["resultado"]),
                     "impresso_discrepancies": len(vs.get("impresso_discrepancies", [])),
                     "nomes_sem_cadastro": vs.get("nomes_sem_cadastro", 0),
                     "votos": {k: votos[k] for k in ("sim", "nao", "abstencao", "obstrucao", "ausente", "presidindo") if votos[k]},
                     "por_ano": {y: dict(c) for y, c in sorted(por_ano_vot.items())}},
        "presenca": {"sessoes": ps.get("sessoes"), "sessoes_deliberativas": ps.get("sessoes_deliberativas"),
                     "meses_com_dado": len(meses), "primeiro_mes": meses[0] if meses else None,
                     "ultimo_mes": meses[-1] if meses else None, "linhas": len(presencas),
                     "meses_consultados": ps.get("pedidos"), "meses_vazios": ps.get("meses_vazios"),
                     "marcas": ps.get("marcas", {})},
        "proposicoes": {"total": len(proposicoes), "por_tipo": dict(prop_por_tipo),
                        "por_ano": {y: dict(c) for y, c in sorted(prop_por_ano.items())},
                        "sem_autor_deputado": sum(1 for p in proposicoes if not p.get("autores_ids"))},
        "nomes_nao_casados": sorted(vs.get("unmatched_names", {})),
    }


SOURCE_KINDS_RJ = [
    ("Deputados por legislatura (alerj.rj.gov.br)", r"/Deputados/QuemSao"),
    ("Perfis dos deputados: partidos e contato (alerj.rj.gov.br)", r"/Deputados/PerfilDeputado/"),
    ("Fotos dos deputados (alerj.rj.gov.br)", r"/Uploads/PerfilDeputado/"),
    ("Presenças: índice mensal (ordemdia.nsf)", r"/ordemdia\.nsf/[0-9a-f]{32}\?ReadViewEntries"),
    ("Presenças: tabelas mensais (ordemdia.nsf)", r"/ordemdia\.nsf/[0-9a-f]{32}/[0-9A-Fa-f]{32}\?OpenDocument"),
    ("Proposições da 12ª legislatura (scpro1923.nsf)", r"/scpro1923\.nsf/"),
    ("Proposições da 13ª legislatura (scpro2327.nsf)", r"/scpro2327\.nsf/"),
    ("Diário Oficial: calendário de edições (ioerj)", r"/do_seleciona_data\.php"),
    ("Diário Oficial: edições do dia (ioerj)", r"/do_seleciona_edicao\.php"),
    ("Diário Oficial Parte II: PDFs lidos (ioerj)", r"/mostra_edicao\.php\?k="),
]


def rj_stats(snapshot: dict, votacoes: list[dict], presencas: list[dict], proposicoes: list[dict], meses: list[str],
             prop_por_tipo: Counter, prop_por_ano: dict, por_ano_vot: dict) -> dict:
    """Coverage block for the ALERJ."""
    vs = snapshot["stats"]["votacoes"]
    ps = snapshot["stats"]["presenca"]
    do = vs.get("do", {})
    votos = Counter(x for vt in votacoes for x in vt["votos"].values())
    return {
        "votacoes": {"total": len(votacoes), "edicoes_do_lidas": do.get("edicoes"), "edicoes_com_ata": do.get("com_registro"),
                     "atas_de_sessao": vs.get("atas"), "listas_nominais": vs.get("listas_nominais"),
                     "conferidas_com_a_contagem": vs.get("conferidas"), "sem_contagem_impressa": vs.get("sem_contagem_impressa"),
                     "fora_por_divergir_da_contagem": len(vs.get("divergentes", [])),
                     "so_com_totais": vs.get("so_totais"), "sem_resultado": sum(1 for vt in votacoes if not vt["resultado"]),
                     "votos": {k: votos[k] for k in ("sim", "nao", "abstencao", "ausente", "presidindo") if votos[k]},
                     "por_ano": {y: dict(c) for y, c in sorted(por_ano_vot.items())}},
        "presenca": {"tabelas_mensais": ps.get("tabelas"), "meses_com_dado": len(meses),
                     "primeiro_mes": meses[0] if meses else None, "ultimo_mes": meses[-1] if meses else None,
                     "linhas": len(presencas), "sessoes_deliberativas": ps.get("sessoes_deliberativas"),
                     "nomes_nao_casados": len(snapshot["stats"].get("presenca_unmatched", []))},
        "proposicoes": {"total": len(proposicoes), "por_tipo": dict(prop_por_tipo),
                        "por_ano": {y: dict(c) for y, c in sorted(prop_por_ano.items())},
                        "sem_autor_deputado": sum(1 for p in proposicoes if not p.get("autores_ids"))},
        "nomes_nao_casados": sorted(set(vs.get("nomes_nao_casados", {})) | set(snapshot["stats"].get("presenca_unmatched", []))),
    }


# Per-casa source labels and coverage blocks.
SOURCE_KINDS: dict[str, list[tuple[str, str]]] = {"SP": SOURCE_KINDS_SP, "RJ": SOURCE_KINDS_RJ}
STATS_BUILDERS = {"SP": sp_stats, "RJ": rj_stats}


def _inst(a: str) -> bool:
    from ..names import is_institutional
    return is_institutional(a)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uf", choices=casa_ufs(), default="RJ", type=str.upper)
    ap.add_argument("--snapshot", type=Path, default=None, help="default: data/<uf>/snapshot.json")
    ap.add_argument("--out", type=Path, default=None, help="default: frontend/data/<uf>")
    ap.add_argument("--fotos", type=Path, default=None, help="default: frontend/data/<uf>/fotos")
    ap.add_argument("--no-fotos", action="store_true")
    args = ap.parse_args(argv)
    args.snapshot = args.snapshot or config.snapshot_path(args.uf)
    args.out = args.out or config.FRONTEND_DATA_DIR / args.uf.lower()
    args.fotos = args.fotos or args.out / "fotos"

    snapshot = json.loads(args.snapshot.read_text())
    static, per_votacao, per_deputado = build(snapshot)

    out = args.out
    for sub in ("static-votacoes", "static-deputados"):
        if (out / sub).exists():
            shutil.rmtree(out / sub)
    n_main = dump(out / "static-data.generated.json", static)
    n_vot = sum(dump(out / "static-votacoes" / f"{fs_id(k)}.generated.json", v) for k, v in per_votacao.items())
    n_ver = sum(dump(out / "static-deputados" / f"{fs_id(k)}.generated.json", v) for k, v in per_deputado.items())
    log(f"static-data.generated.json: {n_main/1024:.0f} KB ({len(static['deputados'])} deputados, {len(static['votacoes'])} votações)")
    log(f"static-votacoes/: {len(per_votacao)} files, {n_vot/1024:.0f} KB")
    log(f"static-deputados/: {len(per_deputado)} files, {n_ver/1024:.0f} KB")
    if not args.no_fotos:
        n = 0
        if args.fotos.exists():
            shutil.rmtree(args.fotos)
        for v in snapshot["deputados"]:
            if v.get("foto"):
                src = config.photos_dir(args.uf).parent / v["foto"]
                if src.exists():
                    copy_photo(src, args.fotos / src.name)
                    n += 1
        total = sum(p.stat().st_size for p in args.fotos.glob("*.jpg")) if args.fotos.exists() else 0
        log(f"fotos: {n} files, {total/1024:.0f} KB under {args.fotos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
