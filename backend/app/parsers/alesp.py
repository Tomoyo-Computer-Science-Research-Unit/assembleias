"""Parsers for the Assembleia Legislativa do Estado de São Paulo (ALESP).

Sources (details and counts in FINDINGS.md, section "ALESP"):
  /alesp/votacoes-no-plenario?anoSessao=<ano>   HTML list of the plenary votes taken on the electronic
                                                panel, one item per vote with the link to its PDF report
  repositorio/ementario/votacoes/<...>.pdf      "Relatório de Verificação de Votação": every seat with
                                                party and vote, the printed totals and the result
  legis-api-portal-prd: parlamentares, detalhes, lista-presenca-parlamentar (JSON)
  repositorioDados/processo_legislativo: proposituras.xml, documento_autor.xml, naturezasSpl.xml
"""
from __future__ import annotations

import html as htmllib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# --- vote list (HTML) ------------------------------------------------------------------------------


@dataclass
class VotacaoRef:
    data: str                    # ISO date
    sessao_id: str | None        # /alesp/sessao-plenaria/?id=<n>
    sessao_nome: str             # "29ª Sessão Extraordinária"
    pdf_url: str
    titulo: str                  # what the panel was voting, as listed ("PL 407/26 SALVO SUBEMENDAS E EMENDAS")
    propositura_id: str | None   # IdDocumento of the bill, when the list links it
    ementa: str | None


_ITEM = re.compile(r'<li class="list-group-item[^"]*">(.*?)</li>', re.S)


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_votacoes_index(page: str, base: str = "https://www.al.sp.gov.br") -> list[VotacaoRef]:
    out: list[VotacaoRef] = []
    for m in _ITEM.finditer(page):
        body = m.group(1)
        d = re.search(r"(\d{2})/(\d{2})/(\d{4})\s*-", body)
        pdf = re.search(r'Resultado:\s*<a href="([^"]+)"[^>]*>(.*?)</a>', body, re.S)
        if not d or not pdf:
            continue
        sess = re.search(r'sessao-plenaria/\?id=(\d+)"[^>]*>(.*?)</a>', body, re.S)
        em = re.search(r'Ementa:\s*<a href="/propositura\?id=(\d+)"[^>]*>(.*?)</a>', body, re.S)
        url = pdf.group(1)
        if url.startswith("/"):
            url = base + url
        out.append(VotacaoRef(
            data=f"{d.group(3)}-{d.group(2)}-{d.group(1)}",
            sessao_id=sess.group(1) if sess else None,
            sessao_nome=_text(sess.group(2)) if sess else "",
            pdf_url=url.replace("http://", "https://"),
            titulo=_text(pdf.group(2)),
            propositura_id=em.group(1) if em else None,
            ementa=_text(em.group(2)) if em else None,
        ))
    return out


# --- vote report (PDF) ------------------------------------------------------------------------------

VOTO_MAP = {"sim": "sim", "não": "nao", "nao": "nao", "abstenção": "abstencao", "abstencao": "abstencao",
            "obstrução": "obstrucao", "obstrucao": "obstrucao", "licenciado": "licenciado", "licenciada": "licenciado",
            "---": "sem_voto", "em branco": "branco", "branco": "branco"}


@dataclass
class LinhaVoto:
    nome: str
    partido: str
    voto: str            # sim | nao | abstencao | obstrucao | licenciado | sem_voto | branco | "?<raw>"
    marca: str           # "" | "L" (líder) | "P" (presidente) | "G" (líder do governo) | other letter


@dataclass
class RelatorioVotacao:
    titulo: str
    sessao: str                       # "29ª Sessão Extraordinária"
    data: str | None
    hora: str | None
    pedido: str                       # "VERIFICAÇÃO REQ. P/ DEP. X" or what the report prints there
    linhas: list[LinhaVoto] = field(default_factory=list)
    impresso: dict[str, int] = field(default_factory=dict)   # sim, nao, abstencao, branco, presidente, total
    resultado_raw: str | None = None
    partidos_obstrucao: list[str] = field(default_factory=list)


def _join(chars: list[dict]) -> str:
    chars = sorted(chars, key=lambda c: c["x0"])
    out = ""
    last = None
    for c in chars:
        if last is not None and c["x0"] - last > 1.2 and not out.endswith(" ") and c["text"] != " ":
            out += " "
        out += c["text"]
        last = c["x1"]
    return re.sub(r"\s+", " ", out).strip()


_VOTO_TAIL = re.compile(r"^(.*?)\s*(Sim|Não|Nao|Abstenção|Obstrução|Licenciad[oa]|---|Em Branco|Branco)$", re.I)


def _norm_voto(raw: str) -> str:
    key = raw.strip().lower()
    return VOTO_MAP.get(key, f"?{raw.strip()}" if key else "?")


