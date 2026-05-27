"""Gerenciamento de manuais em PDF — upload, armazenamento e extração de texto."""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime
from typing import Any

from app.config import MANUAIS_DIR


MODULOS_VALIDOS = {"acesso_informacao", "participacao_social", "quadro_servicos"}


def _caminho_manual(modulo: str, nome_arquivo: str) -> str:
    return os.path.join(MANUAIS_DIR, modulo, nome_arquivo)


def salvar_manual_pdf(
    modulo: str, nome_arquivo: str, conteudo: bytes
) -> dict[str, Any]:
    """Salva o PDF do manual no diretório de manuais.

    Retorna metadados do arquivo salvo.
    """
    if modulo not in MODULOS_VALIDOS:
        raise ValueError(f"Módulo inválido: {modulo}. Use: {MODULOS_VALIDOS}")

    diretorio = os.path.join(MANUAIS_DIR, modulo)
    os.makedirs(diretorio, exist_ok=True)

    caminho = os.path.join(diretorio, nome_arquivo)
    with open(caminho, "wb") as f:
        f.write(conteudo)

    sha256 = hashlib.sha256(conteudo).hexdigest()

    return {
        "modulo": modulo,
        "nome_arquivo": nome_arquivo,
        "caminho": caminho,
        "tamanho_bytes": len(conteudo),
        "sha256": sha256,
        "data_upload": datetime.now().isoformat(),
    }


def listar_manuais() -> list[dict[str, Any]]:
    """Lista todos os manuais PDF disponíveis, organizados por módulo."""
    manuais: list[dict[str, Any]] = []
    for modulo in MODULOS_VALIDOS:
        diretorio = os.path.join(MANUAIS_DIR, modulo)
        if not os.path.isdir(diretorio):
            continue
        for arquivo in sorted(os.listdir(diretorio)):
            if arquivo.lower().endswith(".pdf"):
                caminho = os.path.join(diretorio, arquivo)
                stat = os.stat(caminho)
                manuais.append(
                    {
                        "modulo": modulo,
                        "nome_arquivo": arquivo,
                        "caminho": caminho,
                        "tamanho_bytes": stat.st_size,
                        "data_modificacao": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                )
    return manuais


def remover_manual(modulo: str, nome_arquivo: str) -> bool:
    """Remove um manual PDF. Retorna True se removido com sucesso."""
    caminho = _caminho_manual(modulo, nome_arquivo)
    if os.path.isfile(caminho):
        os.remove(caminho)
        return True
    return False


def extrair_texto_pdf(caminho: str) -> str:
    """Extrai o texto de um PDF usando pypdf."""
    try:
        from pypdf import PdfReader  # noqa: PLC0415
    except ImportError:
        return "[pypdf não instalado. Execute: pip install pypdf]"

    try:
        reader = PdfReader(caminho)
        partes = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(partes)
    except Exception as exc:  # noqa: BLE001
        return f"[Erro ao extrair texto: {exc}]"


def obter_texto_manual(modulo: str) -> str:
    """Retorna o texto concatenado de todos os PDFs do módulo."""
    diretorio = os.path.join(MANUAIS_DIR, modulo)
    if not os.path.isdir(diretorio):
        return ""
    textos: list[str] = []
    for arquivo in sorted(os.listdir(diretorio)):
        if arquivo.lower().endswith(".pdf"):
            caminho = os.path.join(diretorio, arquivo)
            textos.append(extrair_texto_pdf(caminho))
    return "\n\n".join(textos)
