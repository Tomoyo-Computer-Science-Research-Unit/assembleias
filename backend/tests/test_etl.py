"""Party majority, aggregates per deputado (obstrução included) and the static export shape (small fixtures)."""
import json

from app.etl import export_static_frontend as esf
from app.etl.aggregates import enrich_votacoes, lado_vencedor, party_breakdown, party_majority, deputado_aggregates
from app.names import NameResolver, split_authors

DEPUTADOS = [
    {"id": "cvd:1", "nome": "Alana Passos", "nome_parlamentar": "Alana Passos", "partido": "PL", "partidos_por_legislatura": {"12": "PL"}},
    {"id": "cvd:2", "nome": "Carlo Caiado", "nome_parlamentar": "Carlo Caiado", "partido": "PSD", "partidos_por_legislatura": {"12": "PSD"}},
    {"id": "cvd:3", "nome": "Zico", "nome_parlamentar": "Zico", "partido": "PL", "partidos_por_legislatura": {"12": "PL"}},
    {"id": "cvd:4", "nome": "Poubel", "nome_parlamentar": "Poubel", "partido": "PL", "partidos_por_legislatura": {"12": "PL"}},
    {"id": "cvd:5", "nome": "Dr. Gilberto", "nome_parlamentar": "Dr. Gilberto", "partido": "PSD", "partidos_por_legislatura": {"12": "PSD"}},
]
LEGS = [{"numero": 12, "inicio": "2025-01-01", "fim": "2028-12-31"}]
PARTY = {"cvd:1": "PL", "cvd:2": "PSD", "cvd:3": "PL", "cvd:4": "PL", "cvd:5": "PSD"}


def test_party_majority_and_breakdown():
    votos = {"cvd:1": "sim", "cvd:3": "sim", "cvd:4": "nao", "cvd:2": "sim", "cvd:5": "presidindo"}
    assert party_majority(votos, PARTY, "PL") == "sim"
    assert party_majority(votos, PARTY, "PSD") is None          # only one PSD member voted
    assert party_majority({"cvd:1": "sim", "cvd:3": "nao"}, PARTY, "PL") is None   # tie
    assert party_breakdown(votos, PARTY) == {"PL": {"sim": 2, "nao": 1}, "PSD": {"sim": 1}}
    assert lado_vencedor({"sim": 3, "nao": 1}) == "sim" and lado_vencedor({"sim": 1, "nao": 1}) is None
    assert lado_vencedor({"sim": 0, "nao": 0}) is None


