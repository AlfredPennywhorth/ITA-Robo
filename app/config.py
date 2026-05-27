"""Configurações globais do ITA-Robô."""

import os

# Diretórios
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTADOS_DIR = os.path.join(DATA_DIR, "resultados")
RULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules")
MANUAIS_DIR = os.path.join(DATA_DIR, "manuais")

# Garante que os diretórios existam
os.makedirs(RESULTADOS_DIR, exist_ok=True)
os.makedirs(MANUAIS_DIR, exist_ok=True)

# HTTP
REQUEST_TIMEOUT = 15
USER_AGENT = (
    "Mozilla/5.0 (compatible; ITA-Robo/1.0; "
    "+https://github.com/AlfredPennywhorth/ITA-Robo)"
)
REQUEST_HEADERS = {"User-Agent": USER_AGENT}

# Pontuação
PONTUACAO = {
    "CONFORME": 1.0,
    "PARCIAL": 0.5,
    "NAO_CONFORME": 0.0,
    "NAO_APLICAVEL": None,
    "NAO_VERIFICADO": None,
}

# Formatos de arquivo aberto aceitos
FORMATOS_ABERTOS = {".csv", ".ods", ".odt", ".txt", ".json", ".xml", ".xlsx"}

# Domínios de legislação oficial aceitos
DOMINIOS_LEGISLACAO_OFICIAL = [
    "legislacao.prefeitura.sp.gov.br",
    "www.planalto.gov.br",
    "www.legisweb.com.br",
]

# Banco de dados SQLite
DB_PATH = os.path.join(DATA_DIR, "ita_robo.db")
