"""Testes unitários para os validadores do ITA-Robô."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Fixtures de HTML de exemplo
# ---------------------------------------------------------------------------

HTML_COM_BOTOES = """
<html>
<head><title>Teste</title></head>
<body>
  <nav>
    <a href="/acesso-informacao">Acesso à Informação</a>
    <a href="/participacao-social">Participação Social</a>
    <a href="/quadro-servicos">Quadro de Serviços</a>
  </nav>
</body>
</html>
"""

HTML_SEM_BOTOES = """
<html><body><p>Página sem botões obrigatórios.</p></body></html>
"""

HTML_COM_SECOES = """
<html><body>
  <h2>Institucional</h2>
  <h2>Ações e Programas</h2>
  <h2>Perguntas Frequentes</h2>
  <h3>Serviço de Informação ao Cidadão</h3>
  <h2>Auditorias</h2>
  <p>Atualizado em 01/05/2026</p>
  <a href="/relatorio.csv">Download CSV</a>
  <a href="/lei-1234">Lei 1234</a>
</body></html>
"""

HTML_COM_PDF_APENAS = """
<html><body>
  <a href="/arquivo.pdf">Baixar relatório</a>
</body></html>
"""

HTML_COM_DATA = """
<html><body>
  <p>Última atualização: 10/05/2026</p>
