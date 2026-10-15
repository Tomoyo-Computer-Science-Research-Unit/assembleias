"""ALERJ: roster cards, profile party history, monthly presence, bill search rows and the Diário Oficial record."""
from pathlib import Path

from app.etl.snapshot_alerj import objeto_of, resultado_of, roster_for_date
from app.parsers.alerj import (domino_json, parse_perfil, parse_presenca, parse_quemsao, parse_search_rows, party_on,
                               prop_from_code, view_rows)
from app.parsers.alerj_do import calendar_dates, edition_url, parse_records, parte_ii_guids, pdf_url, split_names

FIX = Path(__file__).parent / "fixtures"


def test_roster_cards():
    cards = parse_quemsao((FIX / "alerj_quemsao_19_excerpt.html").read_text())
    assert [c.id for c in cards][:2] == [467, 418]
    assert cards[0].nome == "ADRIANA BALTHAZAR" and cards[0].partido == "PSD"
    assert cards[0].foto.startswith("https://www.alerj.rj.gov.br/Uploads/PerfilDeputado/Imagem/")


def test_profile_party_history():
    p = parse_perfil((FIX / "alerj_perfil_269_excerpt.html").read_text())
    assert p.nome == "Luiz Paulo" and p.email == "luizpaulo@alerj.rj.gov.br"
    assert ("2020-12-16", "Cidadania") in p.partidos and ("2023-02-01", "PSD") in p.partidos
    assert party_on(p.partidos, "2020-11-01") == "Sem partido"
    assert party_on(p.partidos, "2021-06-01") == "Cidadania" and party_on(p.partidos, "2023-01-31") == "PSD"


def test_monthly_presence():
    t = parse_presenca((FIX / "alerj_presenca_2019_11.html").read_text(encoding="latin-1"))
    assert t.mes_nome == "Novembro" and t.data_publicacao == "2019-12-03"      # Domino prints month first
    assert len(t.linhas) == 70 and t.sessoes_total == 10 and t.sessoes_ordinarias == 10
    by = {l["nome"]: l for l in t.linhas}
    assert by["BAGUEIRA"] == {"nome": "BAGUEIRA", "faltas": 2, "dias": [7, 26]}
    assert by["LUCINHA"]["faltas"] == 1 and by["ALANA PASSOS"]["faltas"] == 0


def test_bill_search_rows():
    rows = parse_search_rows((FIX / "alerj_scpro_busca_excerpt.html").read_text())
    assert rows[0]["cod"] == "20250306389" and rows[0]["data"] == "2025-09-25" and rows[0]["autores"] == ["ANDRE CORREA"]
    assert rows[0]["ementa"].startswith("DECLARA O MUNICÍPIO DE PORCIÚNCULA") and "=>" not in rows[0]["ementa"]
    assert rows[-1]["autores"] == ["VINICIUS COZZOLINO", "Chico Machado", "Yuri Moura"]
    assert prop_from_code("20250306389") == ("PL", 6389, 2025) and prop_from_code("20240700012") == ("IND", 12, 2024)


def test_domino_json_repair():
    d = domino_json('{"viewentry":[{"@position":"1","@unid":"AB","entrydata":[{"@name":"$10","text":{"0":"a =\\> b"}}]}]}')
    assert view_rows(d)[0]["values"]["$10"] == "a => b"


def test_diario_oficial_links():
    page = '<a href="do_seleciona_edicao.php?data=MjAyNDA2MTI=">12</a>'
    assert calendar_dates(page) == ["2024-06-12"]
    assert edition_url("2021-06-10").endswith("data=MjAyMTA2MTA=")
    token = "VFhwV1JGRlZXa05OVkZG"           # not a full token: ignored
    assert parte_ii_guids(f'<a href="mostra_edicao.php?session={token}">Parte II (Poder Legislativo)</a>') == []
    assert pdf_url("C7B10FC9-101A-4DBE-8D80-19A9C2DB0C1E").endswith("k=C7B10FC9-101PA-4DBE-8D80-19A9C2DB0C1E")


def test_session_record_and_vote():
    atas = parse_records((FIX / "alerj_do_20250924_excerpt.txt").read_text())
    assert len(atas) == 1
    a = atas[0]
    assert (a.numero, a.tipo, a.data) == (77, "Ordinária", "2025-09-23")
    assert a.presentes_impresso == 69 and "Alan Lopes" in a.presentes and "Zeidan" in a.presentes
    assert len(a.votos) == 1
    v = a.votos[0]
    assert len(v.sim) == 21 and v.sim[0] == "Átila Nunes" and "Yuri Moura" in v.sim
    assert len(v.nao) == 40 and "Dr. Pedro Ricardo" in v.nao       # the record prints 40 names for 39 votes
    assert v.impresso == {"sim": 21, "nao": 39}
    assert v.resultado_frase == "Está rejeitada o Destaque da Emenda número 301."
    assert v.proposicao == ("PL", 6027, 2025) and v.presidente == "RODRIGO BACELLAR"
    assert objeto_of(v.materia, v.resultado_frase) == "emenda" and resultado_of(v.resultado_frase, "emenda") == "rejeitado"


def test_names_and_results():
    assert split_names("Alan Lopes, Dr. Deodalto; Tia Ju e Val Ceasa.") == ["Alan Lopes", "Dr. Deodalto", "Tia Ju", "Val Ceasa"]
    assert resultado_of("Os Vetos estão rejeitados e retornam ao governo.", "veto") == "derrubado"
    assert resultado_of("Os vetos estão mantidos.", "veto") == "mantido"
    assert objeto_of("Anuncia-se a Discussão Única: VETO TOTAL APOSTO AO PROJETO DE LEI 3246/2020", None) == "veto"
    ex = {(2026, 6): {"a"}, (2026, 7): {"b"}}
    assert roster_for_date("2026-08-12", ex) == ({"b"}, "2026-07") and roster_for_date("2026-05-01", ex) == (set(), None)
