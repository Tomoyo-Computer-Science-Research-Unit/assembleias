"""Diário Oficial do Estado do Rio de Janeiro, Parte II (Poder Legislativo), on ioerj.com.br.

The ALERJ prints there the full record of each plenary session ("ATA DA 77ª SESSÃO ORDINÁRIA
REALIZADA EM 23 DE SETEMBRO DE 2025"): who was present at the opening, with the count, and every
panel vote with the names of who voted "sim" and "não" and the printed totals. ALERJ's own systems
keep only the totals, so this is the only place with the vote of each deputy.

Reaching a PDF takes two requests:
  do_seleciona_data.php                      every date with an edition (one page, all years)
  do_seleciona_edicao.php?data=<b64 YYYYMMDD> one link per part of that day's edition; the link's
                                              session token is base64 three times over "<GUID><digits>"
  mostra_edicao.php?k=<GUID[:12]>P<GUID[12:]> the PDF of that part
"""
from __future__ import annotations

import base64
import re

IOERJ = "https://www.ioerj.com.br/portal/modules/conteudoonline"
PARTE_II = "Parte II (Poder Legislativo)"


def calendar_dates(page: str) -> list[str]:
    """ISO dates that have an edition, from do_seleciona_data.php."""
    out = set()
    for b in re.findall(r"do_seleciona_edicao\.php\?data=([A-Za-z0-9+/=]+)", page):
        try:
            s = base64.b64decode(b + "=" * (-len(b) % 4)).decode("ascii")
        except Exception:
            continue
        if re.fullmatch(r"\d{8}", s):
            out.add(f"{s[:4]}-{s[4:6]}-{s[6:]}")
    return sorted(out)


def edition_url(day: str) -> str:
    return f"{IOERJ}/do_seleciona_edicao.php?data={base64.b64encode(day.replace('-', '').encode()).decode()}"


def parte_ii_guids(page: str) -> list[str]:
    """GUIDs of the Parte II PDFs of one day (some days have a second, extra Parte II)."""
    out = []
    for m in re.finditer(r"mostra_edicao\.php\?session=([A-Za-z0-9+/=]+)[^>]*>\s*([^<]+)<", page):
        if m.group(2).strip() != PARTE_II:
            continue
        x = m.group(1)
        try:
            for _ in range(3):
                x = base64.b64decode(x + "=" * (-len(x) % 4)).decode("latin-1")
        except Exception:
            continue
        guid = x[:36]
        if re.fullmatch(r"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}", guid, re.I) and guid not in out:
            out.append(guid)
    return out


def pdf_url(guid: str) -> str:
    return f"{IOERJ}/mostra_edicao.php?k={guid[:12]}P{guid[12:]}"


ATA_HEAD = re.compile(r"ATA\s+DA\s+(\d+)\s*[ªa°º]\s+SESS[ÃA]O\s+(ORDIN[ÁA]RIA|EXTRAORDIN[ÁA]RIA|SOLENE|ESPECIAL)", re.I)


def has_plenary_record(text: str) -> bool:
    """Worth keeping: a plenary session record or a named vote list."""
    return bool(ATA_HEAD.search(text) or re.search(r"Votaram\s+[“\"]?\s*sim", text, re.I))


# --- plenary records ---------------------------------------------------------------------------------

from dataclasses import dataclass, field  # noqa: E402

