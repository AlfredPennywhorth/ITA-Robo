"""Coleta HTML com Playwright — fallback para páginas dinâmicas (JavaScript)."""

from __future__ import annotations

import contextlib


def buscar_html_dinamico(url: str) -> tuple[str | None, str | None]:
    """Acessa a URL com Playwright e retorna (html, erro).

    Usa Playwright apenas quando necessário (páginas Liferay/JS-heavy).
    Retorna (None, mensagem_de_erro) em caso de falha.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout  # noqa: PLC0415
    except ImportError:
        return None, "Playwright não instalado. Execute: playwright install chromium"

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (compatible; ITA-Robo/1.0; "
                    "+https://github.com/AlfredPennywhorth/ITA-Robo)"
                )
            )
            page = context.new_page()
            with contextlib.suppress(PWTimeout):
                page.goto(url, wait_until="networkidle", timeout=30_000)
            html = page.content()
            browser.close()
            return html, None
    except PWTimeout:
        return None, f"Timeout (Playwright) ao acessar {url}"
    except Exception as exc:  # noqa: BLE001
        return None, f"Erro (Playwright) ao acessar {url}: {exc}"


def capturar_screenshot(url: str, caminho_arquivo: str) -> str | None:
    """Captura screenshot da página e salva em caminho_arquivo.

    Retorna mensagem de erro ou None em caso de sucesso.
    """
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        return "Playwright não instalado."

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30_000)
            page.screenshot(path=caminho_arquivo, full_page=True)
            browser.close()
        return None
    except Exception as exc:  # noqa: BLE001
        return str(exc)
