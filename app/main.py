"""Interface principal Streamlit do ITA-Robô."""

from __future__ import annotations

import io
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import RESULTADOS_DIR
from app.manuais.gerenciador import (
    extrair_texto_pdf,
    listar_manuais,
    remover_manual,
    salvar_manual_pdf,
)
from app.reports.exports import exportar_excel, exportar_html
from app.reports.report_builder import auditar_orgao, construir_dataframe, construir_dataframe_lote
from app.storage.database import listar_auditorias, salvar_auditoria

# ---------------------------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="ITA-Robô — Verificador de Transparência Ativa",
    page_icon="🔍",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Proteção por senha (opcional via variável de ambiente ITA_ROBO_APP_PASSWORD)
# ---------------------------------------------------------------------------
_senha_configurada = os.environ.get("ITA_ROBO_APP_PASSWORD", "")
if _senha_configurada and not st.session_state.get("autenticado"):
    st.title("🔐 Acesso Restrito")
    st.markdown("Informe a senha de acesso para continuar.")
    senha_input = st.text_input("Senha", type="password", key="senha_input")
    if st.button("Entrar", type="primary"):
        if senha_input == _senha_configurada:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta. Tente novamente.")
    st.stop()

MODULOS_NOMES = {
    "acesso_informacao": "Acesso à Informação",
    "participacao_social": "Participação Social",
    "quadro_servicos": "Quadro de Serviços",
}

# ---------------------------------------------------------------------------
# Barra lateral — navegação
# ---------------------------------------------------------------------------
st.sidebar.title("🔍 ITA-Robô")
st.sidebar.caption("Verificador Automatizado do Indicador de Transparência Ativa")

pagina = st.sidebar.radio(
    "Navegar para",
    ["Avaliação Individual", "Avaliação em Lote", "Histórico", "Manuais PDF"],
)

