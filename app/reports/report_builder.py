"""Constrói o DataFrame consolidado de resultados."""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from urllib.parse import urljoin, urlparse
import unicodedata

import pandas as pd
import yaml
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from app.config import RULES_DIR
from app.crawler.fetcher import buscar_html
from app.crawler.browser import buscar_html_dinamico
from app.validators.base import (
    ResultadoCriterio,
    StatusValidacao,
    calcular_pontuacao_modulo,
)
from app.validators.button_validator import validar_botoes
from app.validators.section_validator import validar_secoes
from app.validators.date_validator import validar_data_atualizacao
from app.validators.file_format_validator import validar_formatos_arquivos
from app.validators.link_validator import validar_links_quebrados, validar_legislacao_oficial
from app.validators.text_validator import validar_texto_padrao

import os


def _carregar_regra(nome_arquivo: str) -> dict:
    caminho = os.path.join(RULES_DIR, nome_arquivo)
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _buscar_html_com_fallback(url: str) -> tuple[str | None, str | None, bool]:
    """Tenta requests primeiro, depois Playwright se necessário.

    Retorna (html, erro, usou_playwright).
    """
    html, erro = buscar_html(url)
    if html:
        return html, None, False
    # Fallback para Playwright
    html, erro = buscar_html_dinamico(url)
    return html, erro, True


_MODULOS_NOMES = {
    "acesso_informacao": "Acesso à Informação",
    "participacao_social": "Participação Social",
    "quadro_servicos": "Quadro de Serviços",
}

_MODULOS_SLUG = {
    "acesso_informacao": "acesso-a-informacao",
    "participacao_social": "participacao-social",
    "quadro_servicos": "quadro-de-servicos",
}

_DOMINIOS_EXTERNOS_REJEITADOS = {
    "transparencia.prefeitura.sp.gov.br",
    "sp156.prefeitura.sp.gov.br",
    "legislacao.prefeitura.sp.gov.br",
    "www.planalto.gov.br",
}

_STATUS_PRIORIDADE = {
    StatusValidacao.CONFORME.value: 4,
    StatusValidacao.PARCIAL.value: 3,
    StatusValidacao.NAO_CONFORME.value: 2,
    StatusValidacao.NAO_VERIFICADO.value: 1,
    StatusValidacao.NAO_APLICAVEL.value: 0,
}


def _normalizar_dominio(url: str) -> str:
    dominio = urlparse(url).netloc.lower()
    return dominio[4:] if dominio.startswith("www.") else dominio


