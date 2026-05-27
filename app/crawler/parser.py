"""Extrai informações estruturadas do HTML de uma página."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from dateutil import parser as date_parser  # type: ignore[import]


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def extrair_links(html: str, url_base: str) -> list[dict]:
    """Retorna lista de dicts {texto, href, href_absoluto} dos links da página."""
    soup = _soup(html)
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        texto = tag.get_text(separator=" ", strip=True)
        href_abs = urljoin(url_base, href)
        links.append({"texto": texto, "href": href, "href_absoluto": href_abs})
    return links


def extrair_titulos(html: str) -> list[dict]:
    """Retorna lista de dicts {nivel, texto} dos cabeçalhos h1-h4."""
    soup = _soup(html)
    titulos = []
    for nivel in range(1, 5):
        for tag in soup.find_all(f"h{nivel}"):
            texto = tag.get_text(separator=" ", strip=True)
            if texto:
                titulos.append({"nivel": nivel, "texto": texto})
    return titulos


def extrair_texto_visivel(html: str) -> str:
    """Retorna o texto visível da página (sem scripts/estilos)."""
    soup = _soup(html)
    for tag in soup(["script", "style", "noscript", "meta", "head"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def extrair_arquivos_download(html: str, url_base: str) -> list[dict]:
    """Retorna links que apontam para arquivos baixáveis, com extensão detectada."""
    EXTENSOES = {
        ".pdf", ".csv", ".xlsx", ".xls", ".ods", ".odt", ".doc",
        ".docx", ".zip", ".rar", ".txt", ".json", ".xml",
    }
    links = extrair_links(html, url_base)
    arquivos = []
    for link in links:
        caminho = urlparse(link["href_absoluto"]).path.lower()
        ext = _extensao(caminho)
        if ext in EXTENSOES:
            arquivos.append({**link, "extensao": ext})
    return arquivos


def _extensao(caminho: str) -> str:
    """Extrai extensão do caminho, retorna '' se não encontrar."""
    partes = caminho.rsplit(".", 1)
    return f".{partes[-1]}" if len(partes) == 2 else ""


def extrair_datas(html: str) -> list[str]:
    """Tenta encontrar datas no texto da página."""
    texto = extrair_texto_visivel(html)
    # Padrão brasileiro: dd/mm/yyyy ou dd/mm/yy
    padrao_br = re.findall(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", texto)
    # Padrão por extenso: "10 de maio de 2026"
    padrao_extenso = re.findall(
        r"\b\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b", texto, re.IGNORECASE
    )
    return padrao_br + padrao_extenso


def extrair_data_atualizacao(html: str) -> str | None:
    """Procura pelo padrão 'Atualizado em ...' ou 'Última atualização ...'."""
    texto = extrair_texto_visivel(html)
    padrao = re.search(
        r"(atualizado\s+em|última\s+atualização|última\s+modificação)[:\s]+([^\n.]{5,40})",
        texto,
        re.IGNORECASE,
    )
    if padrao:
        return padrao.group(2).strip()
    return None


def extrair_menu_botoes(html: str, url_base: str) -> list[dict]:
    """Extrai itens de menus de navegação (nav, ul.menu, header)."""
    soup = _soup(html)
    botoes = []

    # Procura em elementos de navegação comuns
    containers = soup.find_all(["nav", "header"]) or [soup]
    for container in containers:
        for tag in container.find_all("a", href=True):
            texto = tag.get_text(separator=" ", strip=True)
            href_abs = urljoin(url_base, tag["href"].strip())
            if texto:
                botoes.append({"texto": texto, "href_absoluto": href_abs})

    return botoes
