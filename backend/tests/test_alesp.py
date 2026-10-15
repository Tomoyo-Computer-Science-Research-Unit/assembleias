"""ALESP: vote list, the panel's PDF report (overlapping columns), names on the panel, presence marks."""
from pathlib import Path

from app.etl.snapshot_alesp import PanelNames, monthly_presence
from app.parsers.alesp import (objeto_of, parse_vote_pdf, parse_votacoes_index, party_on, presenca_status, proposicao_of,
                               resultado_of)

FIX = Path(__file__).parent / "fixtures"


def test_vote_list_items():
    refs = parse_votacoes_index((FIX / "alesp_votacoes_2020_excerpt.html").read_text(encoding="latin-1"))
    assert len(refs) == 2
    r = refs[0]
    assert r.data == "2020-12-17" and r.sessao_id == "14430" and r.sessao_nome == "65ª Sessão Extraordinária"
    assert r.pdf_url.endswith("20201217-020902-ID_SESSAO=14430-PDF.pdf") and r.titulo == "REDAÇÃO FINAL AO PL 627/20"
    assert r.propositura_id == "1000337240" and r.ementa.startswith("Orça a Receita")


def test_pdf_with_federation_overflow():
    rel = parse_vote_pdf(FIX / "alesp_verificacao_pec3_2023.pdf")
    assert rel.titulo == "PEC 03/23 2º TURNO" and rel.sessao == "62ª Sessão Extraordinária"
    assert rel.data == "2023-12-13" and rel.hora == "17:19" and rel.pedido == "VERIFICAÇÃO REQ. P/ DEP. PAULO FIORILO"
    assert len(rel.linhas) == 94
    by = {l.nome: l for l in rel.linhas}
    # "FED PT/PC DO B" runs into the vote column; the vote is printed 0.75 pt lower and must not mix in
    assert by["DONATO"].partido == "FED PT/PC DO B" and by["DONATO"].voto == "sim"
    assert by["EMIDIO DE SOUZA"].voto == "obstrucao"
    assert by["VINICIUS CAMARINHA"].partido == "FED PSDB/CIDADANIA" and by["VINICIUS CAMARINHA"].marca == "L"
    assert by["ANDRÉ DO PRADO"].marca == "P" and by["ANDRÉ DO PRADO"].voto == "sem_voto"
    assert by["MARIA LÚCIA AMARY"].voto == "licenciado"
    assert rel.impresso == {"sim": 70, "nao": 0, "abstencao": 0, "branco": 0, "presidente": 1, "total": 71}
    assert sum(1 for l in rel.linhas if l.voto == "sim") == 70
    assert rel.resultado_raw == "Aprovado" and resultado_of(rel.resultado_raw) == "aprovado"
    assert rel.partidos_obstrucao[:2] == ["FED PSDB/CIDADANIA", "FED PT/PC DO B"]


def test_pdf_without_result_line():
    rel = parse_vote_pdf(FIX / "alesp_verificacao_plc33_2020_veto.pdf")
    assert rel.titulo == "PLC 33/20 VETO" and rel.data == "2021-12-16"
    assert rel.resultado_raw is None and rel.impresso["total"] == 20      # below the quorum of 48
    assert sum(1 for l in rel.linhas if l.voto == "obstrucao") == 50
    assert objeto_of(rel.titulo) == "veto" and proposicao_of(rel.titulo) == ("PLC", 33, 2020)


def test_titles():
    assert objeto_of("REQ. MÉTODO DE VOTAÇÃO PL 407/26") == "requerimento"
    assert objeto_of("PL 407/26 SALVO SUBEMENDAS E EMENDAS") == "projeto"
    assert objeto_of("SUBSTITUTIVO AO PLC 45/19") == "substitutivo"
    assert objeto_of("REDAÇÃO FINAL AO PL 627/20") == "redacao_final"
    assert objeto_of("EMENDA Nº 3 AO PL 10/21") == "emenda"
    assert proposicao_of("REDAÇÃO FINAL AO PL 627/20") == ("PL", 627, 2020)
    assert proposicao_of("PLC 78/2019 SALVO EMENDAS") == ("PLC", 78, 2019)


def test_panel_names():
    deps = {"alesp:1": {"nomes": ["PAULA DA BANCADA FEMINISTA"], "legs": {20}},
            "alesp:2": {"nomes": ["BETH SAHÃO"], "legs": {19, 20}},
            "alesp:3": {"nomes": ["LUIZ CLAUDIO MARCOLINO"], "legs": {19, 20}},
            "alesp:4": {"nomes": ["LUIZ FERNANDO TEIXEIRA FERREIRA"], "legs": {19, 20}},
            "alesp:5": {"nomes": ["CARLA MORANDO"], "legs": {19, 20}}}
    n = PanelNames(deps)
    assert n.match("BETH LULA SAHÃO", 19) == "alesp:2"            # 2019: "Lula" inside PT names
    assert n.match("LUIZ C. MARCOLINO", 20) == "alesp:3"           # initials
    assert n.match("LUIZ FERNANDO", 20) == "alesp:4"
    assert n.match("CARLA S. MORANDO", 20) == "alesp:5"
    assert n.match("FULANO", 20) is None and n.unmatched["FULANO (20)"] == 1


def test_presence_marks_and_months():
    assert presenca_status("Presente") == "presente"
    assert presenca_status("Sessão não Deliberativa - com quórum regimental para abertura da sessão") == "nao_deliberativa"
    assert presenca_status("Não Justificada") == "falta" and presenca_status("Justificada") == "justificada"
    assert presenca_status("Ausência em Sessão Extraordinária") == "extraordinaria"
    linhas = [{"matricula": 7, "sessao_id": i, "data": f"2025-06-{i:02d}", "situacao": s} for i, s in
              enumerate(["Presente", "Não Justificada", "Justificada", "Ausência em Sessão Extraordinária",
                         "Sessão não Deliberativa - com quórum regimental para abertura da sessão"], start=1)]
    row = monthly_presence(linhas, {"alesp:7": "Fulana"})[0]
    assert row["deputado_id"] == "alesp:7" and row["sessoes"] == 4 and row["presencas"] == 1
    assert row["faltas"] == 2 and row["faltas_abonadas"] == 1 and row["total_faltas"] == 3


def test_party_on():
    fil = [{"dtInicio": "2019-03-15", "dtFim": "2021-02-24", "partido": {"txSigla": "PSL"}},
           {"dtInicio": "2022-03-03", "dtFim": None, "partido": {"txSigla": "PL"}}]
    assert party_on(fil, "2020-01-01") == "PSL" and party_on(fil, "2026-01-01") == "PL" and party_on(fil, "2021-06-01") is None
