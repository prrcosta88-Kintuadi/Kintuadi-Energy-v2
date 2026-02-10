# ⚡ Kintuadi Energy Intelligence v2

**Plataforma de inteligência do mercado de energia brasileiro**  
Análise em tempo real do SIN com dados ONS e CCEE.

## 🎯 Objetivo

Fornecer uma visão integrada e explicável do Sistema Interligado Nacional (SIN), combinando dados físicos (ONS) e econômicos (CCEE) para suporte à decisão no mercado de energia.

## 🚀 Primeiros Passos

### Instalação Local:
```bash
# Clone o repositório
git clone https://github.com/seu-usuario/Kintuadi-Energy.git
cd Kintuadi-Energy

# Instale dependências
pip install -r requirements.txt

# Execute
python run_collector.py
# Escolha opção 1
# Acesse: http://localhost:8501

### Docker

docker build -t kintuadi .
docker run -p 8501:8501 kintuadi

###✨ Funcionalidades

Módulo	                            Descrição	                 Status
📊 Dashboard Integrado	   Interface única Streamlit	            ✅
💧 Hidrologia	            EAR, ENA, classificação	               ✅
⚡ Geração Horária	        Dados por fonte/região	              ✅
🔌 Carga Horária	         Consumo por submercado	               ✅
💰 PLD & Mercado	         Preços e volatilidade	               ✅
🔥 Análise Térmica	      Dupla perspectiva (Sistema/Gerador)	   ✅
🌎 Ciclo do SIN	         Regime operacional	                  ✅
📈 MCP Econômico	         Análise do mercado spot	               ✅
🔬 Análises Técnicas	      Explicações detalhadas	               ✅

### 🏗️ Arquitetura

Fluxo de Dados:
ONS/CCEE → Coletores v2 → CSVs → Integração → JSON → Análise CORE → Dashboard

Componentes Principais:
dashboard_integrado.py: Interface principal

run_collector.py: Orquestrador de execução

scripts/core_analysis.py: Motor de análise

scripts/integrated_collector_v2.py: Coletor integrado

analises_tecnicas.py: Explicações detalhadas

###📊 Métricas-Chave

Hidrologia: EAR médio, classificação, tendência
PLD: Preço médio, volatilidade normalizada, posição na banda
Relação CVU/PLD: Percentual com interpretação v5
Geração/Carga: Séries horárias por fonte/região
Ciclo SIN: Classificação do regime operacional

### 🐳 Deploy em Produção

Render.com: 750 horas/mês free

### Docker Compose:
version: '3.8'
services:
  kintuadi:
    build: .
    ports:
      - "8501:8501"
    restart: unless-stopped

### 🔧 Desenvolvimento
Kintuadi-Energy/
├── dashboard_integrado.py     # Dashboard principal
├── run_collector.py          # Menu de execução
├── analises_tecnicas.py      # Explicações técnicas
├── scripts/                  # Módulos internos
│   ├── core_analysis.py      # Análise CORE
│   ├── integrated_collector_v2.py  # Coletor
│   ├── ons_collector_v2.py   # Coletor ONS
│   ├── ccee_collector_v2.py  # Coletor CCEE
│   └── utils.py              # Utilitários
├── data/                     # Dados coletados
├── logs/                     # Logs do sistema
├── Dockerfile               # Configuração Docker
├── docker-compose.yml       # Orquestração
└── requirements.txt         # Dependências

# Testar coleta
python run_collector.py --option 4

# Testar dashboard
streamlit run dashboard_integrado.py

# Build Docker
docker build -t kintuadi .

### 📝 Licença
Este projeto está licenciado sob a MIT License - veja o arquivo LICENSE para detalhes.

### 🤝 Contribuição
Faça um fork do projeto
Crie uma branch para sua feature (git checkout -b feature/nova-funcionalidade)
Commit suas mudanças (git commit -am 'Adiciona nova funcionalidade')
Push para a branch (git push origin feature/nova-funcionalidade)
Abra um Pull Request

### 📞 Suporte
Issues: GitHub Issues

Email: kintuadi@kgmail.com

Desenvolvido com ❤️ para o setor elétrico brasileiro