def _snapshot():
    votacoes = [
        {"id": "u1:0", "data": "2025-03-04", "hora": None, "sessao": {"tipo": "Sessão Ordinária", "numero": "1ª Sessão", "fase": "Ordem do Dia"},
         "proposicao": {"id": "PL-1/2025", "tipo": "PL", "numero": "1", "ano": 2025, "ementa": "E" * 300, "autores": ["ZICO"], "autores_ids": ["cvd:3"]},
         "objeto": "projeto", "resultado": "aprovado", "resultado_frase": "x", "contagem": {"sim": 3, "nao": 1, "abstencao": 0, "presentes_votando": 4},
         "presidente": "cvd:5", "roster_mes": "2025-03",
         "votos": {"cvd:1": "sim", "cvd:3": "sim", "cvd:4": "nao", "cvd:2": "sim", "cvd:5": "presidindo"}, "fonte": "https://x/u1?OpenDocument"},
        {"id": "u2:0", "data": "2025-03-05", "hora": None, "sessao": {"tipo": "Sessão Ordinária", "numero": "2ª Sessão", "fase": "Ordem do Dia"},
         "proposicao": {"id": "PL-2/2025", "tipo": "PL", "numero": "2", "ano": 2025, "ementa": "b", "autores": [], "autores_ids": []},
         "objeto": "veto", "resultado": "derrubado", "resultado_frase": "x", "contagem": {"sim": 0, "nao": 3, "abstencao": 1, "presentes_votando": 4},
         "presidente": "cvd:2", "roster_mes": "2025-03",
         "votos": {"cvd:1": "nao", "cvd:3": "nao", "cvd:4": "abstencao", "cvd:2": "nao", "cvd:5": "ausente"}, "fonte": "https://x/u2?OpenDocument"},
    ]
    presencas = [{"ano": 2025, "mes": 3, "deputado_nome": "ALANA PASSOS", "faltas": 2, "faltas_abonadas": 1, "total_faltas": 1, "deputado_id": "cvd:1"},
                 {"ano": 2025, "mes": 4, "deputado_nome": "ALANA PASSOS", "faltas": 0, "faltas_abonadas": 0, "total_faltas": 0, "deputado_id": "cvd:1"}]
    proposicoes = [{"id": "PL-1/2025", "tipo": "PL", "numero": "1", "ano": 2025, "ementa": "E", "data": "2025-02-01", "autores": ["ZICO", "POUBEL"],
                    "autores_raw": "DEPUTADO ZICO E DEPUTADO POUBEL", "autores_ids": ["cvd:3", "cvd:4"], "autores_outros": False, "comissoes": [], "unid": "x", "legislatura_db": "scpro.nsf"},
                   {"id": "REQINF-9/2026", "tipo": "REQINF", "numero": "9", "ano": 2026, "ementa": "R", "data": "2026-01-10", "autores": ["ZICO"],
                    "autores_raw": "DEPUTADO ZICO", "autores_ids": ["cvd:3"], "autores_outros": False, "comissoes": [], "unid": "y", "legislatura_db": "scpro.nsf"}]
    vs = [dict(v, legislaturas=[12], situacao="em_exercicio", foto="photos/1.jpg" if v["id"] == "cvd:1" else None,
               gabinete=None, telefone=None, email=None, perfil_url=None) for v in DEPUTADOS]
    return {"generated_at": "2026-10-14T00:00:00+00:00", "legislatures": LEGS, "deputados": vs, "votacoes": votacoes,
            "presencas": presencas, "proposicoes": proposicoes,
            "stats": {"votacoes": {"candidates_in_range": 2, "docs_fetched": 2, "docs_with_roll_call": 2, "por_ano": {"2025": {"candidatos": 2, "lidos": 2}},
                                   "unmatched_names": {}, "contagem_mismatches": 0, "impresso_discrepancies": [], "docs_failed": []},
                      "proposicoes": {"unmatched_authors": {}}, "presenca_unmatched": []},
            "sources": [{"name": "GET https://x", "url": "https://x/discvot.nsf/" + "a" * 32 + "/" + "b" * 32 + "?OpenDocument", "accessed_at": "2026-10-14T00:00:00+00:00"}]}


def test_deputado_aggregates():
    snap = _snapshot()
    vts = enrich_votacoes(snap["votacoes"], snap["deputados"], LEGS)
    assert vts[0]["lado_vencedor"] == "sim" and vts[0]["por_partido"]["PL"] == {"sim": 2, "nao": 1}
    agg = deputado_aggregates(snap["deputados"], vts, snap["presencas"], snap["proposicoes"], LEGS)
    zico = agg["cvd:3"]
    assert zico["votos"]["por_ano"]["2025"] == {"sim": 1, "nao": 1, "abstencao": 0, "obstrucao": 0, "ausente": 0, "presidindo": 0}
    assert zico["participacao"] == 1.0 and zico["com_maioria"] == 1.0 and zico["contra_partido"] == 0 and zico["contra_partido_taxa"] == 0.0
    assert zico["proposicoes_por_tipo"] == {"PL": {"2025": 1}, "REQINF": {"2026": 1}} and zico["proposicoes_total"] == 2
    poubel = agg["cvd:4"]
    assert poubel["com_maioria"] == 0.0 and poubel["contra_partido"] == 1 and poubel["contra_partido_taxa"] == 1.0
    gil = agg["cvd:5"]
    assert gil["votos"]["total"]["presidindo"] == 1 and gil["votos"]["total"]["ausente"] == 1 and gil["participacao"] == 0.0
    alana = agg["cvd:1"]
    assert alana["presenca"]["por_ano"]["2025"] == {"faltas": 2, "abonadas": 1, "total": 1, "meses": 2}
    assert alana["presenca"]["por_mes"]["2025-03"] == {"faltas": 2, "abonadas": 1, "total": 1}