def parse_vote_pdf(path: str | Path) -> RelatorioVotacao:
    """Read one "Relatório de Verificação de Votação".

    The report has two columns of seats (marker, name, party, vote). Long party names (federations)
    overflow into the vote column, so words overlap; the vote is printed 0.75 pt lower than the rest of
    its row, which is how its characters are told apart from the party's.
    """
    import pdfplumber

    rel = RelatorioVotacao(titulo="", sessao="", data=None, hora=None, pedido="")
    cols: list[dict] | None = None
    with pdfplumber.open(str(path)) as pdf:
        for pno, page in enumerate(pdf.pages):
            words = page.extract_words()
            heads = [w for w in words if w["text"] in ("Parlamentar", "Partido", "Voto")]
            header_top = None
            if len([w for w in heads if w["text"] == "Parlamentar"]) >= 2:
                header_top = min(w["top"] for w in heads if w["text"] == "Parlamentar")
                row = sorted([w for w in heads if abs(w["top"] - header_top) < 2], key=lambda w: w["x0"])
                if len(row) >= 6:
                    cols = [{"parl": row[0]["x0"], "partido": row[1]["x0"], "voto": row[2]["x0"]},
                            {"parl": row[3]["x0"], "partido": row[4]["x0"], "voto": row[5]["x0"]}]
            if pno == 0:
                lines: dict[int, list[dict]] = {}
                for w in words:
                    if header_top is not None and w["top"] >= header_top - 1:
                        continue
                    lines.setdefault(round(w["top"]), []).append(w)
                ordered = [" ".join(x["text"] for x in sorted(ws, key=lambda w: w["x0"])) for _, ws in sorted(lines.items())]
                ordered = [x for x in ordered if not re.match(r"Assembl[ée]ia Legislativa|Relat[óo]rio de Verifica", x)]
                for x in ordered:
                    m = re.search(r"(\d+)\s*ª\s*(Sess[ãa]o\s+\S+)\s+de\s+(\d{2})/(\d{2})/(\d{4})(?:\s+às\s+(\d{2}:\d{2}))?", x)
                    if m and not rel.data:
                        rel.sessao = f"{m.group(1)}ª {m.group(2)}"
                        rel.data = f"{m.group(5)}-{m.group(4)}-{m.group(3)}"
                        rel.hora = m.group(6)
                    elif not rel.data:
                        rel.titulo = f"{rel.titulo} {x}".strip()
                    else:
                        rel.pedido = f"{rel.pedido} {x}".strip()
            if cols is None:
                continue
            foot = [w for w in words if re.match(r"Votos$", w["text"]) and w["x0"] < cols[0]["partido"]]
            foot_top = min((w["top"] for w in foot), default=page.height)
            body_top = (header_top + 6) if header_top is not None else 0
            split = cols[1]["parl"] - 14
            chars = [c for c in page.chars if body_top < c["top"] < foot_top - 1 and c["text"].strip()]
            for ci, col in enumerate(cols):
                cc = [c for c in chars if (c["x0"] < split) == (ci == 0)]
                name_tops = sorted({round(c["top"], 1) for c in cc if col["parl"] + 6 <= c["x0"] < col["partido"] - 2})
                rows: list[float] = []
                for t in name_tops:
                    if not rows or t - rows[-1] > 0.6:
                        rows.append(t)
                buckets: dict[float, dict[str, list[dict]]] = {r: {"marca": [], "nome": [], "partido": [], "voto": []} for r in rows}
                for c in cc:
                    near = [r for r in rows if -0.5 <= c["top"] - r <= 2.0]
                    if not near:
                        continue
                    r = min(near, key=lambda r: abs(c["top"] - r))
                    d = c["top"] - r
                    if d > 0.4 and c["x0"] >= col["partido"] - 2:
                        buckets[r]["voto"].append(c)
                    elif c["x0"] < col["partido"] - 2:
                        buckets[r]["nome"].append(c)
                    else:
                        buckets[r]["partido"].append(c)
                for r in rows:
                    b = buckets[r]
                    # A marker (L líder, P presidente, G governo) is a lone capital before the name, set apart by a space.
                    nm = sorted(b["nome"], key=lambda c: c["x0"])
                    if len(nm) > 1 and nm[0]["text"] in ("L", "P", "G") and nm[1]["x0"] - nm[0]["x1"] > 1.5:
                        b["marca"], b["nome"] = [nm[0]], nm[1:]
                    nome = _join(b["nome"])
                    if not nome:
                        continue
                    partido, voto = _join(b["partido"]), _norm_voto(_join(b["voto"]))
                    if voto.startswith("?"):
                        # Some reports print the party at the vote's height too: split the joined text instead.
                        m = _VOTO_TAIL.match(_join(b["partido"] + b["voto"]))
                        if m:
                            partido, voto = m.group(1), _norm_voto(m.group(2))
                    rel.linhas.append(LinhaVoto(nome=nome, partido=partido.lstrip(".").strip(), voto=voto, marca=_join(b["marca"])))
            # footer: printed totals, result, parties in obstruction
            fw = [w for w in words if w["top"] >= foot_top - 1]
            flines: list[list[dict]] = []
            for w in sorted((w for w in fw if w["x0"] < cols[0]["partido"] - 10), key=lambda w: w["top"]):
                if flines and w["top"] - flines[-1][0]["top"] < 1.5:
                    flines[-1].append(w)
                else:
                    flines.append([w])
            for ws in flines:
                t = " ".join(x["text"] for x in sorted(ws, key=lambda w: w["x0"]))
                m = re.match(r"(Votos Sim|Votos Não|Abstenção|Em Branco|Presidente|Total)\s+(\d+)", t)
                if m:
                    key = {"Votos Sim": "sim", "Votos Não": "nao", "Abstenção": "abstencao", "Em Branco": "branco",
                           "Presidente": "presidente", "Total": "total"}[m.group(1)]
                    rel.impresso[key] = int(m.group(2))
            mid = [w for w in fw if cols[0]["partido"] - 10 <= w["x0"] < cols[0]["voto"] + 35]
            if mid:
                rel.resultado_raw = " ".join(w["text"] for w in sorted(mid, key=lambda w: (round(w["top"]), w["x0"])))
            right = sorted([w for w in fw if w["x0"] >= cols[0]["voto"] + 35], key=lambda w: (round(w["top"]), w["x0"]))
            txt = " ".join(w["text"] for w in right)
            m = re.search(r"PARTIDOS EM OBSTRU[ÇC][ÃA]O\s*(.*)", txt)
            if m:
                rel.partidos_obstrucao = [p.strip() for p in m.group(1).split(",") if p.strip()]
    return rel


