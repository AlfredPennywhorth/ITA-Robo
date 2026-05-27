"""Verifica links da página: quebrados e domínios de legislação oficial."""

from __future__ import annotations

from urllib.parse import urlparse

import requests

from app.config import DOMINIOS_LEGISLACAO_OFICIAL, REQUEST_HEADERS, REQUEST_TIMEOUT
from app.crawler.parser import extrair_links
from app.validators.base import ResultadoCriterio, StatusValidacao


def validar_links_quebrados(
    html: str, url_base: str, modulo: str = "", max_links: int = 30, timeout: int = REQUEST_TIMEOUT
) -> ResultadoCriterio:
    """Verifica se há links quebrados (status HTTP 4xx/5xx).

    Limita a verificação a max_links links para não sobrecarregar.
    O parâmetro timeout controla o tempo máximo de espera por link (segundos).
    """
    links = extrair_links(html, url_base)[:max_links]
    quebrados: list[str] = []
    verificados = 0

    for link in links:
        href = link["href_absoluto"]
        if not href.startswith("http"):
            continue
        try:
            resp = requests.head(
                href, headers=REQUEST_HEADERS, timeout=timeout, allow_redirects=True
            )
            if resp.status_code >= 400:
                quebrados.append(f"{href} (HTTP {resp.status_code})")
            verificados += 1
        except requests.exceptions.RequestException:
            quebrados.append(f"{href} (erro de conexão)")
            verificados += 1

    if not verificados:
        return ResultadoCriterio(
            criterio_id="links_quebrados",
            descricao="Ausência de links quebrados na página",
            status=StatusValidacao.NAO_VERIFICADO,
            evidencia="Nenhum link HTTP verificado.",
            url=url_base,
            modulo=modulo,
        )

    if quebrados:
        return ResultadoCriterio(
            criterio_id="links_quebrados",
            descricao="Ausência de links quebrados na página",
            status=StatusValidacao.NAO_CONFORME,
            evidencia=f"{len(quebrados)} link(s) quebrado(s): " + "; ".join(quebrados[:5]),
            url=url_base,
            modulo=modulo,
            detalhes={"links_quebrados": quebrados},
        )

    return ResultadoCriterio(
        criterio_id="links_quebrados",
        descricao="Ausência de links quebrados na página",
        status=StatusValidacao.CONFORME,
        evidencia=f"Todos os {verificados} links verificados estão acessíveis.",
        url=url_base,
        modulo=modulo,
    )


def validar_legislacao_oficial(
    html: str, url_base: str, dominios_oficiais: list[str] | None = None, modulo: str = ""
) -> ResultadoCriterio:
    """Verifica se links de legislação apontam para repositório oficial."""
    if dominios_oficiais is None:
        dominios_oficiais = DOMINIOS_LEGISLACAO_OFICIAL

    links = extrair_links(html, url_base)
    links_legislacao = [
        l for l in links
        if any(palavra in l["texto"].lower() for palavra in ["lei ", "decreto", "portaria", "resolução", "instrução normativa"])
    ]

    if not links_legislacao:
        return ResultadoCriterio(
            criterio_id="legislacao_oficial",
            descricao="Links de legislação apontam para repositório oficial",
            status=StatusValidacao.NAO_APLICAVEL,
            evidencia="Nenhum link de legislação identificado na página.",
            url=url_base,
            modulo=modulo,
        )

    nao_oficiais = []
    for link in links_legislacao:
        dominio = urlparse(link["href_absoluto"]).netloc.lower()
        if not any(oficial in dominio for oficial in dominios_oficiais):
            nao_oficiais.append(link["href_absoluto"])

    if not nao_oficiais:
        return ResultadoCriterio(
            criterio_id="legislacao_oficial",
            descricao="Links de legislação apontam para repositório oficial",
            status=StatusValidacao.CONFORME,
            evidencia=f"Todos os {len(links_legislacao)} links de legislação apontam para repositório oficial.",
            url=url_base,
            modulo=modulo,
        )

    parcial = len(nao_oficiais) < len(links_legislacao)
    return ResultadoCriterio(
        criterio_id="legislacao_oficial",
        descricao="Links de legislação apontam para repositório oficial",
        status=StatusValidacao.PARCIAL if parcial else StatusValidacao.NAO_CONFORME,
        evidencia=(
            f"{len(nao_oficiais)} de {len(links_legislacao)} links de legislação "
            f"não apontam para repositório oficial: {'; '.join(nao_oficiais[:3])}"
        ),
        url=url_base,
        modulo=modulo,
        detalhes={"links_nao_oficiais": nao_oficiais},
    )