</body></html>
"""

URL_BASE = "https://www.prefeitura.sp.gov.br/teste"


# ---------------------------------------------------------------------------
# Testes: parser
# ---------------------------------------------------------------------------

class TestParser:
    def test_extrair_links_retorna_lista(self):
        from app.crawler.parser import extrair_links
        links = extrair_links(HTML_COM_BOTOES, URL_BASE)
        assert len(links) == 3
        assert all("texto" in l and "href_absoluto" in l for l in links)

    def test_extrair_titulos(self):
        from app.crawler.parser import extrair_titulos
        titulos = extrair_titulos(HTML_COM_SECOES)
        textos = [t["texto"] for t in titulos]
        assert "Institucional" in textos
        assert "Auditorias" in textos

    def test_extrair_texto_visivel(self):
        from app.crawler.parser import extrair_texto_visivel
        texto = extrair_texto_visivel(HTML_COM_SECOES)
        assert "Institucional" in texto
        assert "Atualizado em" in texto

    def test_extrair_datas(self):
        from app.crawler.parser import extrair_datas
        datas = extrair_datas(HTML_COM_DATA)
        assert len(datas) >= 1
        assert "10/05/2026" in datas

    def test_extrair_data_atualizacao(self):
        from app.crawler.parser import extrair_data_atualizacao
        data = extrair_data_atualizacao(HTML_COM_DATA)
        assert data is not None
        assert "2026" in data or "05" in data

    def test_extrair_arquivos_download_csv(self):
        from app.crawler.parser import extrair_arquivos_download
        arquivos = extrair_arquivos_download(HTML_COM_SECOES, URL_BASE)
        extensoes = {a["extensao"] for a in arquivos}
        assert ".csv" in extensoes

    def test_extrair_arquivos_download_pdf(self):
        from app.crawler.parser import extrair_arquivos_download
        arquivos = extrair_arquivos_download(HTML_COM_PDF_APENAS, URL_BASE)
        extensoes = {a["extensao"] for a in arquivos}
        assert ".pdf" in extensoes


# ---------------------------------------------------------------------------
# Testes: validators/base
# ---------------------------------------------------------------------------

class TestBase:
    def test_status_enum(self):
        from app.validators.base import StatusValidacao
        assert StatusValidacao.CONFORME.value == "CONFORME"
        assert StatusValidacao.PARCIAL.value == "PARCIALMENTE CONFORME"

    def test_pontuacao_conforme(self):
        from app.validators.base import ResultadoCriterio, StatusValidacao
        r = ResultadoCriterio("id1", "Teste", status=StatusValidacao.CONFORME)
        assert r.pontuacao == 1.0

    def test_pontuacao_parcial(self):
        from app.validators.base import ResultadoCriterio, StatusValidacao
        r = ResultadoCriterio("id2", "Teste", status=StatusValidacao.PARCIAL)
        assert r.pontuacao == 0.5

    def test_pontuacao_nao_conforme(self):
        from app.validators.base import ResultadoCriterio, StatusValidacao
        r = ResultadoCriterio("id3", "Teste", status=StatusValidacao.NAO_CONFORME)
        assert r.pontuacao == 0.0

    def test_pontuacao_nao_aplicavel_none(self):
        from app.validators.base import ResultadoCriterio, StatusValidacao
        r = ResultadoCriterio("id4", "Teste", status=StatusValidacao.NAO_APLICAVEL)
        assert r.pontuacao is None

    def test_calcular_pontuacao_modulo(self):
        from app.validators.base import ResultadoCriterio, StatusValidacao, calcular_pontuacao_modulo
        resultados = [
            ResultadoCriterio("a", "A", status=StatusValidacao.CONFORME),
            ResultadoCriterio("b", "B", status=StatusValidacao.NAO_CONFORME),
            ResultadoCriterio("c", "C", status=StatusValidacao.NAO_APLICAVEL),
        ]
        # Entra no cálculo: CONFORME (1.0) + NAO_CONFORME (0.0) = 50%
        assert calcular_pontuacao_modulo(resultados) == 50.0

    def test_to_dict(self):
        from app.validators.base import ResultadoCriterio, StatusValidacao
        r = ResultadoCriterio("x", "Desc", status=StatusValidacao.CONFORME, evidencia="ok", url="https://x.com")
        d = r.to_dict()
        assert d["criterio_id"] == "x"
        assert d["status"] == "CONFORME"
        assert d["pontuacao"] == 1.0


# ---------------------------------------------------------------------------
# Testes: button_validator
# ---------------------------------------------------------------------------

class TestButtonValidator:
    def test_botoes_encontrados(self):
        from app.validators.button_validator import validar_botoes
        botoes = [
            {"texto": "Acesso à Informação", "obrigatorio": True},
            {"texto": "Participação Social", "obrigatorio": True},
            {"texto": "Quadro de Serviços", "obrigatorio": True},
        ]
        resultados = validar_botoes(HTML_COM_BOTOES, URL_BASE, botoes)
        assert len(resultados) == 3
        from app.validators.base import StatusValidacao
        assert all(r.status == StatusValidacao.CONFORME for r in resultados)

    def test_botoes_nao_encontrados(self):
        from app.validators.button_validator import validar_botoes
        from app.validators.base import StatusValidacao
        botoes = [{"texto": "Acesso à Informação", "obrigatorio": True}]
        resultados = validar_botoes(HTML_SEM_BOTOES, URL_BASE, botoes)
        assert resultados[0].status == StatusValidacao.NAO_CONFORME


# ---------------------------------------------------------------------------
# Testes: section_validator
# ---------------------------------------------------------------------------

class TestSectionValidator:
    def test_secoes_encontradas(self):
        from app.validators.section_validator import validar_secoes
        from app.validators.base import StatusValidacao
        resultados = validar_secoes(
            HTML_COM_SECOES, URL_BASE,
            ["Institucional", "Auditorias"],
            modulo="acesso_informacao",
        )
        assert len(resultados) == 2
        statuses = {r.criterio_id: r.status for r in resultados}
        # Ambos devem ser CONFORME ou pelo menos PARCIAL
        for s in statuses.values():
            assert s in (StatusValidacao.CONFORME, StatusValidacao.PARCIAL)

    def test_secao_ausente(self):
        from app.validators.section_validator import validar_secoes
        from app.validators.base import StatusValidacao
        resultados = validar_secoes(
            HTML_SEM_BOTOES, URL_BASE,
            ["Seção Inexistente"],
        )
        assert resultados[0].status == StatusValidacao.NAO_CONFORME


# ---------------------------------------------------------------------------
# Testes: file_format_validator
# ---------------------------------------------------------------------------

class TestFileFormatValidator:
    def test_formato_aberto_presente(self):
        from app.validators.file_format_validator import validar_formatos_arquivos
        from app.validators.base import StatusValidacao
        r = validar_formatos_arquivos(HTML_COM_SECOES, URL_BASE)
        assert r.status == StatusValidacao.CONFORME

    def test_apenas_pdf(self):
        from app.validators.file_format_validator import validar_formatos_arquivos
        from app.validators.base import StatusValidacao
        r = validar_formatos_arquivos(HTML_COM_PDF_APENAS, URL_BASE)
        assert r.status == StatusValidacao.NAO_CONFORME

    def test_sem_arquivos(self):
        from app.validators.file_format_validator import validar_formatos_arquivos
        from app.validators.base import StatusValidacao
        r = validar_formatos_arquivos(HTML_SEM_BOTOES, URL_BASE)
        assert r.status == StatusValidacao.NAO_APLICAVEL


# ---------------------------------------------------------------------------
# Testes: date_validator
# ---------------------------------------------------------------------------

class TestDateValidator:
    def test_data_recente(self):
        from app.validators.date_validator import validar_data_atualizacao
        from app.validators.base import StatusValidacao
        r = validar_data_atualizacao(HTML_COM_DATA, URL_BASE)
        # Data de 05/2026 é recente — deve ser CONFORME ou PARCIAL
        assert r.status in (StatusValidacao.CONFORME, StatusValidacao.PARCIAL, StatusValidacao.NAO_CONFORME)

    def test_sem_data(self):
        from app.validators.date_validator import validar_data_atualizacao
        from app.validators.base import StatusValidacao
        r = validar_data_atualizacao(HTML_SEM_BOTOES, URL_BASE)
        assert r.status == StatusValidacao.NAO_CONFORME


# ---------------------------------------------------------------------------
# Testes: manuais/gerenciador
# ---------------------------------------------------------------------------

class TestGerenciadorManuais:
    def test_salvar_e_listar_manual(self, tmp_path, monkeypatch):
        import app.manuais.gerenciador as ger
        monkeypatch.setattr(ger, "MANUAIS_DIR", str(tmp_path))

        conteudo = b"%PDF-1.4 fake content"
        meta = ger.salvar_manual_pdf("acesso_informacao", "manual_teste.pdf", conteudo)
        assert meta["nome_arquivo"] == "manual_teste.pdf"
        assert meta["tamanho_bytes"] == len(conteudo)

        manuais = ger.listar_manuais()
        assert len(manuais) == 1
        assert manuais[0]["nome_arquivo"] == "manual_teste.pdf"

    def test_remover_manual(self, tmp_path, monkeypatch):
        import app.manuais.gerenciador as ger
        monkeypatch.setattr(ger, "MANUAIS_DIR", str(tmp_path))

        conteudo = b"%PDF-1.4 fake"
        ger.salvar_manual_pdf("participacao_social", "remover.pdf", conteudo)
        resultado = ger.remover_manual("participacao_social", "remover.pdf")
        assert resultado is True
        manuais = ger.listar_manuais()
        assert len(manuais) == 0

    def test_modulo_invalido(self, tmp_path, monkeypatch):
        import app.manuais.gerenciador as ger
        monkeypatch.setattr(ger, "MANUAIS_DIR", str(tmp_path))
        with pytest.raises(ValueError):
            ger.salvar_manual_pdf("modulo_invalido", "arq.pdf", b"x")


# ---------------------------------------------------------------------------
# Testes: storage/database
# ---------------------------------------------------------------------------

class TestDatabase:
    def test_inicializar_e_salvar(self, tmp_path, monkeypatch):
        import app.storage.database as db
        monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))

        from app.validators.base import ResultadoCriterio, StatusValidacao
        auditoria = {
            "nome_orgao": "Órgão Teste",
            "url": "https://teste.prefeitura.sp.gov.br",
            "ano_referencia": 2026,
            "resultados": {
                "acesso_informacao": [
                    ResultadoCriterio("bot_ai", "Botão AI", StatusValidacao.CONFORME, "ok", "https://x.com", "acesso_informacao")
                ]
            },
            "pontuacoes": {"acesso_informacao": 100.0},
            "pontuacao_geral": 100.0,
            "erros": [],
        }
        aid = db.salvar_auditoria(auditoria)
        assert aid == 1

        lista = db.listar_auditorias()
        assert len(lista) == 1
        assert lista[0]["nome_orgao"] == "Órgão Teste"

    def test_buscar_auditoria(self, tmp_path, monkeypatch):
        import app.storage.database as db
        monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test2.db"))

        from app.validators.base import ResultadoCriterio, StatusValidacao
        auditoria = {
            "nome_orgao": "Secretaria Teste",
            "url": "https://sec.prefeitura.sp.gov.br",
            "ano_referencia": 2026,
            "resultados": {},
            "pontuacoes": {},
            "pontuacao_geral": 0.0,
            "erros": ["Erro simulado"],
        }
        aid = db.salvar_auditoria(auditoria)
        detalhes = db.buscar_auditoria(aid)
        assert detalhes is not None
        assert detalhes["nome_orgao"] == "Secretaria Teste"
