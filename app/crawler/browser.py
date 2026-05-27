"""Coleta HTML com Playwright — fallback para páginas dinâmicas (JavaScript)."""

from __future__ import annotations

import contextlib
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

_CHROMIUM_INSTALADO = False

_CONTEXTO_FECHADO_MSGS = (
    "Target page, context or browser has been closed",
    "has been closed",
    "Target closed",
)

_RESOURCE_TYPES_BLOQUEADOS = {"image", "media", "font", "stylesheet"}
_TRACKING_PATTERNS = (
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick.net",
    "facebook.net",
    "hotjar.com",
    "/gtm.js",
)


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


def _contexto_fechado(exc: Exception) -> bool:
    """Verifica se a exceção indica que o contexto/página/browser foi fechado."""
    msg = str(exc)
    return any(m in msg for m in _CONTEXTO_FECHADO_MSGS)


def _navegar_resiliente(page, url: str) -> None:
    """Navega para a URL com estratégia resiliente.

    Usa apenas domcontentloaded (mais tolerante a scripts lentos).
    Aguarda 2 s adicionais para carregamento parcial de JS.
    """
    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_timeout(2_000)


def _configurar_bloqueio_recursos(page) -> None:  # noqa: ANN001
    def _interceptar(route, request):  # noqa: ANN001
        req_url = request.url.lower()
        if request.resource_type in _RESOURCE_TYPES_BLOQUEADOS:
            route.abort()
            return
        if any(padrao in req_url for padrao in _TRACKING_PATTERNS):
            route.abort()
            return
        route.continue_()

    page.route("**/*", _interceptar)


def buscar_html_dinamico(url: str) -> tuple[str | None, str | None]:
    """Acessa a URL com Playwright e retorna (html, erro).

    Usa Playwright apenas quando necessário (páginas Liferay/JS-heavy).
    Retorna (None, mensagem_de_erro) em caso de falha.

    Estratégia resiliente:
    - Navega com wait_until="domcontentloaded" + 2 s de espera
    - Networkidle é opcional e nunca bloqueia
    - Se "Target page, context or browser has been closed", recria tudo e tenta uma vez
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout  # noqa: PLC0415
    except ImportError:
        return None, "Playwright não instalado. Execute: playwright install chromium"

    def _executar_uma_vez(pw) -> tuple[str | None, str | None]:  # noqa: ANN001
        browser = None
        context = None
        try:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (compatible; ITA-Robo/1.0; "
                    "+https://github.com/AlfredPennywhorth/ITA-Robo)"
                )
            )
            page = context.new_page()
            _configurar_bloqueio_recursos(page)
            try:
                _navegar_resiliente(page, url)
            except PWTimeout:
                return None, f"Timeout (Playwright) ao acessar {url}"
            html = page.content()
            return html, None
        except PWTimeout:
            return None, f"Timeout (Playwright) ao acessar {url}"
        except Exception as exc:  # noqa: BLE001
            return None, exc  # type: ignore[return-value]
        finally:
            with contextlib.suppress(Exception):
                if context is not None:
                    context.close()
            with contextlib.suppress(Exception):
                if browser is not None:
                    browser.close()

    def _executar() -> tuple[str | None, str | None]:
        try:
            with sync_playwright() as pw:
                html, err = _executar_uma_vez(pw)
                # Recuperação: se contexto foi fechado, tenta uma segunda vez
                if err is not None and isinstance(err, Exception) and _contexto_fechado(err):
                    logger.warning("Contexto Playwright fechado; recriando para %s", url)
                    html, err = _executar_uma_vez(pw)
                return html, err
        except Exception as exc:  # noqa: BLE001
            return None, exc  # type: ignore[return-value]

    html, err = _executar()
    if err is not None and isinstance(err, Exception) and _exe_nao_encontrado(err):
        install_err = _garantir_chromium()
        if install_err:
            return None, install_err
        html, err = _executar()

    if err is not None and isinstance(err, Exception):
        if _contexto_fechado(err):
            return None, f"Página inacessível (contexto Playwright fechado) ao acessar {url}"
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
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout  # noqa: PLC0415
    except ImportError:
        return "Playwright não instalado."

    def _executar() -> str | None:
        browser = None
        context = None
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
                _configurar_bloqueio_recursos(page)
                _navegar_resiliente(page, url)
                page.screenshot(path=caminho_arquivo, full_page=True)
            return None
        except Exception as exc:  # noqa: BLE001
            return str(exc)
        finally:
            with contextlib.suppress(Exception):
                if context is not None:
                    context.close()
            with contextlib.suppress(Exception):
                if browser is not None:
                    browser.close()

    err = _executar()
    if err is not None and _exe_nao_encontrado(Exception(err)):
        install_err = _garantir_chromium()
        if install_err:
            return install_err
        err = _executar()

    return err
