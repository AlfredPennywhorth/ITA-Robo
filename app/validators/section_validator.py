"""Verifica se as seções obrigatórias estão presentes em uma página."""

from __future__ import annotations

import unicodedata

from rapidfuzz import fuzz

from app.crawler.parser import extrair_cards_navegacao, extrair_texto_visivel, extrair_titulos
from app.validators.base import ResultadoCriterio, StatusValidacao

LIMIAR_TITULO = 80   # Similaridade mínima para título
LIMIAR_TEXTO = 70    # Similaridade mínima para busca em texto corrido


def _normalizar_texto(texto: str) -> str:
    texto_nfkd = unicodedata.normalize("NFKD", texto or "")
    sem_acentos = "".join(ch for ch in texto_nfkd if not unicodedata.combining(ch))
    return " ".join(sem_acentos.lower().replace("-", " ").replace("_", " ").split())


def _secao_em_titulos(secao: str, titulos: list[dict]) -> tuple[bool, str]:
    for t in titulos:
        score = fuzz.partial_ratio(_normalizar_texto(secao), _normalizar_texto(t["texto"]))
        if score >= LIMIAR_TITULO:
            return True, f'Seção "{t["texto"]}" encontrada como H{t["nivel"]}.'
    return False, ""


def _secao_em_texto(secao: str, texto: str) -> tuple[bool, str]:
    score = fuzz.partial_ratio(_normalizar_texto(secao), _normalizar_texto(texto))
    if score >= LIMIAR_TEXTO:
        return True, f'Texto semelhante a "{secao}" encontrado no corpo da página.'
    return False, ""


def _secao_em_cards(secao: str, cards: list[dict]) -> tuple[bool, str, dict]:
    melhor_card: dict = {}
    melhor_score = 0
    termo_norm = _normalizar_texto(secao)

    for card in cards:
        texto_card = " ".join(
            filtro for filtro in (
                card.get("texto_principal", ""),
                card.get("titulo", ""),
                card.get("descricao", ""),
                card.get("texto", ""),
            ) if filtro
        )
        score = fuzz.partial_ratio(termo_norm, _normalizar_texto(texto_card))
        if score >= LIMIAR_TITULO and score > melhor_score:
            melhor_score = score
            melhor_card = card

    if melhor_card:
        return True, f'Seção "{secao}" encontrada como card/botão de navegação.', melhor_card
    return False, "", {}


def _resolver_entrada(entrada) -> tuple[str, list[str]]:
    """Normaliza uma entrada da lista de seções (str ou dict com nome/aliases).

    Retorna (nome_display, lista_de_termos_de_busca).
    """
    if isinstance(entrada, dict):
        nome = entrada.get("nome", "")
        aliases = entrada.get("aliases", [nome])
        return nome, [a for a in aliases if a]
    return entrada, [entrada]


def validar_secoes(
    html: str, url: str, secoes_obrigatorias: list, modulo: str = ""
) -> list[ResultadoCriterio]:
    """Verifica se cada seção obrigatória está presente na página.

    Cada entrada de secoes_obrigatorias pode ser:
    - str: nome simples da seção
    - dict com chaves ``nome`` (exibição) e ``aliases`` (lista de termos de busca)
    """
    titulos = extrair_titulos(html)
    texto_visivel = extrair_texto_visivel(html)
    cards = extrair_cards_navegacao(html, url)
    resultados: list[ResultadoCriterio] = []

    for entrada in secoes_obrigatorias:
        nome_display, termos = _resolver_entrada(entrada)

        criterio_id = (
            f"secao_{nome_display.lower().replace(' ', '_')[:30]}"
            .replace("ã", "a").replace("ç", "c").replace("é", "e")
            .replace("á", "a").replace("ê", "e").replace("ô", "o")
        )

        # Verifica cada termo (nome canônico + aliases)
        encontrado_titulo = False
        evidencia_titulo = ""
        encontrado_card = False
        evidencia_card = ""
        card_encontrado: dict = {}
        encontrado_texto = False
        evidencia_texto = ""

        for termo in termos:
            ok_c, ev_c, card = _secao_em_cards(termo, cards)
            if ok_c:
                encontrado_card = True
                evidencia_card = ev_c
                card_encontrado = card
                break

        if not encontrado_card:
            for termo in termos:
                ok_t, ev_t = _secao_em_titulos(termo, titulos)
                if ok_t:
                    encontrado_titulo = True
                    evidencia_titulo = ev_t
                    break

        if not encontrado_titulo and not encontrado_card:
            for termo in termos:
                ok_tx, ev_tx = _secao_em_texto(termo, texto_visivel)
                if ok_tx:
                    encontrado_texto = True
                    evidencia_texto = ev_tx
                    break

        if encontrado_titulo:
            resultados.append(
                ResultadoCriterio(
                    criterio_id=criterio_id,
                    descricao=f'Seção obrigatória: "{nome_display}"',
                    status=StatusValidacao.CONFORME,
                    evidencia=evidencia_titulo,
                    url=url,
                    modulo=modulo,
                )
            )
        elif encontrado_card:
            resultados.append(
                ResultadoCriterio(
                    criterio_id=criterio_id,
                    descricao=f'Seção obrigatória: "{nome_display}"',
                    status=StatusValidacao.CONFORME,
                    evidencia=evidencia_card,
                    url=url,
                    modulo=modulo,
                    detalhes={"card": card_encontrado},
                )
            )
        elif encontrado_texto:
            resultados.append(
                ResultadoCriterio(
                    criterio_id=criterio_id,
                    descricao=f'Seção obrigatória: "{nome_display}"',
                    status=StatusValidacao.PARCIAL,
                    evidencia=evidencia_texto
                    + " (não encontrada como título formal)",
                    url=url,
                    modulo=modulo,
                )
            )
        else:
            resultados.append(
                ResultadoCriterio(
                    criterio_id=criterio_id,
                    descricao=f'Seção obrigatória: "{nome_display}"',
                    status=StatusValidacao.NAO_CONFORME,
                    evidencia=f'Seção "{nome_display}" não encontrada na página.',
                    url=url,
                    modulo=modulo,
                )
            )

    return resultados
