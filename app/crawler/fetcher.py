"""Busca HTML simples usando requests."""

import requests
from app.config import REQUEST_HEADERS, REQUEST_TIMEOUT


def buscar_html(url: str) -> tuple[str | None, str | None]:
    """Faz GET na URL e retorna (html, erro).

    Retorna (None, mensagem_de_erro) em caso de falha.
    """
    try:
        resposta = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        resposta.raise_for_status()
        resposta.encoding = resposta.apparent_encoding or "utf-8"
        return resposta.text, None
    except requests.exceptions.Timeout:
        return None, f"Timeout ao acessar {url}"
    except requests.exceptions.ConnectionError:
        return None, f"Erro de conexão ao acessar {url}"
    except requests.exceptions.HTTPError as exc:
        return None, f"HTTP {exc.response.status_code} ao acessar {url}"
    except requests.exceptions.RequestException as exc:
        return None, f"Erro ao acessar {url}: {exc}"


def verificar_link(url: str) -> tuple[bool, int | None, str | None]:
    """Verifica se um link está acessível.

    Retorna (ok, status_code, erro).
    """
    try:
        resposta = requests.head(
            url,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        ok = resposta.status_code < 400
        return ok, resposta.status_code, None
    except requests.exceptions.RequestException as exc:
        return False, None, str(exc)