def _coletar_links_com_contexto(html: str, url_base: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    links: list[dict[str, Any]] = []
    dominio_base = _normalizar_dominio(url_base)

    for ordem, tag in enumerate(soup.find_all("a", href=True), start=1):
        href = tag["href"].strip()
        href_absoluto = urljoin(url_base, href)
        texto = tag.get_text(separator=" ", strip=True)
        dominio_link = _normalizar_dominio(href_absoluto)
        classes_tag = " ".join(tag.get("class", [])).lower()
        classes_ancestrais = " ".join(
            f"{p.get('id', '')} {' '.join(p.get('class', []))}".lower()
            for p in tag.parents
            if getattr(p, "name", None)
        )
        is_menu = any(
            p.name in ("nav", "header") for p in tag.parents if getattr(p, "name", None)
        )
        is_card = any(k in classes_ancestrais for k in ("card", "bloco", "box", "tile"))
        is_button = (
            tag.get("role", "").lower() == "button"
            or any(k in classes_tag for k in ("btn", "button", "botao", "cta"))
            or any(k in classes_ancestrais for k in ("btn", "button", "botao", "cta"))
        )
        links.append(
            {
                "texto": texto,
                "href": href,
                "href_absoluto": href_absoluto,
                "dominio": dominio_link,
                "interno": dominio_link == dominio_base,
                "is_menu": is_menu,
                "is_card": is_card,
                "is_button": is_button,
                "ordem": ordem,
            }
        )
    return links


def _normalizar_texto_busca(texto: str) -> str:
    texto_nfkd = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(ch for ch in texto_nfkd if not unicodedata.combining(ch))
    return " ".join(sem_acentos.lower().split())


def _resolve_entrada_secao(entrada: Any) -> tuple[str, list[str]]:
    if isinstance(entrada, dict):
        nome = entrada.get("nome", "")
        aliases = entrada.get("aliases", [nome])
        termos = [a for a in aliases if isinstance(a, str) and a.strip()]
        return nome, termos or [nome]
    if isinstance(entrada, str):
        return entrada, [entrada]
    return str(entrada), [str(entrada)]


def _score_correspondencia_link(texto_link: str, termo: str) -> int:
    texto_norm = _normalizar_texto_busca(texto_link)
    termo_norm = _normalizar_texto_busca(termo)
    if not texto_norm or not termo_norm:
        return 0
    if termo_norm in texto_norm or texto_norm in termo_norm:
        return 100
    return int(fuzz.partial_ratio(termo_norm, texto_norm))


def _descobrir_subpaginas_obrigatorias(
    html: str,
    url_pagina: str,
    subpaginas_obrigatorias: list[Any],
) -> dict[str, Any]:
    links = _coletar_links_com_contexto(html, url_pagina)
    encontrados: list[dict[str, str]] = []
    nao_encontrados: list[dict[str, str]] = []
    urls_ja_escolhidas: set[str] = set()

    for entrada in subpaginas_obrigatorias:
        nome_display, termos = _resolve_entrada_secao(entrada)
        melhor_link = None
        melhor_score = 0

        for link in links:
            if not link.get("interno"):
                continue
            href = link["href_absoluto"]
            if href in urls_ja_escolhidas:
                continue
            if href == url_pagina:
                continue

            score = max((_score_correspondencia_link(link.get("texto", ""), termo) for termo in termos), default=0)
            if score < 80:
                continue
            if score > melhor_score:
                melhor_score = score
                melhor_link = link

        if melhor_link:
            href = melhor_link["href_absoluto"]
            urls_ja_escolhidas.add(href)
            encontrados.append({"nome": nome_display, "url": href})
        else:
            nao_encontrados.append({"nome": nome_display})

    return {"encontrados": encontrados, "nao_encontrados": nao_encontrados}


def _validar_secoes_em_paginas(
    paginas: list[dict[str, str]],
    secoes: list[Any],
    modulo: str,
) -> list[ResultadoCriterio]:
    resultados: list[ResultadoCriterio] = []
    for secao in secoes:
        melhor: ResultadoCriterio | None = None
        melhor_url = ""
        for pagina in paginas:
            resultado_pagina = validar_secoes(
                pagina["html"],
                pagina["url"],
                [secao],
                modulo=modulo,
            )[0]
            prioridade = _STATUS_PRIORIDADE[resultado_pagina.status.value]
            prioridade_melhor = _STATUS_PRIORIDADE[melhor.status.value] if melhor else -1
            if prioridade > prioridade_melhor:
                melhor = resultado_pagina
                melhor_url = pagina["url"]

            if resultado_pagina.status == StatusValidacao.CONFORME:
                break

        if melhor is None:
            continue
        if melhor_url != paginas[0]["url"] and melhor.status in (
            StatusValidacao.CONFORME,
            StatusValidacao.PARCIAL,
        ):
            melhor.evidencia = f"Critério encontrado em subpágina ({melhor_url}). {melhor.evidencia}"
        resultados.append(melhor)
    return resultados


def _html_suficiente(html: str) -> bool:
    texto = BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)
    return len(texto) >= 120 and ("<a " in html.lower() or "<h" in html.lower())


def selecionar_url_principal_modulo(
    html: str,
    url_base: str,
    modulo: str,
    texto_botao: str,
) -> dict[str, Any]:
    slug = _MODULOS_SLUG.get(modulo, "")
    links = _coletar_links_com_contexto(html, url_base)
    candidatos: list[dict[str, Any]] = []
    for link in links:
        texto = link.get("texto", "")
        score_texto = fuzz.partial_ratio(texto_botao.lower(), texto.lower()) if texto else 0
        slug_no_path = slug in urlparse(link["href_absoluto"]).path.lower()
        if score_texto >= 80 or slug_no_path:
            candidatos.append({**link, "score_texto": score_texto, "slug_no_path": slug_no_path})

    internos = [c for c in candidatos if c["interno"]]
    dominio_base = _normalizar_dominio(url_base)
    externos_ignorados = []
    for c in candidatos:
        if c["interno"]:
            continue
        dominio = c.get("dominio", "")
        motivo = (
            f"domínio externo bloqueado ({dominio})"
            if dominio in _DOMINIOS_EXTERNOS_REJEITADOS
            else f"domínio diferente do avaliado ({dominio_base})"
        )
        externos_ignorados.append({"url": c["href_absoluto"], "motivo": motivo})

    if not internos:
        return {
            "url": None,
            "motivo": "Nenhuma URL interna encontrada para o módulo; apenas referências externas.",
            "externos_ignorados": externos_ignorados,
            "status": StatusValidacao.NAO_VERIFICADO.value,
        }

    internos_ordenados = sorted(
        internos,
        key=lambda c: (
            1 if c["slug_no_path"] else 0,
            1 if c["is_menu"] else 0,
            1 if (c["is_card"] or c["is_button"]) else 0,
            c["score_texto"],
            -c["ordem"],
        ),
        reverse=True,
    )
    escolhido = internos_ordenados[0]
    contexto = (
        "menu principal"
        if escolhido["is_menu"]
        else "card/botão interno"
        if (escolhido["is_card"] or escolhido["is_button"])
        else "link interno da página"
    )
    motivo = (
        f"URL interna priorizada ({contexto})"
        + (" com slug do módulo no caminho." if escolhido["slug_no_path"] else ".")
    )

    return {
        "url": escolhido["href_absoluto"],
        "motivo": motivo,
        "externos_ignorados": externos_ignorados,
        "status": StatusValidacao.CONFORME.value,
    }


