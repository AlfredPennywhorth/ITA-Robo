"""Verifica se as seções obrigatórias estão presentes em uma página."""

from __future__ import annotations

from rapidfuzz import fuzz

from app.crawler.parser import extrair_titulos, extrair_texto_visivel
from app.validators.base import ResultadoCriterio, StatusValidacao

LIMIAR_TITULO = 80   # Similaridade mínima para título
LIMIAR_TEXTO = 70    # Similaridade mínima para busca em texto corrido


def _secao_em_titulos(secao: str, titulos: list[dict]) -> tuple[bool, str]:
    for t in titulos:
        score = fuzz.partial_ratio(secao.lower(), t["texto"].lower())
        if score >= LIMIAR_TITULO:
            return True, f'Seção "{t["texto"]}" encontrada como H{t["nivel"]}.'
    return False, ""


def _secao_em_texto(secao: str, texto: str) -> tuple[bool, str]:
    score = fuzz.partial_ratio(secao.lower(), texto.lower())
    if score >= LIMIAR_TEXTO:
        return True, f'Texto semelhante a "{secao}" encontrado no corpo da página.'
    return False, ""


def validar_secoes(
    html: str, url: str, secoes_obrigatorias: list[str], modulo: str = ""
) -> list[ResultadoCriterio]:
    """Verifica se cada seção obrigatória está presente na página."""
    titulos = extrair_titulos(html)
    texto_visivel = extrair_texto_visivel(html)
    resultados: list[ResultadoCriterio] = []

    for secao in secoes_obrigatorias:
        criterio_id = (
            f"secao_{secao.lower().replace(' ', '_')[:30]}"
            .replace("ã", "a").replace("ç", "c").replace("é", "e")
            .replace("á", "a").replace("ê", "e").replace("ô", "o")
        )

        encontrado_titulo, evidencia_titulo = _secao_em_titulos(secao, titulos)
        if encontrado_titulo:
            resultados.append(
                ResultadoCriterio(
                    criterio_id=criterio_id,
                    descricao=f'Seção obrigatória: "{secao}"',
                    status=StatusValidacao.CONFORME,
                    evidencia=evidencia_titulo,
                    url=url,
                    modulo=modulo,
                )
            )
            continue

        encontrado_texto, evidencia_texto = _secao_em_texto(secao, texto_visivel)
        if encontrado_texto:
            resultados.append(
                ResultadoCriterio(
                    criterio_id=criterio_id,
                    descricao=f'Seção obrigatória: "{secao}"',
                    status=StatusValidacao.PARCIAL,
                    evidencia=evidencia_texto
                    + " (não encontrada como título formal)",
                    url=url,
                    modulo=modulo,
                )
            )
            continue

        resultados.append(
            ResultadoCriterio(
                criterio_id=criterio_id,
                descricao=f'Seção obrigatória: "{secao}"',
                status=StatusValidacao.NAO_CONFORME,
                evidencia=f'Seção "{secao}" não encontrada na página.',
                url=url,
                modulo=modulo,
            )
        )

    return resultados