MESES = {"JANEIRO": 1, "FEVEREIRO": 2, "MARCO": 3, "MARÇO": 3, "ABRIL": 4, "MAIO": 5, "JUNHO": 6, "JULHO": 7,
         "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12}

ATA = re.compile(r"ATA\s+DA\s+(\d+)\s*[ªºa°]?\s*SESS[ÃA]O\s+(ORDIN[ÁA]RIA|EXTRAORDIN[ÁA]RIA|SOLENE|ESPECIAL)"
                 r"[^\n]{0,60}?,?\s*\n?\s*REALIZADA\s+EM\s+(\d{1,2})\s*(?:º|°)?\s+DE\s+([A-ZÇÃa-zçã]+)\s+DE\s+(\d{4})", re.I)
_SIDE = {"sim": "sim", "nao": "nao", "não": "nao", "abstencao": "abstencao", "abstenção": "abstencao"}
# A printed list names the deputies after "os Senhores Deputados" or a colon; spoken roll calls
# ("Deputado X. Votou “não” no grupo.") have neither and are not lists.
LISTA = re.compile(
    r"(?:Vot(?:aram|ou)\s*[“\"”]?\s*(sim|n[ãa]o|absten[çc][ãa]o)\s*[”\"“]?\s*,?\s*(?:(?:o|os)?\s*(?:senhor(?:es)?|srs?\.)\s*deputad[oa]s?\s*:?|:)"
    r"|(Abstiveram-se|Absteve-se)\s+(?:o|os)?\s*(?:senhor(?:es)?|srs?\.)\s*deputad[oa]s?\s*:?)\s*", re.I)
# Words that end a list of names: the totals, the next list, the result or a speaker.
_END = re.compile(r"\n\s*(?:Tota(?:l|is)\b|Vot(?:aram|ou)\b|Abstiveram|Absteve|Est[áa]\s|O\s+SR\.|A\s+SRA\.|Proclamo|Anuncia"
                  r"|Em\s+vota|Vamos\s|(?:Os|As|O|A)\s+[a-zà-ú])")
_ABBR = re.compile(r"(?:\b(?:Dr|Dra|Drª|Prof|Profª|Profa|Sr|Sra|Jr|Pr|Cel|Cap|Sgt|Ten|Sub)\.)$", re.I)


@dataclass
class Lista:
    lado: str
    nomes: list[str]
    start: int
    end: int


@dataclass
class VotoDO:
    sim: list[str]
    nao: list[str]
    abstencao: list[str]
    start: int
    end: int
    impresso: dict[str, int] = field(default_factory=dict)
    resultado_frase: str | None = None
    materia: str | None = None
    presidente: str | None = None
    proposicao: tuple[str, int, int] | None = None     # last bill named before the vote
    anuncio: str | None = None                          # the last "Anuncia-se ..." before the vote


@dataclass
class AtaDO:
    numero: int
    tipo: str               # "Ordinária" | "Extraordinária" | "Solene" | "Especial"
    data: str               # ISO
    presentes: list[str]
    presentes_impresso: int | None
    votos: list[VotoDO]
    so_totais: list[str]     # roll calls whose names the record does not print (the proclamation only)


def _unspace(name: str) -> str:
    """Justified lines letter-space some names ("Léo Vi e i r a"): glue runs of single letters back."""
    out: list[str] = []
    for tok in name.split():
        if out and len(tok) == 1 and tok.isalpha() and (len(out[-1]) <= 2 or out[-1][-1].isalpha()) and not (len(out[-1]) > 2 and tok.isupper()):
            out[-1] += tok
        else:
            out.append(tok)
    return " ".join(out)


def split_names(s: str) -> list[str]:
    s = re.sub(r"\s+", " ", s).strip(" .;")
    parts = re.split(r"\s*[,;]\s*|\s+e\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", s)
    return [_unspace(p.strip(" .")) for p in parts if p and p.strip(" .") and len(p.strip(" .")) > 1]


def clean_text(text: str) -> str:
    """Drop the running page header (control characters and "PODER LEGISLATIVO") that pdfium leaves
    inside words split across pages ("Ber- … PODER LEGISLATIVO … nardo")."""
    text = text.replace("\ufffe", "")
    text = re.sub(r"[\x00-\x08\x0b\x0e-\x1f]+", " ", text)
    text = re.sub(r"(\w)-\s+(?:[ÁA]\s+)*PODER LEGISLATIVO\s+(?=\w)", r"\1", text)
    return re.sub(r"[ \t]+(?:[ÁA][ \t]+)*PODER LEGISLATIVO[ \t]+", " ", text)


def _list_end(text: str, start: int) -> int:
    """End of a list of names: a period that is not part of 'Dr.'/'Prof.', or a line that starts something else."""
    limit = min(len(text), start + 3000)
    m = _END.search(text, start, limit)
    stop = m.start() if m else limit
    for p in re.finditer(r"\.", text[start:stop]):
        pos = start + p.start()
        if _ABBR.search(text[max(start, pos - 6):pos + 1]):
            continue
        nxt = text[pos + 1:pos + 3]
        if re.match(r"\s*[a-zà-ú]", nxt):      # "Jr. e" inside a name list
            continue
        return pos
    return stop


def find_lists(text: str) -> list[Lista]:
    out: list[Lista] = []
    for m in LISTA.finditer(text):
        lado = _SIDE.get((m.group(1) or "").lower()) or ("abstencao" if m.group(2) else None)
        if lado is None:
            continue
        end = _list_end(text, m.end())
        body = text[m.end():end]
        if re.search(r"\d", body) or len(body) < 3:
            continue
        nomes = split_names(body)
        if nomes:
            out.append(Lista(lado, nomes, m.start(), end))
    return out


_TOT = [
    re.compile(r"[“\"]\s*(sim|n[ãa]o|absten[çc][ãa]o)\s*[”\"]\s*[:,]?\s*(\d+)", re.I),
    re.compile(r"\bvotos\s+(sim|n[ãa]o|absten[çc][ãa]o)\s*[:,]?\s*(\d+)", re.I),
    re.compile(r"(\d+)\s*[“\"]\s*(sim|n[ãa]o|absten[çc][ãa]o)\s*[”\"]", re.I),
]


def printed_totals(window: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for k, rx in enumerate(_TOT):
        for m in rx.finditer(window):
            a, b = m.group(1), m.group(2)
            lado, n = (_SIDE[fold_side(a)], int(b)) if k < 2 else (_SIDE[fold_side(b)], int(a))
            out.setdefault(lado, n)
    tm = re.search(r"Total(?:\s+de\s+votos)?\s*[:,]?\s*(\d+)", window, re.I)
    if tm:
        out.setdefault("total", int(tm.group(1)))
    return out


def fold_side(s: str) -> str:
    s = s.lower().replace("ã", "a").replace("ç", "c")
    return {"sim": "sim", "nao": "nao", "abstencao": "abstencao"}.get(s, s)


_RES = re.compile(r"(?:est[áa]|foi|ficou|fica|ficam|est[ãa]o|foram)\s+(aprovad[oa]s?|rejeitad[oa]s?|mantid[oa]s?|derrubad[oa]s?|prejudicad[oa]s?)"
                  r"|\b(Aprovad[oa]s?|Rejeitad[oa]s?|Mantid[oa]s?)\b", re.I)


PROP_REF = re.compile(r"(PROJETO\s+DE\s+LEI\s+COMPLEMENTAR|PROJETO\s+DE\s+LEI|PROJETO\s+DE\s+DECRETO\s+LEGISLATIVO|"
                      r"PROJETO\s+DE\s+RESOLU[ÇC][ÃA]O|PROPOSTA\s+DE\s+EMENDA\s+(?:[ÀA]\s+)?CONSTITUI[ÇC][ÃA]O|PLC|PDL|PEC|PL|PR)"
                      r"\s*(?:N[º°o]\.?\s*)?(\d{1,5})(?:\s*-\s*[A-Z])?\s*/\s*(\d{4})", re.I)
_PROP_TIPO = {"PROJETO DE LEI COMPLEMENTAR": "PLC", "PROJETO DE LEI": "PL", "PROJETO DE DECRETO LEGISLATIVO": "PDL",
              "PROJETO DE RESOLUCAO": "PR", "PROPOSTA DE EMENDA CONSTITUICAO": "PEC", "PROPOSTA DE EMENDA A CONSTITUICAO": "PEC"}


def prop_ref(m: re.Match) -> tuple[str, int, int]:
    k = re.sub(r"\s+", " ", fold(m.group(1)).upper())
    tipo = _PROP_TIPO.get(k, k if k in ("PLC", "PDL", "PEC", "PL", "PR") else "PL")
    return tipo, int(m.group(2)), int(m.group(3))


def group_votes(text: str, lists: list[Lista]) -> list[VotoDO]:
    votes: list[VotoDO] = []
    cur: VotoDO | None = None
    for l in lists:
        new = cur is None or l.start - cur.end > 900 or getattr(cur, l.lado)
        if new:
            cur = VotoDO(sim=[], nao=[], abstencao=[], start=l.start, end=l.end)
            votes.append(cur)
        getattr(cur, l.lado).extend(l.nomes)
        cur.end = l.end
    # The same roll call is sometimes printed twice in a row (proclaimed, then with the totals): keep the second.
    kept: list[VotoDO] = []
    for v in votes:
        if kept:
            a = kept[-1]
            sa, sb = set(a.sim) | set(a.nao), set(v.sim) | set(v.nao)
            if v.start - a.end < 2500 and sa and sb and len(sa & sb) / len(sa | sb) > 0.9 \
                    and not _RES.search(text[a.end:v.start]):
                kept[-1] = v
                continue
        kept.append(v)
    votes = kept
    for i, v in enumerate(votes):
        nxt = votes[i + 1].start if i + 1 < len(votes) else len(text)
        after = text[v.end:min(nxt, v.end + 600)]
        before = text[max(0, v.start - 300):v.start]
        v.impresso = printed_totals(after[:400])
        for k, n in printed_totals(before[-200:]).items():
            v.impresso.setdefault(k, n)
        r = _RES.search(after)
        if r:
            line_start = after.rfind("\n", 0, r.start()) + 1
            line_end = after.find("\n", r.end())
            v.resultado_frase = re.sub(r"\s+", " ", after[line_start:line_end if line_end > 0 else None]).strip()
        prev_end = votes[i - 1].end if i else 0
        ctx = text[max(prev_end, v.start - 6000):v.start]
        an = list(re.finditer(r"(Anuncia-se|Anuncio|Em votação|Há sobre a mesa|Vamos (?:à|a) votação)", ctx, re.I))
        if an:
            v.materia = re.sub(r"\s+", " ", ctx[an[-1].start():an[-1].start() + 700]).strip()
        # The bill is the one announced last ("Anuncia-se a discussão ... PROJETO DE LEI Nº ..."),
        # else the last one named before the vote.
        ann = list(re.finditer(r"Anuncia-se|Anuncio", text[:v.start]))
        ref = PROP_REF.search(text, ann[-1].start(), min(v.start, ann[-1].start() + 1500)) if ann else None
        if ann:
            v.anuncio = re.sub(r"\s+", " ", text[ann[-1].start():min(v.start, ann[-1].start() + 900)]).strip()
        if ref is None:
            refs = list(PROP_REF.finditer(text[max(0, v.start - 20000):v.start]))
            ref = refs[-1] if refs else None
        if ref is not None:
            v.proposicao = prop_ref(ref)
        pr = list(re.finditer(r"O SR\. PRESIDENTE \(([^)]+)\)", text[max(0, v.start - 4000):v.start]))
        if pr:
            v.presidente = pr[-1].group(1).strip()
    return votes


def parse_records(text: str) -> list[AtaDO]:
    """Every plenary session record (ata) of one edition, with presence and the votes with names."""
    text = clean_text(text)
    heads = list(ATA.finditer(text))
    out: list[AtaDO] = []
    for i, h in enumerate(heads):
        mes = MESES.get(fold(h.group(4)).upper())
        if not mes:
            continue
        body = text[h.end():heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        # stop at the next unrelated record (committee minutes, public hearings)
        stop = re.search(r"\nATA\s+DA\s+\d+\s*[ªºa°]?\s*(REUNI[ÃA]O|AUDI[ÊE]NCIA)", body)
        if stop:
            body = body[:stop.start()]
        pres = re.search(r"com\s+a\s+presen[çc]a\s+d[oa]s\s+(?:senhor(?:es|as)?\s+)?deputad[oa]s?\s*:?(.*?)\((\d+)\)", body[:6000], re.I | re.S)
        presentes = split_names(pres.group(1)) if pres else []
        lists = find_lists(body)
        votos = group_votes(body, lists)
        so_totais = []
        for m in re.finditer(r"Votaram\s+(\d+)\s+(?:Srs?\.|senhores)?\s*(?:deputad[oa]s|parlamentares)\s*[:.]?\s*(\d+)\s*[“\"]\s*sim", body, re.I):
            if not any(v.start - 400 <= m.start() <= v.end + 50 for v in votos):
                so_totais.append(re.sub(r"\s+", " ", body[m.start():m.start() + 80]))
        tipo = {"ORDINARIA": "Ordinária", "EXTRAORDINARIA": "Extraordinária", "SOLENE": "Solene", "ESPECIAL": "Especial"}[fold(h.group(2)).upper()]
        out.append(AtaDO(numero=int(h.group(1)), tipo=tipo, data=f"{h.group(5)}-{mes:02d}-{int(h.group(3)):02d}",
                         presentes=presentes, presentes_impresso=int(pres.group(2)) if pres else None,
                         votos=votos, so_totais=so_totais))
    return out


def fold(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))