def _encontrar_url_botao(
    html: str, url_base: str, modulo: str, texto_botao: str
) -> dict[str, Any]:
    """Seleciona a URL principal do módulo com prioridade para links internos."""
    return selecionar_url_principal_modulo(html, url_base, modulo, texto_botao)


def auditar_orgao(
    url: str,
    nome_orgao: str,
    ano_referencia: int,
    modulos_ativos: list[str],
    usar_playwright: bool = False,
    callback_progresso=None,
    verificar_links: bool = True,
    timeout_pagina: int = 15,
    max_paginas: int = 20,
) -> dict[str, Any]:
    """Executa a auditoria completa de um órgão.

    Retorna dict com:
      - nome_orgao, url, ano_referencia
      - resultados: dict[modulo -> list[ResultadoCriterio]]
      - pontuacoes: dict[modulo -> float]
      - pontuacao_geral: float
      - erros: list[str]
      - urls_visitadas: list[str]
      - metodos_coleta: dict[url -> str]
      - modulos_ativos: list[str]
    """
    erros: list[str] = []
    resultados_por_modulo: dict[str, list[ResultadoCriterio]] = {}
    urls_visitadas: list[str] = [url]
    metodos_coleta: dict[str, str] = {}
    selecao_urls_modulos: dict[str, dict[str, Any]] = {}
    subpaginas_visitadas: list[dict[str, str]] = []
    subpaginas_esperadas_nao_encontradas: list[dict[str, str]] = []
    evidencias_por_url: dict[str, list[str]] = defaultdict(list)

    def _progresso(msg: str):
        if callback_progresso:
            callback_progresso(msg)

    def _buscar_e_rastrear(target_url: str) -> tuple[str | None, str | None]:
        """Busca HTML rastreando URL e método de coleta usados."""
        if target_url not in urls_visitadas:
            urls_visitadas.append(target_url)

        html, erro = buscar_html(target_url)
        if html:
            if not usar_playwright or _html_suficiente(html):
                metodos_coleta[target_url] = "requests"
                return html, None
            metodos_coleta[target_url] = "requests (conteúdo insuficiente)"
        if usar_playwright:
            html_pw, erro_pw = buscar_html_dinamico(target_url)
            if html_pw:
                metodos_coleta[target_url] = "Playwright"
                return html_pw, None

            if erro_pw and "contexto Playwright fechado" in erro_pw:
                html_retry, erro_retry = buscar_html(target_url)
                if html_retry:
                    metodos_coleta[target_url] = "requests (fallback pós-falha Playwright)"
                    return html_retry, None
                return None, erro_retry or erro_pw
            return None, erro_pw

        html_pw, erro_pw = buscar_html_dinamico(target_url)
        if html_pw:
            metodos_coleta[target_url] = "Playwright (fallback automático)"
            return html_pw, None
        if erro_pw and "contexto Playwright fechado" in erro_pw:
            html_retry, erro_retry = buscar_html(target_url)
            if html_retry:
                metodos_coleta[target_url] = "requests (retry pós-falha Playwright)"
                return html_retry, None
            return None, erro_retry or erro_pw
        metodos_coleta[target_url] = "Playwright (fallback automático)"
        return None, erro_pw

    _progresso(f"Acessando página inicial: {url}")

    html_inicial, erro_inicial = _buscar_e_rastrear(url)

    if not html_inicial:
        erros.append(f"Falha ao acessar página inicial: {erro_inicial}")
        return {
            "nome_orgao": nome_orgao,
            "url": url,
            "ano_referencia": ano_referencia,
            "resultados": {},
            "pontuacoes": {},
            "pontuacao_geral": 0.0,
            "erros": erros,
            "urls_visitadas": urls_visitadas,
            "metodos_coleta": metodos_coleta,
            "modulos_ativos": modulos_ativos,
            "selecao_urls_modulos": selecao_urls_modulos,
            "subpaginas_visitadas": subpaginas_visitadas,
            "subpaginas_esperadas_nao_encontradas": subpaginas_esperadas_nao_encontradas,
            "evidencias_por_url": dict(evidencias_por_url),
        }

    MAPA_REGRAS = {
        "acesso_informacao": "acesso_informacao.yaml",
        "participacao_social": "participacao_social.yaml",
        "quadro_servicos": "quadro_servicos.yaml",
    }

    for modulo in modulos_ativos:
        if modulo not in MAPA_REGRAS:
            continue

        _progresso(f"Validando módulo: {modulo}")
        regra = _carregar_regra(MAPA_REGRAS[modulo])
        resultados_modulo: list[ResultadoCriterio] = []

        # 1. Validar botão na página inicial
        botoes_config = regra.get("pagina_inicial", {}).get("botoes_obrigatorios", [])
        if botoes_config:
            res_botoes = validar_botoes(html_inicial, url, botoes_config)
            for r in res_botoes:
                r.modulo = modulo
            resultados_modulo.extend(res_botoes)

        # 2. Acessar a página do módulo
        texto_botao = botoes_config[0]["texto"] if botoes_config else regra.get("nome", modulo)
        selecao_url = _encontrar_url_botao(html_inicial, url, modulo, texto_botao)
        url_pagina = selecao_url.get("url")
        selecao_urls_modulos[modulo] = {
            "modulo": modulo,
            "nome": _MODULOS_NOMES.get(modulo, modulo),
            "url_principal": url_pagina,
            "motivo": selecao_url.get("motivo", ""),
            "externos_ignorados": selecao_url.get("externos_ignorados", []),
            "status": selecao_url.get("status", StatusValidacao.NAO_VERIFICADO.value),
        }

        html_pagina = None
        if url_pagina:
            _progresso(f"Acessando: {url_pagina}")
            html_pagina, erro_pg = _buscar_e_rastrear(url_pagina)
            if erro_pg:
                erros.append(f"[{modulo}] Falha ao acessar {url_pagina}: {erro_pg}")

        if html_pagina:
            paginas_validacao = [{"url": url_pagina, "html": html_pagina}]

            if modulo == "acesso_informacao":
                subpaginas_cfg = regra.get("subpaginas_obrigatorias_institucional", [])
                descoberta = _descobrir_subpaginas_obrigatorias(
                    html_pagina,
                    url_pagina,
                    subpaginas_cfg,
                )
                for faltante in descoberta["nao_encontrados"]:
                    subpaginas_esperadas_nao_encontradas.append(
                        {"modulo": modulo, "nome": faltante["nome"]}
                    )

                for subpagina in descoberta["encontrados"]:
                    url_sub = subpagina["url"]
                    html_sub, erro_sub = _buscar_e_rastrear(url_sub)
                    if html_sub:
                        paginas_validacao.append({"url": url_sub, "html": html_sub})
                        subpaginas_visitadas.append(
                            {
                                "modulo": modulo,
                                "nome": subpagina["nome"],
                                "url": url_sub,
                                "status": StatusValidacao.CONFORME.value,
                                "evidencia": "Subpágina obrigatória acessada com sucesso.",
                            }
                        )
                    else:
                        msg_falha = "Subpágina não acessível no momento da avaliação"
                        subpaginas_visitadas.append(
                            {
                                "modulo": modulo,
                                "nome": subpagina["nome"],
                                "url": url_sub,
                                "status": StatusValidacao.NAO_VERIFICADO.value,
                                "evidencia": msg_falha,
                            }
                        )
                        resultados_modulo.append(
                            ResultadoCriterio(
                                criterio_id=(
                                    "subpagina_obrigatoria_"
                                    f"{subpagina['nome'].lower().replace(' ', '_')[:30]}"
                                ),
                                descricao=f'Subpágina obrigatória: "{subpagina["nome"]}"',
                                status=StatusValidacao.NAO_VERIFICADO,
                                evidencia=msg_falha,
                                url=url_sub,
                                modulo=modulo,
                            )
                        )
                        if erro_sub:
                            erros.append(f"[{modulo}] Falha ao acessar subpágina {url_sub}: {erro_sub}")

            # 3. Validar seções obrigatórias
            secoes = regra.get("pagina_principal", {}).get("secoes_obrigatorias", [])
            if secoes:
                res_secoes = _validar_secoes_em_paginas(
                    paginas_validacao,
                    secoes,
                    modulo=modulo,
                )
                resultados_modulo.extend(res_secoes)

            # 4. Validar data de atualização
            validacoes = regra.get("validacoes_gerais", regra.get("validacoes", {}))
            if validacoes.get("exigir_data_atualizacao"):
                r_data = validar_data_atualizacao(html_pagina, url_pagina, modulo=modulo)
                resultados_modulo.append(r_data)

            # 5. Validar formatos de arquivo
            if validacoes.get("exigir_formato_aberto_downloads"):
                r_formato = validar_formatos_arquivos(html_pagina, url_pagina, modulo=modulo)
                resultados_modulo.append(r_formato)

            # 6. Validar links quebrados
            if verificar_links and validacoes.get("verificar_links_quebrados"):
                r_links = validar_links_quebrados(
                    html_pagina, url_pagina, modulo=modulo, timeout=timeout_pagina
                )
                resultados_modulo.append(r_links)
            elif not verificar_links and validacoes.get("verificar_links_quebrados"):
                resultados_modulo.append(
                    ResultadoCriterio(
                        criterio_id="links_quebrados",
                        descricao="Ausência de links quebrados na página",
                        status=StatusValidacao.NAO_VERIFICADO,
                        evidencia="Verificação de links desativada pelo usuário.",
                        url=url_pagina or url,
                        modulo=modulo,
                    )
                )

            # 7. Validar legislação oficial
            dominios_oficiais = validacoes.get("dominio_legislacao_oficial")
            if dominios_oficiais:
                r_leg = validar_legislacao_oficial(
                    html_pagina, url_pagina, dominios_oficiais=dominios_oficiais, modulo=modulo
                )
                resultados_modulo.append(r_leg)

            # 8. Validar textos padrão obrigatórios
            textos_padrao = validacoes.get("textos_padrao", [])
            if textos_padrao:
                res_textos = validar_texto_padrao(
                    html_pagina, url_pagina, textos_padrao, modulo=modulo
                )
                resultados_modulo.extend(res_textos)
        else:
            resultados_modulo.append(
                ResultadoCriterio(
                    criterio_id=f"{modulo}_pagina_inacessivel",
                    descricao=f"Página do módulo {regra.get('nome', modulo)} acessível",
                    status=StatusValidacao.NAO_VERIFICADO if not url_pagina else StatusValidacao.NAO_CONFORME,
                    evidencia=(
                        "Página principal do módulo não localizada no domínio avaliado; "
                        "foram encontrados apenas links externos de referência."
                        if not url_pagina
                        else "Não foi possível acessar a página do módulo."
                    ),
                    url=url_pagina or url,
                    modulo=modulo,
                    )
                )

        resultados_por_modulo[modulo] = resultados_modulo
        for resultado in resultados_modulo:
            evidencias_por_url[resultado.url].append(
                f"[{resultado.modulo}] {resultado.descricao}: {resultado.status.value}"
            )

    # Calcular pontuações
    pontuacoes = {
        mod: calcular_pontuacao_modulo(res)
        for mod, res in resultados_por_modulo.items()
    }
    todos_resultados = [r for res in resultados_por_modulo.values() for r in res]
    pontuacao_geral = calcular_pontuacao_modulo(todos_resultados)

    return {
        "nome_orgao": nome_orgao,
        "url": url,
        "ano_referencia": ano_referencia,
        "resultados": resultados_por_modulo,
        "pontuacoes": pontuacoes,
        "pontuacao_geral": pontuacao_geral,
        "erros": erros,
        "urls_visitadas": urls_visitadas,
        "metodos_coleta": metodos_coleta,
        "modulos_ativos": modulos_ativos,
        "selecao_urls_modulos": selecao_urls_modulos,
        "subpaginas_visitadas": subpaginas_visitadas,
        "subpaginas_esperadas_nao_encontradas": subpaginas_esperadas_nao_encontradas,
        "evidencias_por_url": dict(evidencias_por_url),
    }


def construir_dataframe(auditoria: dict) -> pd.DataFrame:
    """Constrói DataFrame pandas com todos os critérios avaliados."""
    linhas = []
    for modulo, resultados in auditoria["resultados"].items():
        for r in resultados:
            linha = r.to_dict()
            linha["orgao"] = auditoria["nome_orgao"]
            linha["url_orgao"] = auditoria["url"]
            linha["ano_referencia"] = auditoria["ano_referencia"]
            linhas.append(linha)
    if not linhas:
        return pd.DataFrame()
    return pd.DataFrame(linhas)


def construir_dataframe_lote(auditorias: list[dict]) -> pd.DataFrame:
    """Constrói DataFrame unificado para múltiplos órgãos."""
    frames = [construir_dataframe(a) for a in auditorias]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
