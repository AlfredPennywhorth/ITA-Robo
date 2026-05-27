"""Verifica datas de atualização nas páginas."""

from __future__ import annotations

from datetime import datetime

from dateutil import parser as date_parser

from app.crawler.parser import extrair_data_atualizacao, extrair_datas
from app.validators.base import ResultadoCriterio, StatusValidacao


def validar_data_atualizacao(
    html: str, url: str, modulo: str = ""
) -> ResultadoCriterio:
    """Verifica se a página possui data de atualização recente.

    Considera 'recente' como dentro dos últimos 13 meses.
    """
    data_texto = extrair_data_atualizacao(html)
    if not data_texto:
        # Tenta datas genéricas
        datas = extrair_datas(html)
        if not datas:
            return ResultadoCriterio(
                criterio_id="data_atualizacao",
                descricao="Página possui data de atualização",
                status=StatusValidacao.NAO_CONFORME,
                evidencia="Nenhuma data de atualização encontrada na página.",
                url=url,
                modulo=modulo,
            )
        data_texto = datas[0]

    # Tenta parsear a data encontrada
    try:
        data_encontrada = date_parser.parse(data_texto, dayfirst=True, fuzzy=True)
        agora = datetime.now()
        meses_diff = (agora.year - data_encontrada.year) * 12 + (
            agora.month - data_encontrada.month
        )
        if meses_diff <= 1:
            status = StatusValidacao.CONFORME
            evidencia = f'Data de atualização: "{data_texto}" (dentro do mês corrente)'
        elif meses_diff <= 13:
            status = StatusValidacao.PARCIAL
            evidencia = f'Data de atualização: "{data_texto}" ({meses_diff} meses atrás)'
        else:
            status = StatusValidacao.NAO_CONFORME
            evidencia = f'Data de atualização: "{data_texto}" ({meses_diff} meses atrás — desatualizado)'
    except (ValueError, OverflowError):
        status = StatusValidacao.PARCIAL
        evidencia = f'Data encontrada mas não parseada: "{data_texto}"'

    return ResultadoCriterio(
        criterio_id="data_atualizacao",
        descricao="Página possui data de atualização",
        status=status,
        evidencia=evidencia,
        url=url,
        modulo=modulo,
    )
