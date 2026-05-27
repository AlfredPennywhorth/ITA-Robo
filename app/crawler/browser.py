"""Coleta HTML com Playwright — fallback para páginas dinâmicas (JavaScript)."""

from __future__ import annotations

import contextlib
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

_CHROMIUM_INSTALADO = False


def _garantir_chromium() -> str | None:
    """Instala o Chromium do Playwright se ainda não estiver disponível.

    Executa ``python -m playwright install chromium`` usando o mesmo
    interpretador em execução.  Sem ``--with-deps``, pois as dependências
    Linux já são fornecidas pelo packages.txt do Streamlit Cloud.

    Retorna None em caso de sucesso ou uma mensagem de erro amigável.
    """
    global _CHROMIUM_INSTALADO  # noqa: PLW0603
    if _CHROMIUM_INSTALADO:
        return None

    logger.info("Instalando Chromium do Playwright…")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error("playwright install chromium falhou: %s", result.stderr)
            return "Chromium do Playwright não pôde ser instalado no ambiente atual."
    except subprocess.TimeoutExpired:
        logger.error("playwright install chromium excedeu o timeout de 120s")
        return "Chromium do Playwright não pôde ser instalado no ambiente atual."
    except Exception as exc:  # noqa: BLE001
        logger.error("Erro ao instalar Chromium: %s", exc)
        return "Chromium do Playwright não pôde ser instalado no ambiente atual."

    _CHROMIUM_INSTALADO = True
    logger.info("Chromium instalado com sucesso.")
    return None


def _exe_nao_encontrado(exc: Exception) -> bool:
    """Verifica se a exceção indica que o executável do Chromium não existe."""
    return "Executable doesn't exist" in str(exc)


def buscar_html_dinamico(url: str) -> tuple[str | None, str | None]:
    """Acessa a URL com Playwright e retorna (html, erro).

    Usa Playwright apenas quando necessário (páginas Liferay/JS-heavy).
    Retorna (None, mensagem_de_erro) em caso de falha.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout  # noqa: PLC0415
    except ImportError:
        return None, "Playwright não instalado. Execute: playwright install chromium"

    def _executar() -> tuple[str | None, str | None]:
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
            return None, exc  # type: ignore[return-value]

    html, err = _executar()
    if err is not None and isinstance(err, Exception) and _exe_nao_encontrado(err):
        install_err = _garantir_chromium()
        if install_err:
            return None, install_err
        html, err = _executar()

    if err is not None and isinstance(err, Exception):
        return None, f"Erro (Playwright) ao acessar {url}: {err}"

    # Garante Chromium na próxima inicialização fria (primeira chamada sem erro)
    if err is None and not _CHROMIUM_INSTALADO:
        _garantir_chromium()

    return html, err  # type: ignore[return-value]


def capturar_screenshot(url: str, caminho_arquivo: str) -> str | None:
    """Captura screenshot da página e salva em caminho_arquivo.

    Retorna mensagem de erro ou None em caso de sucesso.
    """
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        return "Playwright não instalado."

    def _executar() -> str | None:
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

    err = _executar()
    if err is not None and _exe_nao_encontrado(Exception(err)):
        install_err = _garantir_chromium()
        if install_err:
            return install_err
        err = _executar()

    return err
