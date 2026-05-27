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


def _texto_limpo(texto: str) -> str:
    return " ".join(texto.split())


def _extrair_href_clicavel(tag) -> str | None:
    href = tag.get("href")
    if isinstance(href, str) and href.strip():
        return href.strip()

    for atributo in ("data-href", "data-url"):
        valor = tag.get(atributo)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()

    onclick = tag.get("onclick", "")
    if not isinstance(onclick, str):
        return None

    padrao = re.search(
        r"""(?:location(?:\.href)?|window\.location(?:\.href)?)\s*=\s*['"]([^'"]+)['"]""",
        onclick,
        re.IGNORECASE,
    )
    if padrao:
        return padrao.group(1).strip()
    return None


def _eh_candidato_card(tag) -> bool:
    classes = " ".join(tag.get("class", [])).lower()
    identificador = str(tag.get("id", "")).lower()
    classes_ancestrais = " ".join(
        f"{pai.get('id', '')} {' '.join(pai.get('class', []))}".lower()
        for pai in tag.parents
        if getattr(pai, "name", None)
    )
    descricao = f"{classes} {identificador} {classes_ancestrais}"
    palavras_card = (
        "card", "box", "tile", "item", "painel", "panel", "bloco", "botao",
    )
    possui_classe_card = any(p in descricao for p in palavras_card)
    possui_link = _extrair_href_clicavel(tag) is not None
    eh_clicavel = (
        possui_link
        or tag.get("role", "").lower() == "button"
        or str(tag.get("tabindex", "")).strip() == "0"
    )
    possui_bloco_interno = tag.find(["div", "section", "article", "p", "h1", "h2", "h3", "h4", "strong"])

    if tag.name == "a":
        return bool(possui_link and (possui_classe_card or possui_bloco_interno))
    return bool((possui_classe_card or eh_clicavel) and _texto_limpo(tag.get_text(" ", strip=True)))


def _titulo_descricao_card(tag) -> tuple[str, str, str]:
    titulo_tag = tag.find(["h1", "h2", "h3", "h4", "strong", "b"])
    titulo = _texto_limpo(titulo_tag.get_text(" ", strip=True)) if titulo_tag else ""
    texto = _texto_limpo(tag.get_text(" ", strip=True))

    if not titulo:
        partes = [parte.strip() for parte in re.split(r"\s{2,}|\n+", texto) if parte.strip()]
        titulo = partes[0] if partes else texto

    descricao = texto
    if titulo and texto.startswith(titulo):
        descricao = _texto_limpo(texto[len(titulo):].strip())

    return titulo or texto, descricao, texto


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


def extrair_cards_navegacao(html: str, url_base: str) -> list[dict]:
    """Extrai cards e botões de navegação, incluindo blocos clicáveis."""
    soup = _soup(html)
    dominio_base = urlparse(url_base).netloc.lower().removeprefix("www.")
    cards: list[dict] = []
    vistos: set[tuple[str, str]] = set()

    for ordem, tag in enumerate(soup.find_all(["a", "div", "section", "article", "li"]), start=1):
        if not _eh_candidato_card(tag):
            continue

        href = _extrair_href_clicavel(tag)
        href_absoluto = urljoin(url_base, href) if href else ""
        dominio = urlparse(href_absoluto).netloc.lower().removeprefix("www.") if href_absoluto else ""
        titulo, descricao, texto = _titulo_descricao_card(tag)
        texto_principal = _texto_limpo(titulo or texto)
        if not texto_principal:
            continue

        chave = (href_absoluto, texto_principal.lower())
        if chave in vistos:
            continue
        vistos.add(chave)

        cards.append(
            {
                "texto": texto,
                "texto_principal": texto_principal,
                "titulo": titulo,
                "descricao": descricao,
                "href": href or "",
                "href_absoluto": href_absoluto,
                "interno": bool(href_absoluto and dominio == dominio_base),
                "tag": tag.name,
                "classes": " ".join(tag.get("class", [])),
                "ordem": ordem,
            }
        )

    return cards
