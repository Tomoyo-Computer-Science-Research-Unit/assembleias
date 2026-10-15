"""Name normalisation and the resolver used to join deputados across sources.

Sources never carry the ``cvd`` id except the two roster pages, so attendance rows, roll-call
names and SPL author strings are matched by normalised name. ``NameResolver`` does the join:
exact match, alias table, token-subset match ("Dr. Gilberto" ~ "Gilberto"), close spelling
("Welington"/"Wellington"), and finally a split of run-on strings produced by a missing comma
("Rodrigo Vizeu Salvino Oliveira" -> two people).
"""
from __future__ import annotations

import difflib
import re
import unicodedata

_TITLES = re.compile(r"^(deputad[oa]s?|sr\.?a?|dra?\.?|prof\.?a?|professora?|pastora?|delegad[oa]|coronel|capit[aã]o|major|sargento)\s+", re.I)

# Normalised alias -> normalised nome_parlamentar as printed on camara.rio.
# Only add what the sources actually print; keep the right-hand side exactly as the roster has it.
ALIASES: dict[str, str] = {
    # spelling variants seen in transcripts / attendance tables -> roster spelling
    "wellington dias": "welington dias",
    "william coelho": "willian coelho",
    "rogerio amorim": "dr rogerio amorim",
    "celio lupparelli": "prof celio lupparelli",
    "luiz carlos ramos filho": "luiz ramos filho",
}

# Author strings that are not people (institutions, committees); never resolved to a deputado.
_INSTITUTIONAL = re.compile(r"^(poder executivo|mesa diretora|comiss(ao|oes) |tribunal |prefeit|procurador|ministerio|defensoria|camara)", re.I)


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("’", "'").replace("`", "'")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    while True:
        t = _TITLES.sub("", s)
        if t == s:
            return s
        s = t


def norm_keep_titles(name: str) -> str:
    """Like norm() but keeps 'Dr.'/'Prof.' -- the roster prints them as part of the parliamentary name."""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"^(deputad[oa]s?|sra?) ", "", s)


def slug(name: str) -> str:
    return norm(name).replace("'", "").replace(" ", "-")


def is_institutional(author: str) -> bool:
    return bool(_INSTITUTIONAL.match(norm_keep_titles(author)))


class NameResolver:
    """Map free-text names to deputado ids. Unmatched names are counted in ``unmatched``."""

    def __init__(self, deputados: list, aliases: dict[str, str] | None = None) -> None:
        self.index: dict[str, str] = {}
        self.index_titled: dict[str, str] = {}
        for v in deputados:
            vid = v["id"] if isinstance(v, dict) else v.id
            for nm in {(v["nome_parlamentar"] if isinstance(v, dict) else v.nome_parlamentar),
                       (v["nome"] if isinstance(v, dict) else v.nome)}:
                if not nm:
                    continue
                self.index.setdefault(norm(nm), vid)
                self.index_titled.setdefault(norm_keep_titles(nm), vid)
        for a, b in {**ALIASES, **(aliases or {})}.items():
            target = self.index.get(norm(b)) or self.index_titled.get(norm_keep_titles(b))
            if target:
                self.index.setdefault(norm(a), target)
                self.index_titled.setdefault(norm_keep_titles(a), target)
        self.unmatched: dict[str, int] = {}
        self._cache: dict[str, list[str]] = {}

    def add(self, vid: str, nome: str) -> None:
        self.index.setdefault(norm(nome), vid)
        self.index_titled.setdefault(norm_keep_titles(nome), vid)
        self._cache.clear()

    def _one(self, key: str) -> str | None:
        if key in self.index:
            return self.index[key]
        toks = set(key.split())
        if len(toks) == 0:
            return None
        # token subset ("Dr. Gilberto" vs "Gilberto", "Rafael Aloisio Freitas" vs "Rafael Aloísio Freitas")
        best = [k for k in self.index if toks <= set(k.split()) or set(k.split()) <= toks]
        if len(best) != 1:
            best = difflib.get_close_matches(key, list(self.index), n=1, cutoff=0.9)
        if len(best) == 1:
            return self.index[best[0]]
        return None

    def resolve(self, name: str, *, count_unmatched: bool = True) -> list[str]:
        """Return the ids for ``name`` (one id normally; two or more for run-on strings; [] if unknown)."""
        raw = name.strip()
        if raw in self._cache:
            return self._cache[raw]
        out: list[str] = []
        key_t = norm_keep_titles(raw)
        if key_t in self.index_titled:
            out = [self.index_titled[key_t]]
        else:
            key = norm(raw)
            one = self._one(key)
            if one:
                out = [one]
            else:
                toks = key.split()
                for i in range(1, len(toks)):  # missing comma between two names
                    a, b = " ".join(toks[:i]), " ".join(toks[i:])
                    if a in self.index and b in self.index:
                        out = [self.index[a], self.index[b]]
                        break
        if not out and count_unmatched:
            self.unmatched[raw] = self.unmatched.get(raw, 0) + 1
        self._cache[raw] = out
        return out

    def resolve_one(self, name: str) -> str:
        ids = self.resolve(name)
        return ids[0] if len(ids) == 1 else (ids[0] if ids else f"nome:{slug(name)}")