# ---------------------------------------------------------------------------
# Página: Avaliação Individual
# ---------------------------------------------------------------------------
if pagina == "Avaliação Individual":
    st.title("Avaliação Individual de Órgão")
    st.markdown(
        "Informe os dados do órgão a ser avaliado. "
        "O robô acessará a página inicial, localizará os botões obrigatórios e verificará as seções exigidas pelos manuais."
    )

    with st.form("form_avaliacao"):
        col1, col2 = st.columns(2)
        with col1:
            nome_orgao = st.text_input("Nome do órgão", placeholder="Ex.: Secretaria de Inovação")
            url = st.text_input("URL do site", placeholder="https://www.prefeitura.sp.gov.br/...")
        with col2:
            ano = st.number_input(
                "Ano de referência",
                min_value=2020,
                max_value=datetime.now().year + 1,
                value=datetime.now().year,
            )
            usar_playwright = st.checkbox(
                "Usar Playwright (sites com JavaScript)",
                help="Marque se o site usa carregamento dinâmico (ex.: Liferay).",
            )

        st.markdown("**Módulos a verificar:**")
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            verificar_ai = st.checkbox("Acesso à Informação", value=True)
        with col_m2:
            verificar_ps = st.checkbox("Participação Social", value=True)
        with col_m3:
            verificar_qs = st.checkbox("Quadro de Serviços", value=True)

        st.markdown("**Configurações de coleta:**")
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            verificar_links = st.checkbox(
                "Verificar links quebrados",
                value=True,
                help="Desmarque para acelerar a avaliação. Links não serão verificados.",
            )
        with col_c2:
            timeout_pagina = st.slider(
                "Timeout por página (s)",
                min_value=5,
                max_value=60,
                value=15,
                help="Tempo máximo de espera por página e por link verificado.",
            )
        with col_c3:
            max_paginas = st.number_input(
                "Máximo de páginas",
                min_value=1,
                max_value=100,
                value=20,
                help="Limite de páginas a visitar por módulo (aplicável a crawling futuro).",
            )

        executar = st.form_submit_button("▶ Executar Avaliação", type="primary")

    if executar:
        if not url or not nome_orgao:
            st.error("Informe o nome do órgão e a URL antes de executar.")
        else:
            modulos_ativos = []
            if verificar_ai:
                modulos_ativos.append("acesso_informacao")
            if verificar_ps:
                modulos_ativos.append("participacao_social")
            if verificar_qs:
                modulos_ativos.append("quadro_servicos")

            if not modulos_ativos:
                st.warning("Selecione ao menos um módulo.")
            else:
                with st.spinner("Avaliando... aguarde."):
                    barra = st.progress(0)
                    log_container = st.empty()
                    mensagens: list[str] = []

                    def progresso(msg: str):
                        mensagens.append(msg)
                        log_container.info("\n".join(mensagens[-5:]))
                        barra.progress(min(len(mensagens) / (len(modulos_ativos) * 5 + 2), 0.95))

                    auditoria = auditar_orgao(
                        url=url,
                        nome_orgao=nome_orgao,
                        ano_referencia=int(ano),
                        modulos_ativos=modulos_ativos,
                        usar_playwright=usar_playwright,
                        callback_progresso=progresso,
                        verificar_links=verificar_links,
                        timeout_pagina=int(timeout_pagina),
                        max_paginas=int(max_paginas),
                    )
                    barra.progress(1.0)

                salvar_auditoria(auditoria)
                df = construir_dataframe(auditoria)

                # Exibe erros
                if auditoria["erros"]:
                    with st.expander("⚠️ Erros durante a avaliação", expanded=False):
                        for erro in auditoria["erros"]:
                            st.warning(erro)

                # Pontuações
                st.subheader("Resultado da Avaliação")
                cols = st.columns(len(auditoria["pontuacoes"]) + 1)
                with cols[0]:
                    st.metric("Pontuação Geral", f"{auditoria['pontuacao_geral']:.1f}%")
                for i, (mod, nota) in enumerate(auditoria["pontuacoes"].items(), start=1):
                    with cols[i]:
                        st.metric(MODULOS_NOMES.get(mod, mod), f"{nota:.1f}%")

                # URLs visitadas
                urls_vis = auditoria.get("urls_visitadas", [])
                metodos = auditoria.get("metodos_coleta", {})
                if urls_vis:
                    with st.expander("🔗 URLs visitadas e método de coleta", expanded=False):
                        dados_urls = [
                            {"URL": u, "Método de Coleta": metodos.get(u, "—")}
                            for u in urls_vis
                        ]
                        st.table(dados_urls)

                # Tabela de critérios
                if not df.empty:
                    st.subheader("Detalhamento por Critério")
                    st.dataframe(
                        df[["modulo", "descricao", "status", "pontuacao", "evidencia", "url"]],
                        use_container_width=True,
                    )

                # Downloads
                st.subheader("Baixar Relatório")
                col_dl1, col_dl2 = st.columns(2)

                if not df.empty:
                    excel_bytes = exportar_excel(df, nome_orgao, int(ano))
                    html_str = exportar_html(df, auditoria)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    nome_base = nome_orgao.replace(" ", "_")[:20]

                    with col_dl1:
                        st.download_button(
                            "📥 Baixar Excel",
                            data=excel_bytes,
                            file_name=f"relatorio_{nome_base}_{ts}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    with col_dl2:
                        st.download_button(
                            "📄 Baixar HTML",
                            data=html_str.encode("utf-8"),
                            file_name=f"relatorio_{nome_base}_{ts}.html",
                            mime="text/html",
                        )

# ---------------------------------------------------------------------------
# Página: Avaliação em Lote
# ---------------------------------------------------------------------------
elif pagina == "Avaliação em Lote":
    st.title("Avaliação em Lote")
    st.markdown(
        "Faça upload de um arquivo CSV com as colunas `orgao` e `url` para avaliar múltiplos órgãos."
    )

    arquivo_csv = st.file_uploader("Arquivo CSV (orgao, url)", type=["csv"])
    exemplo_csv = "orgao,url\nSecretaria de Exemplo,https://www.prefeitura.sp.gov.br/exemplo\n"
    st.download_button(
        "📥 Baixar exemplo CSV",
        data=exemplo_csv,
        file_name="orgaos_exemplo.csv",
        mime="text/csv",
    )

    if arquivo_csv:
        try:
            df_orgaos = pd.read_csv(arquivo_csv)
            st.dataframe(df_orgaos, use_container_width=True)

            col_b1, col_b2 = st.columns(2)
            with col_b1:
                ano_lote = st.number_input(
                    "Ano de referência",
                    min_value=2020,
                    max_value=datetime.now().year + 1,
                    value=datetime.now().year,
                    key="ano_lote",
                )
            with col_b2:
                usar_playwright_lote = st.checkbox(
                    "Usar Playwright", key="playwright_lote"
                )

            if st.button("▶ Executar Avaliação em Lote", type="primary"):
                auditorias: list[dict] = []
                barra_lote = st.progress(0)
                total = len(df_orgaos)

                for i, linha in df_orgaos.iterrows():
                    nome = linha.get("orgao", f"Órgão {i+1}")
                    url_l = linha.get("url", "")
                    st.info(f"Avaliando ({i+1}/{total}): {nome}")

                    auditoria = auditar_orgao(
                        url=url_l,
                        nome_orgao=nome,
                        ano_referencia=int(ano_lote),
                        modulos_ativos=["acesso_informacao", "participacao_social", "quadro_servicos"],
                        usar_playwright=usar_playwright_lote,
                    )
                    salvar_auditoria(auditoria)
                    auditorias.append(auditoria)
                    barra_lote.progress((i + 1) / total)

                df_geral = construir_dataframe_lote(auditorias)

                st.success(f"✅ Avaliação concluída. {total} órgão(s) auditado(s).")

                # Resumo geral
                resumo_dados = [
                    {"Órgão": a["nome_orgao"], "URL": a["url"], "Pontuação Geral (%)": a["pontuacao_geral"]}
                    | {MODULOS_NOMES.get(m, m): v for m, v in a["pontuacoes"].items()}
                    for a in auditorias
                ]
                st.subheader("Resumo Geral")
                st.dataframe(pd.DataFrame(resumo_dados), use_container_width=True)

                if not df_geral.empty:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    excel_geral = exportar_excel(df_geral, "Lote", int(ano_lote))
                    st.download_button(
                        "📥 Baixar relatório geral (Excel)",
                        data=excel_geral,
                        file_name=f"relatorio_geral_{ts}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
        except Exception as exc:
            st.error(f"Erro ao processar CSV: {exc}")

# ---------------------------------------------------------------------------
# Página: Histórico
# ---------------------------------------------------------------------------
elif pagina == "Histórico":
    st.title("Histórico de Auditorias")
    auditorias_hist = listar_auditorias()
    if not auditorias_hist:
        st.info("Nenhuma auditoria registrada ainda.")
    else:
        df_hist = pd.DataFrame(auditorias_hist)[
            ["id", "nome_orgao", "url", "ano_referencia", "data_auditoria", "pontuacao_geral"]
        ]
        df_hist.columns = ["ID", "Órgão", "URL", "Ano", "Data", "Pontuação Geral (%)"]
        st.dataframe(df_hist, use_container_width=True)

# ---------------------------------------------------------------------------
# Página: Manuais PDF
# ---------------------------------------------------------------------------
elif pagina == "Manuais PDF":
    st.title("Gestão de Manuais em PDF")
    st.markdown(
        """
        Faça upload dos manuais vigentes (ou atualizados) em PDF.
        O sistema armazena os arquivos e permite extrair o texto para consulta.

        > **Como funciona:** os manuais ficam organizados por módulo e podem ser
        consultados diretamente pela equipe. Para versões futuras, o conteúdo extraído
        poderá alimentar automaticamente as regras de validação.
        """
    )

    st.subheader("📤 Enviar Novo Manual")
    with st.form("form_upload_manual"):
        modulo_upload = st.selectbox(
            "Módulo",
            options=list(MODULOS_NOMES.keys()),
            format_func=lambda x: MODULOS_NOMES[x],
        )
        arquivo_pdf = st.file_uploader("Arquivo PDF do manual", type=["pdf"])
        enviar = st.form_submit_button("Enviar Manual", type="primary")

    if enviar:
        if arquivo_pdf is None:
            st.error("Selecione um arquivo PDF.")
        else:
            conteudo = arquivo_pdf.read()
            meta = salvar_manual_pdf(modulo_upload, arquivo_pdf.name, conteudo)
            st.success(
                f"✅ Manual enviado com sucesso! "
                f"Arquivo: **{meta['nome_arquivo']}** — "
                f"{meta['tamanho_bytes'] / 1024:.1f} KB"
            )

    st.divider()
    st.subheader("📚 Manuais Disponíveis")

    manuais_disponiveis = listar_manuais()
    if not manuais_disponiveis:
        st.info("Nenhum manual PDF enviado ainda.")
    else:
        for manual in manuais_disponiveis:
            with st.expander(
                f"📄 {manual['nome_arquivo']} — {MODULOS_NOMES.get(manual['modulo'], manual['modulo'])}"
            ):
                col_info, col_acoes = st.columns([3, 1])
                with col_info:
                    st.markdown(f"**Módulo:** {MODULOS_NOMES.get(manual['modulo'], manual['modulo'])}")
                    st.markdown(f"**Tamanho:** {manual['tamanho_bytes'] / 1024:.1f} KB")
                    st.markdown(f"**Última modificação:** {manual['data_modificacao'][:19].replace('T', ' ')}")

                    if st.button(f"👁 Extrair e visualizar texto", key=f"ver_{manual['caminho']}"):
                        with st.spinner("Extraindo texto do PDF..."):
                            texto = extrair_texto_pdf(manual["caminho"])
                        st.text_area("Texto extraído", value=texto[:3000] + ("..." if len(texto) > 3000 else ""), height=300)

                with col_acoes:
                    # Download do PDF
                    with open(manual["caminho"], "rb") as f:
                        st.download_button(
                            "📥 Baixar",
                            data=f.read(),
                            file_name=manual["nome_arquivo"],
                            mime="application/pdf",
                            key=f"dl_{manual['caminho']}",
                        )
                    if st.button("🗑 Remover", key=f"rm_{manual['caminho']}"):
                        remover_manual(manual["modulo"], manual["nome_arquivo"])
                        st.warning(f"Manual **{manual['nome_arquivo']}** removido.")
                        st.rerun()
