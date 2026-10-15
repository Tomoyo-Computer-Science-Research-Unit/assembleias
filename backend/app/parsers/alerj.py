"""Parsers for the Assembleia Legislativa do Estado do Rio de Janeiro (ALERJ) sites.

  www.alerj.rj.gov.br/Deputados/QuemSao           roster per legislature (POST), with the site's numeric id
  www.alerj.rj.gov.br/Deputados/PerfilDeputado/N  profile: name, e-mail, party history with dates
  alerjln1 ordemdia.nsf (view presint)            monthly table of absences per deputy
  alerjln1 scpro1923.nsf / scpro2327.nsf          bills (Lotus Domino full-text search results)
The Diário Oficial (votes) is in alerj_do.py.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import unicodedata
from dataclasses import dataclass, field

MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
         "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


# --- roster ------------------------------------------------------------------------------------------

@dataclass
class Card:
    id: int
    nome: str            # as the card prints it (upper case)
    partido: str | None
    foto: str | None     # absolute URL


def parse_quemsao(page: str, base: str = "https://www.alerj.rj.gov.br") -> list[Card]:
    """One card per deputy; the photo and the party sit just before the name link."""
    out: list[Card] = []
    seen: set[int] = set()
    for m in re.finditer(r'<div class="nome">\s*<a href="/Deputados/PerfilDeputado/(\d+)[^"]*">(.*?)</a>', page, re.S):
        i = int(m.group(1))
        if i in seen:
            continue
        seen.add(i)
        before = page[max(0, m.start() - 1200):m.start()]
        before = before[before.rfind(f"PerfilDeputado/{i}") - 200:] if f"PerfilDeputado/{i}" in before else before
        p = re.findall(r'<div class="partido">(.*?)</div>', before, re.S)
        img = re.findall(r'<img src="([^"]+)"', before)
        foto = img[-1] if img else None
        out.append(Card(id=i, nome=clean(m.group(2)), partido=(clean(p[-1]) or None) if p else None,
                        foto=(base + foto) if foto and foto.startswith("/") else foto))
    return out


@dataclass
class Perfil:
    nome: str | None
    email: str | None
    telefone: str | None
    foto: str | None
    partidos: list[tuple[str, str]] = field(default_factory=list)   # (ISO date, party) events, oldest first


def parse_perfil(page: str, base: str = "https://www.alerj.rj.gov.br") -> Perfil:
    nome = None
    m = re.search(r'<span>DEPUTAD[OA]</span>.*?<h1>(.*?)</h1>', page, re.S)
    if m:
        nome = clean(m.group(1))
    em = re.search(r"[\w.+-]+@alerj\.rj\.gov\.br", page)
    tel = re.search(r"<h2[^>]*>CONTATO</h2>(.*?)</div>", page, re.S)
    telefone = None
    if tel:
        t = re.search(r"\(\d{2}\)\s*[\d\s-]{8,}", clean(tel.group(1)))
        telefone = t.group(0).strip() if t else None
    foto = re.search(r'<img src="(/Uploads/PerfilDeputado/Imagem/[^"]+)"', page)
    ev: list[tuple[str, str]] = []
    for m in re.finditer(r"(Posse na ALERJ:\s*([^-<]+?)\s*-\s*Data\s*(\d{2})/(\d{2})/(\d{4})|"
                         r"Troca de partido:\s*Ingresso no\s+([^-<]+?)\s*-\s*Data\s*(\d{2})/(\d{2})/(\d{4}))", page):
        if m.group(2):
            ev.append((f"{m.group(5)}-{m.group(4)}-{m.group(3)}", htmllib.unescape(m.group(2)).strip()))
        else:
            ev.append((f"{m.group(9)}-{m.group(8)}-{m.group(7)}", htmllib.unescape(m.group(6)).strip()))
    ev.sort(key=lambda e: e[0])          # stable: same-day events keep the page's order
    return Perfil(nome=nome, email=em.group(0) if em else None, telefone=telefone,
                  foto=(base + foto.group(1)) if foto else None, partidos=ev)


def party_on(events: list[tuple[str, str]], day: str) -> str | None:
    """Party in force on ``day``; "S/PARTIDO" reads as no party."""
    p = None
    for d, party in events:
        if d <= day:
            p = party
    if p and re.sub(r"\W", "", p.upper()) in ("SPARTIDO", "SEMPARTIDO"):
        return "Sem partido"
    return p


# --- Domino helpers -------------------------------------------------------------------------------------

def domino_json(text: str) -> dict:
    """Domino's JSON has invalid escapes such as "=\\>"; drop the stray backslash before parsing."""
    return json.loads(re.sub(r'\\(?!["\\/bfnrtu])', "", text), strict=False)


