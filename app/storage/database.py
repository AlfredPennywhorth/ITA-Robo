"""Armazenamento em banco SQLite das auditorias."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from app.config import DB_PATH


def _conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_banco() -> None:
    """Cria as tabelas se não existirem."""
    with _conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auditorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_orgao TEXT NOT NULL,
                url TEXT NOT NULL,
                ano_referencia INTEGER,
                data_auditoria TEXT NOT NULL,
                pontuacao_geral REAL,
                pontuacoes_json TEXT,
                erros_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS criterios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auditoria_id INTEGER NOT NULL,
                criterio_id TEXT,
                modulo TEXT,
                descricao TEXT,
                status TEXT,
                pontuacao REAL,
                evidencia TEXT,
                url TEXT,
                FOREIGN KEY (auditoria_id) REFERENCES auditorias(id)
            )
            """
        )
        conn.commit()


def salvar_auditoria(auditoria: dict[str, Any]) -> int:
    """Persiste uma auditoria no banco. Retorna o ID da auditoria inserida."""
    inicializar_banco()
    with _conectar() as conn:
        cursor = conn.execute(
            """
            INSERT INTO auditorias
                (nome_orgao, url, ano_referencia, data_auditoria,
                 pontuacao_geral, pontuacoes_json, erros_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                auditoria.get("nome_orgao", ""),
                auditoria.get("url", ""),
                auditoria.get("ano_referencia"),
                datetime.now().isoformat(),
                auditoria.get("pontuacao_geral"),
                json.dumps(auditoria.get("pontuacoes", {}), ensure_ascii=False),
                json.dumps(auditoria.get("erros", []), ensure_ascii=False),
            ),
        )
        auditoria_id = cursor.lastrowid

        for resultados in auditoria.get("resultados", {}).values():
            for r in resultados:
                d = r.to_dict()
                conn.execute(
                    """
                    INSERT INTO criterios
                        (auditoria_id, criterio_id, modulo, descricao,
                         status, pontuacao, evidencia, url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        auditoria_id,
                        d.get("criterio_id"),
                        d.get("modulo"),
                        d.get("descricao"),
                        d.get("status"),
                        d.get("pontuacao"),
                        d.get("evidencia"),
                        d.get("url"),
                    ),
                )
        conn.commit()
    return auditoria_id


def listar_auditorias() -> list[dict]:
    """Retorna todas as auditorias registradas."""
    inicializar_banco()
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM auditorias ORDER BY data_auditoria DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def buscar_auditoria(auditoria_id: int) -> dict | None:
    """Retorna detalhes de uma auditoria pelo ID."""
    inicializar_banco()
    with _conectar() as conn:
        row = conn.execute(
            "SELECT * FROM auditorias WHERE id = ?", (auditoria_id,)
        ).fetchone()
        if not row:
            return None
        auditoria = dict(row)
        criterios = conn.execute(
            "SELECT * FROM criterios WHERE auditoria_id = ?", (auditoria_id,)
        ).fetchall()
        auditoria["criterios"] = [dict(c) for c in criterios]
    return auditoria
