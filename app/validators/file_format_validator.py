"""Verifica se arquivos para download possuem versão em formato aberto."""

from __future__ import annotations

from app.config import FORMATOS_ABERTOS
from app.crawler.parser import extrair_arquivos_download
from app.validators.base import ResultadoCriterio, StatusValidacao


def validar_formatos_arquivos(
    html: str, url: str, modulo: str = ""
) -> ResultadoCriterio:
    """Verifica se há arquivos em formato aberto disponíveis para download.

    Retorna CONFORME se houver ao menos um formato aberto,
    PARCIAL se só houver PDF,
    NAO_CONFORME se não houver arquivos,
    NAO_APLICAVEL se não houver arquivos de nenhum tipo.
    """
    arquivos = extrair_arquivos_download(html, url)

    if not arquivos:
        return ResultadoCriterio(
            criterio_id="formato_aberto_downloads",
            descricao="Arquivos para download possuem versão em formato aberto",
            status=StatusValidacao.NAO_APLICAVEL,
            evidencia="Nenhum arquivo para download encontrado na página.",
            url=url,
            modulo=modulo,
        )

    extensoes_encontradas = {a["extensao"] for a in arquivos}
    tem_formato_aberto = bool(extensoes_encontradas & FORMATOS_ABERTOS)
    tem_so_pdf = extensoes_encontradas == {".pdf"}

    formatos_str = ", ".join(sorted(extensoes_encontradas))

    if tem_formato_aberto:
        return ResultadoCriterio(
            criterio_id="formato_aberto_downloads",
            descricao="Arquivos para download possuem versão em formato aberto",
            status=StatusValidacao.CONFORME,
            evidencia=f"Formatos encontrados: {formatos_str}. Formato aberto presente.",
            url=url,
            modulo=modulo,
            detalhes={"arquivos": [a["href_absoluto"] for a in arquivos[:10]]},
        )

    if tem_so_pdf:
        return ResultadoCriterio(
            criterio_id="formato_aberto_downloads",
            descricao="Arquivos para download possuem versão em formato aberto",
            status=StatusValidacao.NAO_CONFORME,
            evidencia=(
                f"Apenas arquivos PDF encontrados ({len(arquivos)} arquivos). "
                "O manual exige ao menos uma versão em formato aberto."
            ),
            url=url,
            modulo=modulo,
            detalhes={"arquivos": [a["href_absoluto"] for a in arquivos[:10]]},
        )

    return ResultadoCriterio(
        criterio_id="formato_aberto_downloads",
        descricao="Arquivos para download possuem versão em formato aberto",
        status=StatusValidacao.PARCIAL,
        evidencia=f"Formatos encontrados: {formatos_str}. Verificar se formato aberto está disponível.",
        url=url,
        modulo=modulo,
    )
