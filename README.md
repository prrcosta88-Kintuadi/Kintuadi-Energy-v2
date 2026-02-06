# Kintuadi Energy v2

Plataforma de coleta, integração e análise de dados do setor elétrico brasileiro
(ONS, CCEE e fontes correlatas).

## Estrutura do Projeto

Kintuadi-Energy-v2/
├── data/
├── logs/
├── scripts/
│ ├── data_models.py
│ ├── ons_collector_v2.py
│ ├── ccee_collector_v2.py
│ ├── analyzer_v2.py
│ ├── integrated_collector_v2.py
│ └── utils.py
├── dashboard_integrado.py
├── run_collector.py
├── requirements.txt
└── README.md


## Requisitos
- Python 3.10+
- Dependências listadas em `requirements.txt`

## Execução
```bash
python run_collector.py

---

## 4️⃣ Primeiro commit (registrar o estado inicial)

### 4.1 Ver o que será versionado
```bash
git status
