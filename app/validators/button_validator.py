"""Verifica a presença dos botões obrigatórios na página inicial."""

from __future__ import annotations

from rapidfuzz import fuzz

from app.crawler.parser import extrair_links, extrair_menu_botoes
from app.validators.base import ResultadoCriterio, StatusValidacao

# Limiar mínimo de similaridade para aceitar uma correspondência fuzzy
LIMIAR_SIMILARIDADE = 80


def _encontrar_botao(
    texto_alvo: str, links: list[dict]
) -> tuple[bool, str, str]:
    """Busca o texto_alvo nos links, com tolerância a variações.

    Retorna (encontrado, evidência, href_absoluto).
    """
    for link in links:
        texto = link.get("texto", "")
        score = fuzz.partial_ratio(texto_alvo.lower(), texto.lower())
        if score >= LIMIAR_SIMILARIDADE:
            return True, f'Link encontrado: "{texto}" → {link["href_absoluto"]}', link[
                "href_absoluto"
            ]
    return False, f'Botão "{texto_alvo}" não localizado na página.', ""


def validar_botoes(
    html: str, url_base: str, botoes_config: list[dict]
) -> list[ResultadoCriterio]:
    """Valida a presença de botões obrigatórios na página.

    botoes_config: lista de dicts com chaves 'texto', 'obrigatorio', 'posicao_esperada' (opcional).

    Distinção de contexto:
    - CONFORME: link encontrado dentro de elemento nav/header (menu principal).
    - PARCIAL: link encontrado fora do menu principal (corpo, rodapé, breadcrumb).
    - NAO_CONFORME: nenhum link com o texto encontrado.
    """
    links_menu = extrair_menu_botoes(html, url_base)
    todos_links = extrair_links(html, url_base)

    resultados: list[ResultadoCriterio] = []

    for botao in botoes_config:
        texto_alvo = botao.get("texto", "")
        obrigatorio = botao.get("obrigatorio", True)
        posicao_esperada = botao.get("posicao_esperada")

        criterio_id = f"botao_{texto_alvo.lower().replace(' ', '_').replace('à', 'a').replace('ã', 'a')}"

        no_menu, ev_menu, href_menu = _encontrar_botao(texto_alvo, links_menu)
        na_pagina, ev_pagina, href_pagina = _encontrar_botao(texto_alvo, todos_links)

        if not na_pagina:
            # Não encontrado em lugar algum
            status = (
                StatusValidacao.NAO_CONFORME
                if obrigatorio
                else StatusValidacao.NAO_APLICAVEL
            )
            resultado = ResultadoCriterio(
                criterio_id=criterio_id,
                descricao=f'Botão "{texto_alvo}" presente na página inicial',
                status=status,
                evidencia=f'Botão "{texto_alvo}" não localizado na página.',
                url=url_base,
            )
        elif no_menu:
            # Encontrado no menu principal — verifica posição se necessário
            status = StatusValidacao.CONFORME
            evidencia = ev_menu
            if posicao_esperada is not None:
                posicao_real = _posicao_no_menu(texto_alvo, links_menu)
                if posicao_real is None or posicao_real != posicao_esperada:
                    status = StatusValidacao.PARCIAL
                    evidencia += (
                        f" | Posição esperada: {posicao_esperada}, "
                        f"posição encontrada: {posicao_real or 'indeterminada'}."
                    )
            resultado = ResultadoCriterio(
                criterio_id=criterio_id,
                descricao=f'Botão "{texto_alvo}" presente na página inicial',
                status=status,
                evidencia=evidencia,
                url=url_base,
                detalhes={"href": href_menu},
            )
        else:
            # Encontrado fora do menu principal (corpo, rodapé, breadcrumb)
            resultado = ResultadoCriterio(
                criterio_id=criterio_id,
                descricao=f'Botão "{texto_alvo}" presente na página inicial',
                status=StatusValidacao.PARCIAL,
                evidencia=ev_pagina + " (link fora do menu principal — verificar posicionamento)",
                url=url_base,
                detalhes={"href": href_pagina},
            )

        resultados.append(resultado)

    return resultados


def _posicao_no_menu(texto_alvo: str, links_menu: list[dict]) -> int | None:
    """Retorna a posição (1-based) do botão no menu, ou None se não encontrado."""
    for i, link in enumerate(links_menu, start=1):
        score = fuzz.partial_ratio(texto_alvo.lower(), link.get("texto", "").lower())
        if score >= LIMIAR_SIMILARIDADE:
            return i
    return None
