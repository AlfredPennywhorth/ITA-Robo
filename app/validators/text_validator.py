"""Verifica se textos padrão obrigatórios estão presentes na página."""

from __future__ import annotations

from rapidfuzz import fuzz

from app.crawler.parser import extrair_texto_visivel
from app.validators.base import ResultadoCriterio, StatusValidacao

LIMIAR_TEXTO_PADRAO = 75


def validar_texto_padrao(
    html: str, url: str, textos_padrao: list[str], modulo: str = ""
) -> list[ResultadoCriterio]:
    """Verifica se cada texto padrão está presente na página (busca por similaridade)."""
    texto_pagina = extrair_texto_visivel(html).lower()
    resultados: list[ResultadoCriterio] = []

    for texto in textos_padrao:
        criterio_id = (
            f"texto_{texto[:30].lower().replace(' ', '_')}"
        )
        score = fuzz.partial_ratio(texto.lower(), texto_pagina)
        if score >= LIMIAR_TEXTO_PADRAO:
            evidencia = f'Texto padrão encontrado (similaridade {score}%): "{texto[:80]}..."'
            status = StatusValidacao.CONFORME if score >= 90 else StatusValidacao.PARCIAL
        else:
            evidencia = f'Texto padrão não localizado: "{texto[:80]}..."'
            status = StatusValidacao.NAO_CONFORME

        resultados.append(
            ResultadoCriterio(
                criterio_id=criterio_id,
                descricao=f'Texto padrão obrigatório: "{texto[:60]}..."',
                status=status,
                evidencia=evidencia,
                url=url,
                modulo=modulo,
            )
        )

    return resultados
