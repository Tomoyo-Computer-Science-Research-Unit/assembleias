"""The deputado record every adapter writes into the snapshot."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Deputado:
    id: str                     # "<casa>:<id in the casa's own system>", stable across sources
    nome: str
    nome_parlamentar: str
    partido: str | None
    legislaturas: list[int] = field(default_factory=list)
    partidos_por_legislatura: dict[str, str] = field(default_factory=dict)
    situacao: str | None = None  # "em_exercicio" | "fora_de_exercicio"
    foto: str | None = None
    gabinete: str | None = None
    telefone: str | None = None
    email: str | None = None
    perfil_url: str | None = None
