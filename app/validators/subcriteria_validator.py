"""Validador genérico de subcritérios de checklist."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from rapidfuzz import fuzz

from app.config import FORMATOS_ABERTOS
from app.crawler.parser import (
    extrair_arquivos_download,
    extrair_cards_navegacao,
    extrair_links,
    extrair_texto_visivel,
    extrair_titulos,
)
from app.validators.base import ResultadoCriterio, StatusValidacao
from app.validators.date_validator import validar_data_atualizacao

_LIMIAR_TEXTO = 82
_LIMIAR_TITULO = 85
_LIMIAR_LINK = 80


def _normalizar(texto: str) -> str:
    texto_nfkd = unicodedata.normalize("NFKD", texto or "")
    sem_acentos = "".join(ch for ch in texto_nfkd if not unicodedata.combining(ch))
    return " ".join(sem_acentos.lower().replace("-", " ").replace("_", " ").split())


def _slug(texto: str) -> str:
    return (
        _normalizar(texto)
        .replace(" ", "_")
        .replace("/", "_")
        .replace("__", "_")
        .strip("_")
    )


def _score_match(alvos: list[str], valor: str) -> int:
    valor_norm = _normalizar(valor)
    melhor = 0
    for alvo in alvos:
        alvo_norm = _normalizar(alvo)
        if not alvo_norm:
            continue
        if alvo_norm in valor_norm or valor_norm in alvo_norm:
            return 100
        melhor = max(melhor, int(fuzz.partial_ratio(alvo_norm, valor_norm)))
    return melhor


def _buscar_termos_paginas(
    paginas: list[dict[str, Any]],
    termos: list[str],
) -> dict[str, Any]:
    melhor: dict[str, Any] = {"encontrado": False, "score": 0}
    for idx, pagina in enumerate(paginas):
        url = pagina["url"]
        titulos = pagina["titulos"]
        cards = pagina["cards"]
        texto = pagina["texto"]
        origem_subpagina = idx > 0

        for titulo in titulos:
            score = _score_match(termos, titulo["texto"])
            if score >= _LIMIAR_TITULO and score >= melhor["score"]:
                melhor = {
                    "encontrado": True,
                    "url": url,
                    "score": score,
                    "tipo_evidencia": "seção encontrada como título",
                    "evidencia": f'Termo encontrado como título "{titulo["texto"]}".',
                }

        for card in cards:
            texto_card = " ".join(
                parte
                for parte in (
                    card.get("texto_principal", ""),
                    card.get("titulo", ""),
                    card.get("descricao", ""),
                    card.get("texto", ""),
                )
                if parte
            )
            score = _score_match(termos, texto_card)
            if score >= _LIMIAR_TITULO and score >= melhor["score"]:
                melhor = {
                    "encontrado": True,
                    "url": url,
                    "score": score,
                    "tipo_evidencia": "seção encontrada como card",
                    "evidencia": (
                        f'Termo encontrado em card/botão "{card.get("texto_principal", "")}".'
                    ),
                }

        score_texto = _score_match(termos, texto)
        if score_texto >= _LIMIAR_TEXTO and score_texto >= melhor["score"]:
            melhor = {
                "encontrado": True,
                "url": url,
                "score": score_texto,
                "tipo_evidencia": (
                    "seção encontrada em subpágina" if origem_subpagina else "texto obrigatório parcialmente encontrado"
                ),
                "evidencia": "Texto obrigatório encontrado no conteúdo da página.",
            }

    return melhor


def _buscar_links_esperados(
    paginas: list[dict[str, Any]],
    regras_links: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    resultados: list[dict[str, Any]] = []
    for regra in regras_links:
        nome = regra.get("nome", "link esperado")
        termos_texto = regra.get("termos_texto", [])
        termos_url = regra.get("termos_url", [])
        encontrado = None
        for pagina in paginas:
            for link in pagina["links"]:
                score_texto = _score_match(termos_texto, link["texto"]) if termos_texto else 100
                score_url = _score_match(termos_url, link["href_absoluto"]) if termos_url else 100
                if score_texto >= _LIMIAR_LINK and score_url >= _LIMIAR_LINK:
                    encontrado = {
                        "ok": True,
                        "nome": nome,
                        "url": pagina["url"],
                        "evidencia": f'Link esperado encontrado: "{link["texto"]}" → {link["href_absoluto"]}',
                        "tipo_evidencia": "seção encontrada em subpágina"
                        if pagina is not paginas[0]
                        else "seção encontrada como título",
                    }
                    break
            if encontrado:
                break
        if not encontrado:
            encontrado = {
                "ok": False,
                "nome": nome,
                "evidencia": f'Link esperado ausente: "{nome}".',
                "tipo_evidencia": "texto obrigatório ausente",
            }
        resultados.append(encontrado)
    return resultados


def _status_por_score_checklist(score: int) -> StatusValidacao:
    if score >= 2:
        return StatusValidacao.CONFORME
    if score == 1:
        return StatusValidacao.PARCIAL
    return StatusValidacao.NAO_CONFORME


def validar_subcriterios_paginas(
    paginas: list[dict[str, str]],
    subcriterios: list[dict[str, Any]],
    modulo: str = "",
) -> list[ResultadoCriterio]:
    """Valida subcritérios em página principal + subpáginas."""
    if not paginas:
        return []

    paginas_processadas: list[dict[str, Any]] = []
    for pagina in paginas:
        html = pagina["html"]
        url = pagina["url"]
        paginas_processadas.append(
            {
                "url": url,
                "texto": extrair_texto_visivel(html),
                "titulos": extrair_titulos(html),
                "cards": extrair_cards_navegacao(html, url),
                "links": extrair_links(html, url),
                "arquivos": extrair_arquivos_download(html, url),
                "html": html,
            }
        )

    resultados: list[ResultadoCriterio] = []
    texto_consolidado = " ".join(p["texto"] for p in paginas_processadas)
    arquivos_consolidados = [a for p in paginas_processadas for a in p["arquivos"]]
    exts_arquivos = {a["extensao"] for a in arquivos_consolidados}

    for sub in subcriterios:
        sub_id = sub.get("id", "")
        secao = sub.get("secao", "")
        descricao = sub.get("descricao", sub_id or secao or "Subcritério")
        criterio_id = f"subcriterio_{sub_id or _slug(descricao)[:50]}"
        itens = sub.get("textos_obrigatorios", [])
        grupos_alternativos = sub.get("grupos_alternativos", [])
        regras_links = sub.get("links_esperados", [])
        frases_negativas = sub.get("frases_negativas_validas", [])
        exigir_data = bool(sub.get("data_exigida"))
        heuristica_cfg = sub.get("heuristica_minima")
        exigir_formato_aberto = bool(sub.get("exigir_formato_aberto_quando_houver_download"))

        obrigatorios = 0
        atendidos = 0
        evidencias: list[str] = []
        url_evidencia = paginas_processadas[0]["url"]
        tipo_evidencia = "texto obrigatório ausente"
        heuristica_alerta = False
        frase_negativa_valida = False

        for item in itens:
            nome = item["nome"] if isinstance(item, dict) else str(item)
            termos = item.get("termos", [nome]) if isinstance(item, dict) else [nome]
            alternativas = item.get("alternativas", []) if isinstance(item, dict) else []
            obrigatorio = bool(item.get("obrigatorio", True)) if isinstance(item, dict) else True
            obrigatorios += 1 if obrigatorio else 0

            encontrado = _buscar_termos_paginas(paginas_processadas, termos + alternativas)
            if encontrado.get("encontrado"):
                atendidos += 1 if obrigatorio else 0
                evidencias.append(f'✅ {nome}: {encontrado["evidencia"]}')
                url_evidencia = encontrado.get("url", url_evidencia)
                tipo_evidencia = encontrado.get("tipo_evidencia", tipo_evidencia)
            else:
                evidencias.append(f'❌ {nome}: texto obrigatório ausente.')

        for grupo in grupos_alternativos:
            nome = grupo.get("nome", "Grupo alternativo")
            opcoes = grupo.get("opcoes", [])
            obrigatorios += 1
            encontrado = _buscar_termos_paginas(paginas_processadas, opcoes)
            if encontrado.get("encontrado"):
                atendidos += 1
                evidencias.append(f'✅ {nome}: alternativa encontrada ({encontrado["evidencia"]})')
                url_evidencia = encontrado.get("url", url_evidencia)
                tipo_evidencia = encontrado.get("tipo_evidencia", tipo_evidencia)
            else:
                evidencias.append(f'❌ {nome}: nenhuma alternativa encontrada.')

        if regras_links:
            links_resultado = _buscar_links_esperados(paginas_processadas, regras_links)
            obrigatorios += len(links_resultado)
            ok_links = [r for r in links_resultado if r["ok"]]
            atendidos += len(ok_links)
            evidencias.extend(("✅ " + r["evidencia"]) if r["ok"] else ("❌ " + r["evidencia"]) for r in links_resultado)
            if ok_links:
                url_evidencia = ok_links[0].get("url", url_evidencia)
                tipo_evidencia = ok_links[0].get("tipo_evidencia", tipo_evidencia)

        if exigir_data:
            obrigatorios += 1
            melhores_datas = []
            for pagina in paginas_processadas:
                r_data = validar_data_atualizacao(pagina["html"], pagina["url"], modulo=modulo)
                if r_data.status in (StatusValidacao.CONFORME, StatusValidacao.PARCIAL):
                    melhores_datas.append(r_data)
            if melhores_datas:
                atendidos += 1
                melhor_data = melhores_datas[0]
                evidencias.append(f'✅ Data de atualização: {melhor_data.evidencia}')
                url_evidencia = melhor_data.url or url_evidencia
            else:
                evidencias.append("❌ Data de atualização ausente ou inválida.")

        if exigir_formato_aberto:
            obrigatorios += 1
            if not arquivos_consolidados:
                evidencias.append("ℹ️ Sem arquivos para download no escopo do subcritério.")
            elif exts_arquivos & FORMATOS_ABERTOS:
                atendidos += 1
                evidencias.append(
                    f"✅ Formatos abertos encontrados: {', '.join(sorted(exts_arquivos & FORMATOS_ABERTOS))}."
                )
            else:
                evidencias.append(
                    f"❌ Sem formato aberto; extensões encontradas: {', '.join(sorted(exts_arquivos))}."
                )

        if heuristica_cfg:
            padrao = heuristica_cfg.get("regex", "")
            minimo = int(heuristica_cfg.get("minimo", 0))
            apenas_heuristica = bool(heuristica_cfg.get("apenas_heuristica", True))
            if padrao and minimo > 0:
                ocorrencias = len(re.findall(padrao, texto_consolidado, flags=re.IGNORECASE))
                if ocorrencias >= minimo:
                    evidencias.append(
                        f"✅ Heurística satisfeita: {ocorrencias} ocorrência(s) para mínimo de {minimo}."
                    )
                else:
                    msg_heur = (
                        f"Heurística abaixo do mínimo: {ocorrencias}/{minimo}. Exige revisão humana."
                    )
                    evidencias.append(f"⚠️ {msg_heur}")
                    heuristica_alerta = True
                    if not apenas_heuristica:
                        obrigatorios += 1

        if frases_negativas:
            frase_encontrada = _buscar_termos_paginas(paginas_processadas, frases_negativas)
            if frase_encontrada.get("encontrado"):
                frase_negativa_valida = True
                evidencias.append(
                    f'✅ Frase negativa válida detectada: {frase_encontrada.get("evidencia", "")}'
                )
                url_evidencia = frase_encontrada.get("url", url_evidencia)
                tipo_evidencia = "frase negativa válida"
                if sub.get("frase_negativa_satisfaz_subcriterio", True):
                    atendidos = max(atendidos, obrigatorios)

        if obrigatorios <= 0:
            status = StatusValidacao.NAO_APLICAVEL
            score_checklist = 2
        else:
            if atendidos >= obrigatorios:
                score_checklist = 2
            elif atendidos == 0:
                score_checklist = 2 if frase_negativa_valida else 0
            else:
                score_checklist = 1
            status = _status_por_score_checklist(score_checklist)
            if heuristica_alerta and status == StatusValidacao.CONFORME:
                status = StatusValidacao.PARCIAL
                score_checklist = 1

        resultados.append(
            ResultadoCriterio(
                criterio_id=criterio_id,
                descricao=f"Subcritério ({secao}): {descricao}" if secao else f"Subcritério: {descricao}",
                status=status,
                evidencia=" | ".join(evidencias),
                url=url_evidencia,
                modulo=modulo,
                detalhes={
                    "secao": secao,
                    "subcriterio": descricao,
                    "tipo_evidencia": tipo_evidencia,
                    "pontuacao_script": score_checklist,
                    "frase_negativa_valida": frase_negativa_valida,
                },
            )
        )

    return resultados