def test_export_shape(tmp_path):
    snap = _snapshot()
    static, per_vot, per_ver = esf.build(snap)
    assert {"generated_at", "legislaturas", "deputados", "votacoes", "presenca_meses", "stats", "sources"} <= set(static)
    row = static["votacoes"][0]
    assert row["id"] == "u2:0" and row["data"] == "2025-03-05"           # newest first
    assert "votos" not in row and row["por_partido"] == {"PL": {"nao": 2, "abstencao": 1}, "PSD": {"nao": 1}}
    assert row["sessao"]["numero"] == "2ª Sessão" and row["fonte"].endswith("?OpenDocument") and row["proposicao"]["autores"] == []
    assert static["votacoes"][1]["proposicao"]["ementa"]  # ementa completa no nucleo; o site quebra linha em vez de cortar
    v1 = next(v for v in static["deputados"] if v["id"] == "cvd:1")
    assert v1["foto"] == "fotos/1.jpg" and v1["presenca"]["por_mes"]["2025-04"] == {"faltas": 0, "abonadas": 0, "total": 0}
    assert v1["presenca"]["por_ano"]["2025"]["meses"] == 2 and v1["totais"]["votacoes_registradas"] == 2
    assert static["stats"]["votacoes"]["total"] == 2 and static["stats"]["presenca"]["ultimo_mes"] == "2025-04"
    assert per_vot["u1:0"]["votos"]["cvd:5"] == "presidindo" and per_vot["u1:0"]["por_partido"]["PSD"]["sim"] == 1
    zico = per_ver["cvd:3"]
    assert [v["votacao_id"] for v in zico["votos"]] == ["u2:0", "u1:0"]
    assert zico["proposicoes"][0]["id"] == "REQINF-9/2026" and zico["proposicoes"][1] == {"id": "PL-1/2025", "tipo": "PL", "numero": "1", "ano": 2025, "ementa": "E", "data": "2025-02-01"}
    assert esf.fs_id("cvd:390") == "cvd-390" and esf.fs_id("u1:0") == "u1-0"
    # files on disk
    (tmp_path / "snap.json").write_text(json.dumps(snap))
    esf.main(["--snapshot", str(tmp_path / "snap.json"), "--out", str(tmp_path / "lib"), "--no-fotos"])
    assert (tmp_path / "lib" / "static-data.generated.json").exists()
    assert (tmp_path / "lib" / "static-votacoes" / "u1-0.generated.json").exists()
    assert json.loads((tmp_path / "lib" / "static-deputados" / "cvd-3.generated.json").read_text())["id"] == "cvd:3"


def test_name_resolver_and_authors():
    r = NameResolver(DEPUTADOS)
    assert r.resolve("Deputada ALANA PASSOS") == ["cvd:1"] and r.resolve("Gilberto") == ["cvd:5"]
    assert r.resolve("Zico Poubel") == ["cvd:3", "cvd:4"]           # missing comma between two names
    assert r.resolve("Fulano de Tal") == [] and r.unmatched == {"Fulano de Tal": 1}
    assert split_authors("DEPUTADO ZICO, DEPUTADA ALANA PASSOS E DEPUTADO POUBEL E OUTROS") == ["ZICO", "ALANA PASSOS", "POUBEL"]
    assert split_authors("COMISSÃO DE TRABALHO, EMPREGO E RENDA") == ["COMISSÃO DE TRABALHO, EMPREGO E RENDA"]
    assert split_authors("DEPUTADOS ZICO E POUBEL E DAS COMISSÕES DE JUSTIÇA E REDAÇÃO, DE EDUCAÇÃO E DO DEPUTADO DR. GILBERTO") == \
        ["ZICO", "POUBEL", "COMISSÕES DE JUSTIÇA E REDAÇÃO, DE EDUCAÇÃO", "DR. GILBERTO"]


def test_obstrucao_counts_in_office_not_as_vote():
    deps = [dict(v, legislaturas=[12]) for v in DEPUTADOS]
    vts = enrich_votacoes([{"id": "o:1", "data": "2025-05-01", "contagem": {"sim": 2, "nao": 0, "abstencao": 0, "presentes_votando": 2},
                            "votos": {"cvd:1": "sim", "cvd:3": "sim", "cvd:4": "obstrucao", "cvd:2": "obstrucao"}}], deps, LEGS)
    assert vts[0]["por_partido"] == {"PL": {"sim": 2, "obstrucao": 1}, "PSD": {"obstrucao": 1}}
    agg = deputado_aggregates(deps, vts, [], [], LEGS)
    assert agg["cvd:4"]["votos"]["total"]["obstrucao"] == 1 and agg["cvd:4"]["participacao"] == 0.0
    assert agg["cvd:4"]["contra_partido_base"] == 0          # obstruction is not a sim/não against the party
