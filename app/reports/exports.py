"""Exporta relatórios em Excel e HTML."""

from __future__ import annotations

import io
import os
from datetime import datetime

import pandas as pd
from jinja2 import Environment, FileSystemLoader


def exportar_excel(df: pd.DataFrame, nome_orgao: str, ano: int) -> bytes:
    """Gera arquivo Excel em memória e retorna bytes."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultados")

        # Aba de resumo por módulo
        if "modulo" in df.columns and "pontuacao" in df.columns:
            resumo = (
                df[df["pontuacao"].notna()]
                .groupby("modulo")["pontuacao"]
                .agg(["mean", "count"])
                .reset_index()
            )
            resumo.columns = ["Módulo", "Pontuação Média", "Critérios Avaliados"]
            resumo["Pontuação Média (%)"] = (resumo["Pontuação Média"] * 100).round(1)
            resumo.to_excel(writer, index=False, sheet_name="Resumo por Módulo")

    return output.getvalue()


def exportar_html(
    df: pd.DataFrame,
    auditoria: dict,
    templates_dir: str | None = None,
) -> str:
    """Gera relatório HTML a partir do template Jinja2."""
    if templates_dir is None:
        templates_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "templates"
        )

    env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)
    template = env.get_template("relatorio.html")

    # Monta dados para o template
    pontuacoes_pct = {
        mod: f"{v:.1f}%" for mod, v in auditoria.get("pontuacoes", {}).items()
    }

    tabela_html = df.to_html(
        index=False,
        classes="tabela-resultados",
        border=0,
        escape=True,
    )

    return template.render(
        nome_orgao=auditoria.get("nome_orgao", ""),
        url=auditoria.get("url", ""),
        ano_referencia=auditoria.get("ano_referencia", ""),
        data_verificacao=datetime.now().strftime("%d/%m/%Y %H:%M"),
        pontuacao_geral=f"{auditoria.get('pontuacao_geral', 0):.1f}%",
        pontuacoes=pontuacoes_pct,
        erros=auditoria.get("erros", []),
        tabela_html=tabela_html,
        urls_visitadas=auditoria.get("urls_visitadas", []),
        metodos_coleta=auditoria.get("metodos_coleta", {}),
        modulos_avaliados=[
            m.replace("_", " ").title()
            for m in auditoria.get("modulos_ativos", [])
        ],
    )


def salvar_resultados(
    df: pd.DataFrame,
    auditoria: dict,
    diretorio_saida: str,
) -> dict[str, str]:
    """Salva Excel e HTML no diretório de saída.

    Retorna dict com caminhos dos arquivos gerados.
    """
    os.makedirs(diretorio_saida, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_base = (
        auditoria.get("nome_orgao", "orgao")
        .replace(" ", "_")
        .replace("/", "-")[:30]
    )
    arquivos: dict[str, str] = {}

    # Excel
    caminho_excel = os.path.join(diretorio_saida, f"relatorio_{nome_base}_{timestamp}.xlsx")
    with open(caminho_excel, "wb") as f:
        f.write(exportar_excel(df, auditoria.get("nome_orgao", ""), auditoria.get("ano_referencia", 0)))
    arquivos["excel"] = caminho_excel

    # HTML
    caminho_html = os.path.join(diretorio_saida, f"relatorio_{nome_base}_{timestamp}.html")
    with open(caminho_html, "w", encoding="utf-8") as f:
        f.write(exportar_html(df, auditoria))
    arquivos["html"] = caminho_html

    return arquivos