def view_rows(d: dict) -> list[dict]:
    out = []
    for e in d.get("viewentry", []):
        vals = {}
        for x in e.get("entrydata", []):
            for kind in ("text", "number", "datetime", "textlist"):
                if kind in x:
                    v = x[kind]
                    if isinstance(v, dict):
                        v = v.get("0")
                    vals[x.get("@name")] = v
        out.append({"position": e.get("@position"), "unid": e.get("@unid"), "values": vals})
    return out


# --- monthly presence (ordemdia.nsf) ------------------------------------------------------------------

@dataclass
class PresencaMes:
    mes_nome: str
    data_publicacao: str | None
    linhas: list[dict]                   # {"nome", "faltas", "dias": [int]}
    sessoes_ordinarias: int | None
    sessoes_extraordinarias: int | None
    sessoes_total: int | None


def parse_presenca(page: str) -> PresencaMes:
    mes = re.search(r"M[êe]s de\s*:\s*(?:</font>\s*</b>\s*<b>\s*<font[^>]*>)?\s*([A-Za-zçÇ]+)", page)
    mes_nome = mes.group(1) if mes else ""
    if not mes_nome:
        t = clean(page)
        m2 = re.search(r"M[êe]s de\s*:\s*([A-Za-zçÇ]+)", t)
        mes_nome = m2.group(1) if m2 else ""
    data = None
    dm = re.search(r"Data:\s*(?:</font></b><b><font[^>]*>)?\s*(\d{2})/(\d{2})/(\d{4})", page)
    if dm:      # Domino prints dates month first
        data = f"{dm.group(3)}-{dm.group(1)}-{dm.group(2)}"
    linhas: list[dict] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        tds = [clean(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)]
        if len(tds) < 3:
            continue
        for k in range(0, len(tds) - 2, 3):
            nome, faltas, dias = tds[k], tds[k + 1], tds[k + 2]
            if not nome or nome.upper() in ("DEPUTADO", "DEPUTADA") or not re.search(r"[A-ZÁ-Ú]", nome):
                continue
            if faltas and not re.fullmatch(r"\d+", faltas):
                continue
            if not re.fullmatch(r"[\d,\s]*", dias):
                continue
            linhas.append({"nome": nome.strip(), "faltas": int(faltas) if faltas else 0,
                           "dias": [int(x) for x in re.findall(r"\d+", dias)]})
    t = clean(page)

    def num(label: str) -> int | None:
        m = re.search(label + r"\s*-\s*(\d+)?", t)
        return int(m.group(1)) if m and m.group(1) else None
    return PresencaMes(mes_nome=mes_nome, data_publicacao=data, linhas=linhas,
                       sessoes_ordinarias=num(r"SESS[ÕO]ES ORDIN[ÁA]RIAS DELIBERATIVAS"),
                       sessoes_extraordinarias=num(r"SESS[ÕO]ES EXTRAORDIN[ÁA]RIAS DELIBERATIVAS"),
                       sessoes_total=num(r"TOTAL DE SESS[ÕO]ES DELIBERATIVAS"))


# --- bills (scpro full-text search results) ------------------------------------------------------------

# prop_cod_prop = YYYY + TT + NNNNN. TT -> type code used by the site.
TIPO_COD = {"01": "PEC", "02": "PLC", "03": "PL", "04": "PDL", "05": "PR", "07": "IND", "09": "REQINF", "14": "MOC"}


def parse_search_rows(page: str) -> list[dict]:
    """Rows of a SearchView result: code, ementa, publication date and authors."""
    out = []
    for tr in re.findall(r'<tr valign="top">(.*?)</tr>', page, re.S):
        link = re.search(r'<a href="(/[^"]+\?OpenDocument)">\s*(\d{11})\s*</a>', tr)
        if not link:
            continue
        tds = [x for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        texts = [clean(x) for x in tds]
        date = None
        for t in texts:
            m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", t)
            if m:
                date = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
        cod = link.group(2)
        ementa = ""
        for t in texts:
            if "=>" in t and cod in t:
                ementa = t.split("=>")[0].strip()
        if not ementa:
            cands = [t for t in texts if t and t != cod and not re.fullmatch(r"[\d/]+", t)]
            ementa = max(cands[:-1] or cands, key=len) if cands else ""
        autores_raw = texts[-1] if texts else ""
        out.append({"cod": cod, "url": link.group(1), "ementa": ementa, "data": date,
                    "autores": [a.strip() for a in autores_raw.split(",") if a.strip()]})
    return out


def prop_from_code(cod: str) -> tuple[str, int, int] | None:
    """("PL", 6389, 2025) from 20250306389."""
    if not re.fullmatch(r"\d{11}", cod):
        return None
    tipo = TIPO_COD.get(cod[4:6])
    return (tipo, int(cod[6:]), int(cod[:4])) if tipo else None
