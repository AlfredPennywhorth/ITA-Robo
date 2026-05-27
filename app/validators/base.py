"""Estrutura base de resultado de validação."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StatusValidacao(str, Enum):
    """Status possíveis de um critério verificado."""

    CONFORME = "CONFORME"
    PARCIAL = "PARCIALMENTE CONFORME"
    NAO_CONFORME = "NÃO CONFORME"
    NAO_APLICAVEL = "NÃO APLICÁVEL"
    NAO_VERIFICADO = "NÃO VERIFICADO AUTOMATICAMENTE"


# Mapeamento de pontuação por status
PONTUACAO_STATUS: dict[StatusValidacao, float | None] = {
    StatusValidacao.CONFORME: 1.0,
    StatusValidacao.PARCIAL: 0.5,
    StatusValidacao.NAO_CONFORME: 0.0,
    StatusValidacao.NAO_APLICAVEL: None,
    StatusValidacao.NAO_VERIFICADO: None,
}


@dataclass
class ResultadoCriterio:
    """Representa o resultado de avaliação de um critério."""

    criterio_id: str
    descricao: str
    status: StatusValidacao = StatusValidacao.NAO_VERIFICADO
    evidencia: str = ""
    url: str = ""
    modulo: str = ""
    detalhes: dict[str, Any] = field(default_factory=dict)

    @property
    def pontuacao(self) -> float | None:
        """Retorna pontuação numérica do status (None = não entra no cálculo)."""
        return PONTUACAO_STATUS[self.status]

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterio_id": self.criterio_id,
            "modulo": self.modulo,
            "descricao": self.descricao,
            "status": self.status.value,
            "pontuacao": self.pontuacao,
            "evidencia": self.evidencia,
            "url": self.url,
        }


def calcular_pontuacao_modulo(resultados: list[ResultadoCriterio]) -> float:
    """Calcula a pontuação percentual de uma lista de resultados.

    Critérios NAO_APLICAVEL e NAO_VERIFICADO não entram no cálculo.
    Retorna valor de 0 a 100 (percentual).
    """
    entram = [r for r in resultados if r.pontuacao is not None]
    if not entram:
        return 0.0
    total = sum(r.pontuacao for r in entram)  # type: ignore[misc]
    return round((total / len(entram)) * 100, 1)
