# ITA-Robô — Verificador Automatizado do Indicador de Transparência Ativa

**Projeto:** Verificação automatizada dos três botões obrigatórios de Transparência Ativa nos portais da Prefeitura de São Paulo.

**Módulos verificados:**
- ✅ Acesso à Informação
- ✅ Participação Social
- ✅ Quadro de Serviços

---

## Funcionalidades

- Interface web em **Streamlit** (sem Node.js)
- Crawler com **requests + BeautifulSoup** (padrão) e **Playwright** (fallback para sites com JavaScript/Liferay)
- Regras de verificação em arquivos **YAML** — editáveis sem alterar código
- **Upload de manuais em PDF** — armazene as versões vigentes e atualizações futuras dos manuais
- Extração de texto dos PDFs dos manuais para consulta
- Relatórios em **Excel** e **HTML**
- Histórico de auditorias em banco **SQLite**
- Avaliação em lote (via CSV)
- Agendamento mensal via **GitHub Actions**

---

## Estrutura do Projeto

```
ITA-Robo/
├─ app/
│  ├─ main.py                    # Interface Streamlit
│  ├─ config.py                  # Configurações globais
│  ├─ crawler/
│  │  ├─ fetcher.py              # Coleta HTML com requests
│  │  ├─ browser.py              # Fallback com Playwright
│  │  ├─ parser.py               # Extração de texto, links, datas, arquivos
│  │  └─ sitemap.py              # Descoberta de páginas
│  ├─ validators/
│  │  ├─ base.py                 # Estrutura ResultadoCriterio e StatusValidacao
│  │  ├─ button_validator.py     # Verifica botões obrigatórios
│  │  ├─ section_validator.py    # Verifica seções obrigatórias
│  │  ├─ text_validator.py       # Verifica textos padrão
│  │  ├─ date_validator.py       # Verifica datas de atualização
│  │  ├─ file_format_validator.py # Verifica formatos de arquivo
│  │  └─ link_validator.py       # Verifica links quebrados e legislação oficial
│  ├─ rules/
│  │  ├─ acesso_informacao.yaml
│  │  ├─ participacao_social.yaml
│  │  └─ quadro_servicos.yaml
│  ├─ reports/
│  │  ├─ report_builder.py       # Orquestra a auditoria e gera DataFrame
│  │  ├─ exports.py              # Exporta Excel e HTML
│  │  └─ templates/relatorio.html
│  ├─ storage/
│  │  └─ database.py             # SQLite — histórico de auditorias
│  └─ manuais/
│     └─ gerenciador.py          # Upload, listagem e extração de PDFs dos manuais
├─ data/
│  ├─ orgaos.csv                 # Lista de órgãos para auditoria em lote
│  ├─ manuais/                   # PDFs dos manuais armazenados por módulo
│  └─ resultados/                # Relatórios gerados
├─ tests/
│  └─ test_ita_robo.py
├─ requirements.txt
└─ .github/workflows/auditoria_mensal.yml
```

---

## Como Rodar no GitHub Codespaces

1. **Abra o Codespace** no repositório (botão verde `<> Code` → aba `Codespaces`)

2. **Instale as dependências:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Execute o aplicativo:**
   ```bash
   streamlit run app/main.py
   ```

4. Acesse o endereço exibido no terminal (o Codespace redireciona automaticamente para o seu navegador).

---

## Como Rodar Localmente

```bash
# Clone o repositório
git clone https://github.com/AlfredPennywhorth/ITA-Robo.git
cd ITA-Robo

# Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Instale dependências
pip install -r requirements.txt
playwright install chromium

# Rode a interface
streamlit run app/main.py
```

---

## Deploy em Produção

### Opção A — Streamlit Community Cloud

