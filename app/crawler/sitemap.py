"""Descobre páginas relacionadas via sitemap.xml ou varredura de links."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from app.crawler.fetcher import buscar_html
from app.crawler.parser import extrair_links


def _mesmo_dominio(url_base: str, url: str) -> bool:
    return urlparse(url_base).netloc == urlparse(url).netloc


def descobrir_paginas(url_base: str, profundidade: int = 1) -> list[str]:
    """Coleta URLs do mesmo domínio encontradas na página inicial.

    Parâmetro profundidade controla quantos níveis de links seguir (máx 2).
    """
    visitados: set[str] = set()
    fila = [url_base]
    encontrados: list[str] = []

    for _ in range(max(1, min(profundidade, 2))):
        proxima_fila: list[str] = []
        for url in fila:
            if url in visitados:
                continue
            visitados.add(url)
            html, erro = buscar_html(url)
            if erro or not html:
                continue
            for link in extrair_links(html, url):
                href = link["href_absoluto"]
                if _mesmo_dominio(url_base, href) and href not in visitados:
                    proxima_fila.append(href)
                    encontrados.append(href)
        fila = proxima_fila

    return list(dict.fromkeys(encontrados))  # remove duplicatas mantendo ordem


def buscar_sitemap(url_base: str) -> list[str]:
    """Tenta ler sitemap.xml e retorna lista de URLs."""
    candidatos = [
        urljoin(url_base, "/sitemap.xml"),
        urljoin(url_base, "/sitemap_index.xml"),
    ]
    urls: list[str] = []
    for sitemap_url in candidatos:
        html, erro = buscar_html(sitemap_url)
        if erro or not html:
            continue
        # Extrai <loc> do sitemap
        import re  # noqa: PLC0415
        for loc in re.findall(r"<loc>(.*?)</loc>", html, re.IGNORECASE):
            urls.append(loc.strip())
    return urls