# --- resultado, objeto, proposição -------------------------------------------------------------------

def resultado_of(raw: str | None) -> str | None:
    s = (raw or "").lower()
    if not s:
        return None
    if "aprovad" in s:
        return "aprovado"
    if "rejeitad" in s:
        return "rejeitado"
    if "prejudicad" in s:
        return "prejudicado"
    if "sem qu" in s or "falta de qu" in s or "não há qu" in s or "nao ha qu" in s:
        return "sem_quorum"
    if "mantid" in s:
        return "mantido"
    if "derrubad" in s:
        return "derrubado"
    return None


def objeto_of(titulo: str) -> str:
    t = titulo.upper()
    if re.search(r"\bVETO\b", t):
        return "veto"
    if re.match(r"\s*(REQ|REQUERIMENTO)\b", t):
        return "requerimento"
    if "REDAÇÃO FINAL" in t or "REDACAO FINAL" in t:
        return "redacao_final"
    if re.search(r"\bSUBSTITUTIVO\b", t):
        return "substitutivo"
    if re.search(r"\bSUBEMENDA|\bEMENDA", t) and not re.search(r"SALVO\s+(SUB)?EMENDA", t) and not re.match(r"\s*PEC\b", t):
        return "emenda"
    if re.search(r"\bPARECER\b", t):
        return "parecer"
    return "projeto"


_TIPOS = {"PL": "PL", "PLC": "PLC", "PDL": "PDL", "PR": "PR", "PEC": "PEC", "PLP": "PLC"}


def proposicao_of(titulo: str) -> tuple[str, int, int] | None:
    """("PL", 407, 2026) from "PL 407/26 SALVO EMENDAS"; years with two digits are 20xx (or 19xx above 50)."""
    m = re.search(r"\b(PLC|PDL|PEC|PLP|PL|PR)\.?\s*(?:N[º°o]\.?\s*)?(\d{1,4})\s*/\s*(\d{2,4})\b", titulo.upper())
    if not m:
        return None
    ano = int(m.group(3))
    if ano < 100:
        ano += 1900 if ano > 50 else 2000
    return _TIPOS[m.group(1)], int(m.group(2)), ano


# --- names ---------------------------------------------------------------------------------------------

def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def title_name(nome: str) -> str:
    small = {"de", "da", "do", "das", "dos", "e"}
    words = []
    for i, w in enumerate(nome.lower().split()):
        if w in small and i:
            words.append(w)
        elif re.fullmatch(r"[a-z]\.", w) or w in ("jr.", "jr"):
            words.append(w.capitalize())
        else:
            words.append(w[:1].upper() + w[1:])
    return " ".join(words)


# --- presence ------------------------------------------------------------------------------------------

def presenca_status(situacao: str) -> str:
    """Map the portal's text to: presente | falta | extraordinaria | justificada | licenca | nao_deliberativa | outro."""
    s = norm_name(situacao)
    if s == "PRESENTE":
        return "presente"
    if s.startswith("SESSAO NAO DELIBERATIVA"):
        return "nao_deliberativa"
    if s.startswith("NAO JUSTIFICADA"):
        return "falta"
    if s.startswith("AUSENCIA EM SESSAO EXTRAORDINARIA"):
        return "extraordinaria"
    if s.startswith("JUSTIFICADA"):
        return "justificada"
    if "LICEN" in s or "AFASTAD" in s:
        return "licenca"
    return "outro"


def party_on(filiacoes: list[dict], day: str) -> str | None:
    """Party in force on ``day`` from the API's listaFiliacoes."""
    best = None
    for f in filiacoes or []:
        ini, fim = (f.get("dtInicio") or "")[:10], (f.get("dtFim") or "9999-12-31")[:10]
        if ini <= day <= fim:
            if best is None or ini > best[0]:
                best = (ini, (f.get("partido") or {}).get("txSigla"))
    return best[1] if best else None