1. Faça um fork ou push do repositório para seu GitHub.
2. Acesse [share.streamlit.io](https://share.streamlit.io) e conecte o repositório.
3. Defina `app/main.py` como arquivo principal.
4. Para proteger o acesso, adicione nas **Secrets** da aplicação:
   ```toml
   ITA_ROBO_APP_PASSWORD = "sua-senha-aqui"
   ```
5. O arquivo `packages.txt` garante a instalação automática das dependências do Playwright.
6. Após o deploy, execute `playwright install chromium` via **terminal da nuvem** (se disponível) ou use a opção de pós-build nas configurações avançadas.

> **Nota sobre Playwright no Streamlit Cloud:** como o Playwright requer um binário do Chromium, é recomendado testar a coleta com `requests` primeiro. Se o site precisar de JavaScript, utilize o **fallback Playwright** marcando a opção na interface.

### Opção B — Docker (Render, Railway, Fly.io, VPS)

```bash
# Construir a imagem
docker build -t ita-robo .

# Rodar o container
docker run -p 8501:8501 \
  -e ITA_ROBO_APP_PASSWORD="sua-senha-aqui" \
  ita-robo
```

Acesse em `http://localhost:8501`.

#### Deploy no Render

1. Conecte o repositório ao [Render](https://render.com).
2. O arquivo `render.yaml` já define o serviço automaticamente.
3. Defina a variável `ITA_ROBO_APP_PASSWORD` no painel do Render (Environment > Add Environment Variable).

#### Variável de Ambiente de Segurança

| Variável | Descrição | Obrigatório |
|---|---|---|
| `ITA_ROBO_APP_PASSWORD` | Senha de acesso à interface web | Não (se ausente, o app fica aberto) |

---

## ⚠️ Persistência de Dados

Os relatórios Excel/HTML e os manuais PDF são salvos em:
- `data/resultados/` — relatórios gerados
- `data/manuais/` — manuais PDF enviados
- `data/ita_robo.db` — banco SQLite com histórico

**Em plataformas sem volume persistente** (Streamlit Cloud, Render free tier), esses arquivos são perdidos ao reiniciar o container. **Sempre baixe os relatórios imediatamente após a avaliação** usando os botões "📥 Baixar Excel" e "📄 Baixar HTML" na interface.

---

## Como Usar os Manuais em PDF

O sistema permite armazenar os manuais vigentes (e suas atualizações futuras) diretamente na interface:

1. Na barra lateral, clique em **"Manuais PDF"**
2. Selecione o módulo correspondente (Acesso à Informação, Participação Social ou Quadro de Serviços)
3. Faça upload do arquivo PDF
4. O sistema armazena o manual e permite visualizar o texto extraído

Quando os manuais forem atualizados pela CGM, basta enviar a nova versão sem necessidade de alterar código.

---

## Atualizar as Regras YAML

As regras de verificação ficam nos arquivos:

- `app/rules/acesso_informacao.yaml`
- `app/rules/participacao_social.yaml`
- `app/rules/quadro_servicos.yaml`

Para adicionar uma nova seção obrigatória, edite o YAML correspondente:

```yaml
pagina_principal:
  secoes_obrigatorias:
    - "Nova Seção Exigida"
```

---

## Executar os Testes

```bash
# Testes básicos
pytest tests/ -v

# Com cobertura de código
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## Classificação de Resultados

| Status | Pontuação | Descrição |
|--------|-----------|-----------|
| CONFORME | 1,00 | Critério totalmente atendido |
| PARCIALMENTE CONFORME | 0,50 | Critério parcialmente atendido |
| NÃO CONFORME | 0,00 | Critério não atendido |
| NÃO APLICÁVEL | — | Não entra no cálculo |
| NÃO VERIFICADO AUTOMATICAMENTE | — | Requer revisão humana |

> **Atenção:** O índice gerado é um *Índice Automatizado Preliminar de Conformidade*.
> Itens marcados como "NÃO VERIFICADO AUTOMATICAMENTE" exigem revisão humana antes de uso oficial.

---

## Agendamento Mensal (GitHub Actions)

O arquivo `.github/workflows/auditoria_mensal.yml` configura execução automática todo dia 1 de cada mês às 06:00 UTC.

Para executar manualmente:
1. Acesse a aba **Actions** no GitHub
2. Selecione o workflow **Auditoria Mensal — ITA-Robô**
3. Clique em **Run workflow**

---

## Tecnologias Utilizadas

| Camada | Tecnologia |
|--------|-----------|
| Interface | Streamlit |
| Crawler (padrão) | requests + BeautifulSoup4 |
| Crawler (dinâmico) | Playwright Python |
| Regras | YAML |
| Relatórios | Pandas + OpenPyXL + Jinja2 |
| Banco de dados | SQLite |
| Leitura de PDF | pypdf |
| Similaridade textual | rapidfuzz |