_PERSON_MARK = re.compile(r"^(?:autoria\s+)?(?:d[oa]s?\s+)?(?:senhor(?:es|as?)\s+)?(?:nobres?\s+)?deputad[oa]s?\s+", re.I)
_INST_MARK = re.compile(r"^(?:autoria\s+)?(?:d[oa]s?\s+)?(?:comiss(?:ao|ão|oes|ões)|poder|mesa|tribunal|prefeit|procurador|ministerio|ministério|defensoria|camara|câmara)\b", re.I)


def split_authors(s: str) -> list[str]:
    """Split an author string into one string per author.

    Handles the SPL form ("VEREADOR A, VEREADORA B E VEREADOR C") and the transcript form
    ("VEREADORES A, B E C", "AUTORIA DOS VEREADORES A, B, DAS COMISSÕES DE X, DE Y E DO VEREADOR Z").
    Institutional segments (committees, Poder Executivo) are kept whole, so a committee name that
    contains commas or " E " is not broken up. "E OUTROS" is dropped (see has_others()).
    """
    s = re.sub(r"\s+", " ", s or "").strip(" .;")
    s = re.sub(r"\s*,?\s*E OUTR[OA]S\.?$", "", s, flags=re.I)
    if not s:
        return []
    out: list[str] = []
    mode: str | None = None          # "person" | "inst"
    inst_buf: list[str] = []

    def flush_inst() -> None:
        if inst_buf:
            out.append(", ".join(inst_buf))
            inst_buf.clear()

    for seg in re.split(r"\s*,\s*|\s*;\s*", s):
        if not seg:
            continue
        if _PERSON_MARK.match(seg):
            flush_inst()
            mode = "person"
            seg = _PERSON_MARK.sub("", seg)
        elif _INST_MARK.match(seg):
            mode = "inst"
            seg = re.sub(r"^(?:autoria\s+)?(?:d[oa]s?\s+)", "", seg, flags=re.I)
        elif mode is None:
            mode = "inst" if is_institutional(seg) else "person"
        if mode == "inst":
            # a trailing " E DO VEREADOR X" inside an institutional segment starts a person again
            m = re.search(r"\s+E\s+(?:D[OA]S?\s+)?(?:SENHOR(?:ES|AS?)\s+)?DEPUTAD[OA]S?\s+(.+)$", seg, re.I)
            if m:
                inst_buf.append(seg[:m.start()].strip())
                flush_inst()
                mode = "person"
                seg = m.group(1)
            else:
                inst_buf.append(seg.strip())
                continue
        tail = None
        m = re.search(r"\s+E\s+(?=(?:D[OA]S?\s+)?(?:COMISS|PODER|MESA|TRIBUNAL|PREFEIT|PROCURADOR|MINIST|DEFENSORIA|C[AÂ]MARA))", seg, re.I)
        if m:                      # "... E DAS COMISSÕES DE X" inside a person segment
            seg, tail = seg[:m.start()], seg[m.end():]
        for part in re.split(r"\s+E\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", seg):
            part = re.sub(r"^(?:d[oa]s?\s+)?(?:senhor(?:es|as?)\s+)?deputad[oa]s?\s+", "", part.strip(" ."), flags=re.I)
            if part:
                out.append(part)
        if tail:
            mode = "inst"
            inst_buf.append(re.sub(r"^(?:d[oa]s?\s+)", "", tail.strip(), flags=re.I))
    flush_inst()
    return out


def has_others(s: str) -> bool:
    return bool(re.search(r"\bE OUTR[OA]S\b", s or "", re.I))
