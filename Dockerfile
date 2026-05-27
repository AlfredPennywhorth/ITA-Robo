FROM python:3.12-slim

WORKDIR /app

# Copiar e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar Chromium e dependências do sistema via Playwright
RUN playwright install chromium --with-deps

# Copiar o código-fonte
COPY . .

# Garantir que os diretórios de dados existam
RUN mkdir -p data/resultados data/manuais

EXPOSE 8501

ENV PORT=8501

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/_stcore/health || exit 1

CMD streamlit run app/main.py \
    --server.address 0.0.0.0 \
    --server.port ${PORT} \
    --server.headless true
