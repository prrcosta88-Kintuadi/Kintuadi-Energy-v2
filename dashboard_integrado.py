# dashboard_integrado.py — CORE REAL • ZERO DADOS FICTÍCIOS
# VERSÃO REVISADA: Compatível com análise térmica v5 (dupla perspectiva)
# COM BOTÃO DE ATUALIZAÇÃO E CARREGAMENTO DE ARQUIVO COMO FONTE PRINCIPAL

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import json
import glob
import os
import subprocess
import sys
from datetime import datetime, timedelta
import logging
import streamlit.components.v1 as components
from analises_tecnicas import mostrar_analises_tecnicas
from scripts.core_analysis import build_core_analysis
from typing import Optional, Dict, List, Any, Union

#metadata = core.get("metadata", {})
#versao_modelo = metadata.get("modelo_analitico", "v1")
#st.caption(f"Modelo Analítico: {versao_modelo}")


# -----------------------------------------------------------------------------
# Configuração
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração da página
st.set_page_config(
    page_title="Kintuadi Energy Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# CSS Dinâmico baseado no config.toml
# -----------------------------------------------------------------------------
def load_custom_css():
    """Carrega configurações CSS do config.toml e gera CSS dinâmico."""
    
    # Valores padrão (fallback)
    css_config = {
        "global_background": "#020617",
        "global_text_color": "#e5e7eb",
        "sidebar_background": "#020f2a",
        "h1_size": "1.8rem",
        "h3_size": "1.3rem",
        "metric_label_size": "1rem",
        "metric_value_size": "1.8rem",
        "card_title_size": "1.1rem",
        "section_title_size": "1.4rem",
        "success_color": "#22c55e",
        "warning_color": "#f59e0b",
        "critical_color": "#ef4444",
        "info_color": "#3b82f6",
        "kpi_gradient_start": "#38bdf8",
        "kpi_gradient_end": "#0ea5e9",
        "card_border_radius": "10px",
        "card_border_color": "rgba(255,255,255,0.08)",
        "card_success_border": "#22c55e",
        "card_warning_border": "#f59e0b",
        "card_critical_border": "#ef4444",
        "card_info_border": "#3b82f6",
    }
    
    # Tentar carregar do config.toml
    try:
        import toml
        config_path = ".streamlit/config.toml"
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = toml.load(f)
                
            # Atualizar com valores do config.toml se existirem
            if "custom_css" in config:
                css_config.update(config["custom_css"])
                
            print(f"DEBUG: CSS Config carregada: {list(css_config.keys())}")
    except ImportError:
        print("DEBUG: Biblioteca toml não instalada. Use: pip install toml")
    except Exception as e:
        print(f"DEBUG: Erro ao carregar config.toml: {e}")
    
    # Gerar CSS dinâmico
    css = f"""
    <style>
    .stApp {{ 
        background-color:{css_config['global_background']}; 
        color:{css_config['global_text_color']}; 
    }}
    
    /* Sidebar */
    section[data-testid="stSidebar"] {{ 
        background-color:{css_config['sidebar_background']}; 
        color: #ffffff !important;
    }}
    
    section[data-testid="stSidebar"] * {{
        color: #ffffff !important;
    }}
    
    /* Cabeçalhos */
    h1 {{
        font-size: {css_config['h1_size']} !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        margin-bottom: 0.5rem !important;
    }}
    
    h3 {{
        font-size: {css_config['h3_size']} !important;
        color: {css_config['global_text_color']} !important;
        font-weight: 400 !important;
        opacity: 0.9;
        margin-top: 0 !important;
    }}
    
    /* Cards */
    .insight-card {{
        background: linear-gradient(135deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
        border-radius: {css_config['card_border_radius']};
        padding: 1.1rem;
        border: 1px solid {css_config['card_border_color']};
    }}
    
    .insight-card h4 {{
        font-size: {css_config['card_title_size']};
        font-weight: 600;
        margin-bottom: 0.5rem;
        color: #ffffff !important;
    }}
    
    .insight-card p {{
        color: #ffffff !important;
        opacity: 0.9;
        font-size: 0.9rem;
        margin-bottom: 0.3rem;
    }}
    
    .insight-card.success {{ border-left: 4px solid {css_config['card_success_border']}; }}
    .insight-card.warning {{ border-left: 4px solid {css_config['card_warning_border']}; }}
    .insight-card.critical {{ border-left: 4px solid {css_config['card_critical_border']}; }}
    .insight-card.info {{ border-left: 4px solid {css_config['card_info_border']}; }}
    
    .kpi-value {{
        font-size: 1.4rem;
        font-weight: 600;
        background: linear-gradient(90deg, {css_config['kpi_gradient_start']}, {css_config['kpi_gradient_end']});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    
    .section-title {{
        font-size:{css_config['section_title_size']};
        font-weight:700;
        margin:1.0rem 0.5rem;
        color: #ffffff !important;
    }}
    
    /* Métricas */
    [data-testid="metric-container"] {{
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        padding: 16px !important;
        background-color: rgba(255, 255, 255, 0.03) !important;
    }}
    
    [data-testid="stMetricLabel"], 
    [data-testid="stMetricLabel"] p,
    [data-testid="stMetricLabel"] div {{
        color: #ffffff !important;
        font-size: {css_config['metric_label_size']} !important;
        font-weight: 600 !important;
        opacity: 0.9;
    }}
    
    [data-testid="stMetricValue"], 
    [data-testid="stMetricValue"] > div,
    [data-testid="stMetricValue"] p,
    [data-testid="stMetricValue"] span {{
        color: #ffffff !important;
        font-size: {css_config['metric_value_size']} !important;
        font-weight: 700 !important;
    }}
    
    [data-testid="stMetricDelta"], 
    [data-testid="stMetricDelta"] > div,
    [data-testid="stMetricDelta"] svg {{
        color: #ffffff !important;
        fill: #ffffff !important;
    }}
    
    [data-testid="stMetricDelta"] svg path {{
        fill: #ffffff !important;
    }}
    
    /* Análise PLD */
    .pld-analysis-box {{
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(30, 58, 138, 0.05));
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1.5rem 0;
        border-left: 4px solid {css_config['info_color']};
    }}
    
    .pld-warning-box {{
        background: linear-gradient(135deg, rgba(234, 179, 8, 0.1), rgba(202, 138, 4, 0.05));
        border-radius: 10px;
        padding: 1.2rem;
        margin: 1rem 0;
        border-left: 4px solid {css_config['warning_color']};
    }}
    
    /* Tabela */
    .kintuadi-table {{
        width: 100%;
        border-collapse: collapse;
        background-color: {css_config['global_background']};
        color: #ffffff !important;
        font-size: 14px;
    }}
    
    .kintuadi-table thead tr {{
        background-color: {css_config['sidebar_background']};
    }}
    
    .kintuadi-table th {{
        color: #ffffff !important;
        font-weight: 600;
        padding: 8px 10px;
        border: 1px solid #ffffff !important;
        text-align: left;
    }}
    
    .kintuadi-table td {{
        padding: 8px 10px;
        border: 1px solid #ffffff !important;
        text-align: right;
        background-color: {css_config['global_background']} !important;
        color: #ffffff !important;
    }}
    
    .kintuadi-table td:first-child {{
        text-align: left;
    }}
    
    .kintuadi-table tr:hover td {{
        background-color: {css_config['sidebar_background']} !important;
        color: #ffffff !important;
    }}
    
    /* Badges */
    .perspectiva-badge {{
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 0.2rem;
        color: #ffffff !important;
    }}
    
    .badge-sistema {{
        background-color: rgba(59, 130, 246, 0.2);
        color: #ffffff !important;
        border: 1px solid rgba(59, 130, 246, 0.4);
    }}
    
    .badge-gerador {{
        background-color: rgba(16, 185, 129, 0.2);
        color: #ffffff !important;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }}
    
    /* Cards de perspectiva */
    .card-perspectiva {{
        background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
        border-radius: 10px;
        padding: 1.2rem;
        margin: 0.8rem 0;
        border: 1px solid rgba(255,255,255,0.12);
    }}
    
    .card-perspectiva * {{
        color: #ffffff !important;
    }}
    
    .card-sistema {{
        border-left: 4px solid {css_config['info_color']};
    }}
    
    .card-gerador {{
        border-left: 4px solid #10b981;
    }}
    
    /* Botões */
    .update-button {{
        background: linear-gradient(135deg, {css_config['info_color']}, #1d4ed8);
        color: white !important;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s;
        width: 100%;
        margin-top: 1rem;
    }}
    
    .update-button:hover {{
        background: linear-gradient(135deg, #2563eb, #1e40af);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
    }}
    
    .update-button:active {{
        transform: translateY(0);
    }}
    
    .update-button:disabled {{
        background: #6b7280;
        cursor: not-allowed;
        transform: none;
        box-shadow: none;
    }}
    
    /* Loading spinner */
    .loading-spinner {{
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid rgba(59, 130, 246, 0.3);
        border-radius: 50%;
        border-top-color: {css_config['info_color']};
        animation: spin 1s ease-in-out infinite;
        margin-right: 10px;
    }}
    
    @keyframes spin {{
        to {{ transform: rotate(360deg); }}
    }}
    
    /* Outros elementos */
    .streamlit-expanderHeader {{
        color: #ffffff !important;
    }}
    
    .streamlit-expanderContent * {{
        color: #ffffff !important;
    }}
    
    .pld-analysis-box h3,
    .pld-analysis-box p,
    .pld-analysis-box div {{
        color: #ffffff !important;
    }}
    
    /* Mensagens de status */
    .stAlert {{
        color: #ffffff !important;
    }}
    
    .stSuccess {{
        background-color: rgba(34, 197, 94, 0.2) !important;
        border-color: {css_config['success_color']} !important;
    }}
    
    .stError {{
        background-color: rgba(239, 68, 68, 0.2) !important;
        border-color: {css_config['critical_color']} !important;
    }}
    
    .stWarning {{
        background-color: rgba(245, 158, 11, 0.2) !important;
        border-color: {css_config['warning_color']} !important;
    }}
    
    .stInfo {{
        background-color: rgba(59, 130, 246, 0.2) !important;
        border-color: {css_config['info_color']} !important;
    }}
    </style>
    """
    
    return css

# Cabeçalho
st.markdown("# 📊 Dashboard Principal - Kintuadi Energy Intelligence")
st.markdown("### Análises a partir de dados do ONS e CCEE em tempo real")
st.markdown("---")

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def load_latest_raw():
    """Carrega os dados brutos mais recentes."""
    try:
        # Primeiro, tentar carregar do arquivo principal
        if os.path.exists("data/kintuadi_latest.json"):
            with open("data/kintuadi_latest.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"DEBUG: Dados brutos carregados. Tipo: {type(data)}")
                return data
        
        # Se não encontrar, buscar outros arquivos
        files = glob.glob("data/kintuadi_*.json")
        if not files:
            print("DEBUG: Nenhum arquivo kintuadi_*.json encontrado")
            return None
            
        # Pegar o mais recente
        latest_file = max(files, key=os.path.getctime)
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"DEBUG: Dados brutos carregados de arquivo histórico: {latest_file}")
            return data
            
    except Exception as e:
        print(f"DEBUG: Erro ao carregar dados brutos: {e}")
        return None

def load_core_analysis():
    """Executa build_core_analysis no primeiro carregamento da sessão e reutiliza o resultado."""
    cached_core = st.session_state.get("core_runtime")
    if isinstance(cached_core, dict):
        return cached_core

    raw = load_latest_raw()
    if not raw:
        logger.error("Dados brutos indisponíveis para executar build_core_analysis.")
        return None

    try:
        logger.info("Executando build_core_analysis (modo obrigatório no carregamento do dashboard)...")
        core = build_core_analysis(raw, output_dir="data")

        if isinstance(core, dict):
            return core

        logger.error("build_core_analysis retornou estrutura inválida.")
        return None

    except Exception as e:
        logger.error(f"Falha ao executar build_core_analysis: {e}")
        return None


def diagnose_pipeline_status() -> Dict[str, str]:
    """Diagnóstico simples por etapa (coleta → integração → análise)."""
    status = {
        "coleta": "erro",
        "integracao": "erro",
        "analise": "erro",
    }

    has_raw_latest = os.path.exists("data/kintuadi_latest.json")
    has_any_raw = bool(glob.glob("data/kintuadi_*.json"))
    has_core = os.path.exists("data/core_analysis_latest.json")

    if has_raw_latest or has_any_raw:
        status["coleta"] = "ok"
        status["integracao"] = "ok"

    if has_core:
        status["analise"] = "ok"

    return status


def diagnose_pipeline_status() -> Dict[str, str]:
    """Diagnóstico simples por etapa (coleta → integração → análise)."""
    status = {
        "coleta": "erro",
        "integracao": "erro",
        "analise": "erro",
    }

    has_raw_latest = os.path.exists("data/kintuadi_latest.json")
    has_any_raw = bool(glob.glob("data/kintuadi_*.json"))
    has_core = os.path.exists("data/core_analysis_latest.json")

    if has_raw_latest or has_any_raw:
        status["coleta"] = "ok"
        status["integracao"] = "ok"

    if has_core:
        status["analise"] = "ok"

    return status


def run_data_collector():
    """Executa o coletor de dados importando diretamente a função."""
    try:
        print("🔄 Iniciando coleta de dados...")
        
        # Tentar importar do run_collector.py
        try:
            from run_collector import run_collector_v2
            print("✅ Módulo run_collector importado com sucesso")
        except ImportError as e:
            print(f"❌ Erro ao importar run_collector: {e}")
            print("Tentando importar diretamente do integrated_collector_v2...")
            
            # Fallback: importar diretamente
            try:
                from scripts.integrated_collector_v2 import KintuadiIntegratedCollectorV2
                
                # Executar coleta
                collector = KintuadiIntegratedCollectorV2()
                success = collector.quick_collect()
                
                if success:
                    print("✅ Coleta executada com sucesso (método direto)")
                    return True
                else:
                    print("❌ Coleta falhou (método direto)")
                    return False
                    
            except ImportError as e2:
                print(f"❌ Erro ao importar integrated_collector_v2: {e2}")
                st.error(f"Erro de importação: {e2}")
                return False
        
        # Executar usando a função importada
        print("🚀 Executando run_collector_v2()...")
        success = run_collector_v2()
        
        if success:
            print("✅ Coleta concluída com sucesso!")
            return True
        else:
            print("❌ Coleta falhou")
            return False
            
    except Exception as e:
        print(f"❌ Erro durante a execução do coletor: {e}")
        import traceback
        traceback.print_exc()
        st.error(f"Erro na coleta: {str(e)[:100]}...")
        return False

def badge_status_sistema(classificacao: str, risco_sistêmico: str) -> str:
    """
    Determina a cor do badge baseado na classificação do SISTEMA.
    """
    if classificacao in ("risco_custo", "crítico"):
        return "critical"
    if classificacao in ("pressão_moderada", "atenção"):
        return "warning"
    if classificacao in ("folga_estrutural", "folga_operacional", "confortável", "abundante"):
        return "success"
    if risco_sistêmico == "alto":
        return "critical"
    if risco_sistêmico == "moderado":
        return "warning"
    if risco_sistêmico in ("baixo", "muito_baixo"):
        return "success"
    return ""

def badge_status_gerador(perspectiva_gerador: str) -> str:
    """
    Determina a cor do badge baseado na perspectiva do GERADOR.
    """
    if perspectiva_gerador == "competitiva":
        return "success"
    if perspectiva_gerador == "estrutural":
        return "info"  # Azul para indicar necessidade operacional
    return ""

def formatar_percentual_cvu_pld(percentual: Optional[float]) -> str:
    """Formata o percentual CVU/PLD com interpretação."""
    if percentual is None:
        return "—"
    
    if percentual > 150:
        return f"{percentual:.0f}% ⬇️"  # Seta para baixo = folga
    elif percentual >= 100:
        return f"{percentual:.0f}% ⚠️"  # Atenção
    else:
        return f"{percentual:.0f}%"

def interpretar_razao_cvu_pld(percentual: Optional[float]) -> str:
    """Interpreta o percentual CVU/PLD em linguagem natural."""
    if percentual is None:
        return "Dados indisponíveis"
    
    if percentual > 150:
        return "Folga Estrutural - Térmicas fora do despacho econômico"
    elif percentual >= 100:
        return f"CVU em {percentual:.0f}% do PLD - Risco de despacho com prejuízo"
    elif percentual >= 95:
        return f"CVU em {percentual:.0f}% do PLD - Pressão moderada"
    elif percentual >= 80:
        return f"CVU em {percentual:.0f}% do PLD - Atenção"
    else:
        return f"CVU em {percentual:.0f}% do PLD - Folga operacional"

def analisar_formacao_preco_pld(core):
    """Analisa a formação do preço do PLD com base nas correlações."""
    mcp = core.get("mcp_economico", {})
    adv = core.get("advanced_metrics", {})
    
    # Nova abordagem: prioriza aderência físico-econômica do bloco avançado
    corr_carga = adv.get("correlacoes", {}).get("pld_vs_carga_liquida")
    if corr_carga is None:
        corr_carga = mcp.get("correlacoes", {}).get("pld_vs_carga")

    corr_hidro = adv.get("correlacoes", {}).get("pld_vs_ear_mensal")
    if corr_hidro is None:
        corr_hidro = mcp.get("correlacoes", {}).get("pld_vs_hidraulica")
    
    # Valores absolutos para análise de força
    abs_corr_carga = abs(corr_carga) if corr_carga is not None else 0
    abs_corr_hidro = abs(corr_hidro) if corr_hidro is not None else 0
    
    resultados = {
        "carga_explica": False,
        "hidro_explica": False,
        "analise": "",
        "recomendacao": "",
        "severidade": "info"  # info, warning, critical
    }
    
    # Análise da correlação com carga
    if corr_carga is not None:
        if abs_corr_carga > 0.6:
            resultados["carga_explica"] = True
            if corr_carga > 0:
                carga_analise = "PLD responde fortemente à variação da demanda"
            else:
                carga_analise = "PLD tem correlação negativa forte com a demanda (anômalo)"
        elif abs_corr_carga > 0.3:
            resultados["carga_explica"] = True
            carga_analise = "Demanda tem influência moderada no PLD"
        else:
            carga_analise = "Demanda não explica o comportamento do PLD"
    else:
        carga_analise = "Correlação com demanda indisponível"
    
    # Análise da correlação com hidrologia
    if corr_hidro is not None:
        if abs_corr_hidro > 0.6:
            resultados["hidro_explica"] = True
            if corr_hidro < 0:
                hidro_analise = "PLD responde fortemente à hidrologia (comportamento esperado)"
            else:
                hidro_analise = "PLD tem correlação POSITIVA com hidrologia (ANÔMALO)"
                resultados["severidade"] = "warning"
        elif abs_corr_hidro > 0.3:
            resultados["hidro_explica"] = True
            hidro_analise = "Hidrologia tem influência moderada no PLD"
        else:
            hidro_analise = "Hidrologia não explica o comportamento do PLD"
    else:
        hidro_analise = "Correlação com hidrologia indisponível"
    
    # Determinar análise geral
    if resultados["carga_explica"] and resultados["hidro_explica"]:
        if abs_corr_carga > abs_corr_hidro:
            resultados["analise"] = f"Formação de preço predominantemente CONJUNTURAL (demanda)"
        else:
            if corr_hidro < 0:
                resultados["analise"] = f"Formação de preço predominantemente ESTRUTURAL (hidrologia)"
            else:
                resultados["analise"] = f"Formação ANÔMALA: PLD sobe com mais hidrologia"
                resultados["severidade"] = "critical"
    
    elif resultados["carga_explica"]:
        resultados["analise"] = f"Formação CONJUNTURAL: PLD segue principalmente a demanda"
    
    elif resultados["hidro_explica"]:
        if corr_hidro < 0:
            resultados["analise"] = f"Formação ESTRUTURAL: PLD determinado pela hidrologia"
        else:
            resultados["analise"] = f"Formação ANÔMALA: PLD sobe com mais água (investigar)"
            resultados["severidade"] = "critical"
    
    else:
        # Nenhuma correlação forte
        resultados["analise"] = "Comportamento do PLD NÃO EXPLICADO por demanda ou hidrologia"
        resultados["recomendacao"] = "Investigar outros fatores: restrições operacionais, térmicas marginais, fatores externos"
        resultados["severidade"] = "warning"
    
    # Adicionar recomendações específicas
    if not resultados["recomendacao"]:
        if corr_hidro is not None and corr_hidro > 0.3:
            resultados["recomendacao"] = "⚠️ INVESTIGAR: Correlação positiva com hidrologia é contra-intuitiva"
            resultados["severidade"] = "critical"
        elif corr_carga is not None and abs_corr_carga < 0.3 and corr_hidro is not None and abs_corr_hidro < 0.3:
            resultados["recomendacao"] = "🔍 Investigar: PLD pode estar sendo determinado por fatores não capturados (térmicas, restrições, administração)"
            resultados["severidade"] = "warning"
    
    return resultados, carga_analise, hidro_analise

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    # Carregar CSS dinâmico
    css = load_custom_css()
    st.markdown(css, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("## ⚡ **KINTUADI**")
        st.markdown("---")
        
        # Navegação principal
        if 'modo' not in st.session_state:
            st.session_state.modo = "📊 Dashboard Principal"
        
        modo = st.radio(
            "Navegação Principal",
            ["📊 Dashboard Principal", "🔬 Análises Técnicas"],
            index=0 if st.session_state.modo == "📊 Dashboard Principal" else 1,
            help="Selecione o modo de visualização",
            key="modo_selector"
        )
        
        # Atualizar session_state
        st.session_state.modo = modo
        
        st.markdown("---")
        
        # Status do sistema
        st.markdown("### 📊 Status do Sistema")
        
        # Carregar a análise do arquivo como fonte principal
        core = load_core_analysis()
        
        if core:
            timestamp = core.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    formatted_time = dt.strftime("%d/%m/%Y %H:%M:%S")
                    st.success(f"✓ Dados de: {formatted_time}")
                except:
                    st.success(f"✓ Dados disponíveis")

            st.info("🔒 Dashboard em modo somente leitura.")
            
            st.markdown("---")
            
        else:
            st.error("❌ Análise não disponível")
            st.markdown("---")

            status = diagnose_pipeline_status()
            st.markdown("**Diagnóstico por etapa:**")
            st.write(f"• Coleta: {'✅' if status['coleta']=='ok' else '❌'}")
            st.write(f"• Integração: {'✅' if status['integracao']=='ok' else '❌'}")
            st.write(f"• Análise (core): {'✅' if status['analise']=='ok' else '❌'}")

            st.caption("Execute a coleta/integrador externamente e gere o core antes de abrir o dashboard.")
        
        st.markdown("---")
        st.caption("Versão 2.0 • Dados em tempo real")

    # Se não tem core carregado, mostrar erro
    if not core:
        st.error("## ❌ Análise do Sistema Indisponível")
        st.markdown("""
        Não foi possível carregar a análise do sistema. Por favor:
        
        1. **Execute o coletor integrado** primeiro
        2. **Gere o core_analysis** a partir do raw coletado
        3. Verifique se o arquivo `data/core_analysis_latest.json` existe
        
        Fluxo recomendado:
        ```bash
        python run_collector.py
        # depois gere o core (pipeline de análise)
        ```
        """)
        return

    # Roteamento para análises técnicas
    if st.session_state.modo == "🔬 Análises Técnicas":
        mostrar_analises_tecnicas(core)
        return

    # =========================================================================
    # HEADER COM BOTÃO DE ATUALIZAÇÃO RÁPIDO
    # =========================================================================
    
    st.markdown("---")

    # =========================================================================
    # PULSO DO SISTEMA - REVISADO
    # =========================================================================
    st.markdown('<div class="section-title">📈 Pulso do Sistema</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)

    with c1:
        hyd = core.get("hydrology", {})
        ear = hyd.get("ear_medio")
        ear_fmt = f"{ear:.2f}%" if isinstance(ear, (int, float)) else "—"

        st.markdown(
            f"""
<div class="insight-card {badge_status_sistema(hyd.get('classificacao', {}).get('classe', ''), '')}">
<h4>💧 Hidrologia</h4>
<div class="kpi-value">{ear_fmt}</div>
<p><strong>Classificação:</strong> {hyd.get('classificacao', {}).get('classe', 'indisponível').capitalize()}</p>
</div>
""",
            unsafe_allow_html=True,
        )

    with c2:
        prices = core.get("prices", {})
        pld = prices.get("pld_medio")
        vol_norm = prices.get("pld_volatilidade_norm")
        if vol_norm is None:
            # fallback opcional se existir std e média
            std = prices.get("pld_std")
            mean = prices.get("pld_medio")
            if isinstance(std, (int, float)) and isinstance(mean, (int, float)) and mean != 0:
                vol_norm = (std / mean) * 100    
        if vol_norm is not None:
            vol_text = f"{vol_norm:.1f}% (banda)"
        else:
            vol_text = "—"

        pld_fmt = f"R$ {pld:.2f}" if isinstance(pld, (int, float)) else "—"

        st.markdown(
            f"""
<div class="insight-card">
<h4>💰 PLD Horário</h4>
<div class="kpi-value">{pld_fmt}</div>
<p>Volatilidade: {vol_text}</p>
</div>
""",
            unsafe_allow_html=True,
        )

    with c3:
        # NOVA ESTRUTURA: Análise térmica com dupla perspectiva
        thermal = core.get("thermal_analysis", {})
        if not isinstance(thermal, dict):
            thermal = {}
        analise_sistema = thermal.get("analise_sistema", {})
        classificacao = analise_sistema.get("classificacao", "indisponível")
        risco_sistêmico = analise_sistema.get("risco_sistêmico", "")
        
        # Obter percentual CVU/PLD
        indicadores = thermal.get("indicadores_quantitativos", {})
        percentual_cvu_pld = indicadores.get("percentual_cvu_pld")
        
        percentual_fmt = formatar_percentual_cvu_pld(percentual_cvu_pld)
        
        st.markdown(
            f"""
<div class="insight-card {badge_status_sistema(classificacao, risco_sistêmico)}">
<h4>🔥 Relação CVU/PLD</h4>
<div class="kpi-value">{percentual_fmt}</div>
<p>
<strong>Classificação:</strong> {classificacao.replace('_', ' ').title()}<br>
</p>
</div>
""",
            unsafe_allow_html=True,
        )

    # =========================================================================
    # EXPLICAÇÃO DOS CARDS - REVISADA
    # =========================================================================
    with st.expander("📖 Metodologia dos indicadores Pulso do Sistema"):
        st.markdown("""
        **Hidrologia:** Classificação baseada no EAR médio dos subsistemas, refletindo o nível de armazenamento e segurança hídrica do SIN.
        
        **PLD Horário:** Preço médio de liquidação das diferenças, calculado pela CCEE. Volatilidade normalizada considera a banda regulatória total.
        
        **Relação CVU/PLD:** - percentual do CVU em relação ao PLD:
        - **< 80%:** Folga operacional (CVU significativamente menor que PLD)
        - **80-95%:** Atenção (CVU próximo do PLD)
        - **95-100%:** Pressão moderada (CVU muito próximo do PLD)
        - **100-150%:** Risco de custos (CVU ≥ PLD, possível despacho com prejuízo)
        - **> 150%:** Folga estrutural (CVU muito maior que PLD, térmicas fora do despacho econômico)
        """)

    # =========================================================================
    # CICLO DO SIN
    # =========================================================================
    st.markdown('<div class="section-title">🌎 Ciclo do SIN</div>', unsafe_allow_html=True)

    st.caption(
        "O Ciclo do SIN integra hidrologia, estresse de carga e comportamento de preços, "
        "permitindo identificar se o sistema opera em regime úmido, seco, crítico ou de transição."
    )

    cycle = core.get("sin_cycle", {})

    if cycle:
        st.markdown(
            f"""
<div class="insight-card">
<h4>Regime Hidroenergético</h4>
<div class="kpi-value">{cycle.get("cycle", "—").upper()}</div>
<p>{cycle.get("description", "")}</p>
</div>
""",
            unsafe_allow_html=True,
        )

    # =========================================================================
    # ANÁLISE DA FORMAÇÃO DO PREÇO DO PLD
    # =========================================================================
    st.markdown('<div class="section-title">🔍 Análise da Formação do Preço (PLD)</div>', unsafe_allow_html=True)
    
    formacao_resultados, carga_analise, hidro_analise = analisar_formacao_preco_pld(core)
    
    st.markdown(f'<div class="pld-analysis-box">', unsafe_allow_html=True)
    st.markdown(f"### 📊 Comportamento do PLD")
    
    col1, col2 = st.columns(2)
    
    with col1:
        mcp = core.get("mcp_economico", {})
        adv = core.get("advanced_metrics", {})
        corr = mcp.get("correlacoes", {})
        
        corr_carga = adv.get("correlacoes", {}).get("pld_vs_carga_liquida")
        if corr_carga is None:
            corr_carga = corr.get("pld_vs_carga")

        corr_hidro = adv.get("correlacoes", {}).get("pld_vs_ear_mensal")
        if corr_hidro is None:
            corr_hidro = corr.get("pld_vs_hidraulica")
        
        st.metric("PLD vs Carga Líquida", f"{corr_carga:.2f}" if corr_carga is not None else "—")
        st.caption(carga_analise)
        
    with col2:
        st.metric("PLD vs EAR (mensal)", f"{corr_hidro:.2f}" if corr_hidro is not None else "—")
        st.caption(hidro_analise)
    
    st.markdown("---")
    st.markdown(f"### 📈 **Análise Integrada**")
    
    severidade = formacao_resultados["severidade"]
    if severidade == "critical":
        st.error(f"🚨 {formacao_resultados['analise']}")
    elif severidade == "warning":
        st.warning(f"⚠️ {formacao_resultados['analise']}")
    else:
        st.info(f"ℹ️ {formacao_resultados['analise']}")
    
    if formacao_resultados["recomendacao"]:
        st.markdown(f"**Recomendação:** {formacao_resultados['recomendacao']}")
    
    st.markdown('</div>', unsafe_allow_html=True)

    # =========================================================================
    # NOVA CAMADA FÍSICO-ECONÔMICA (ADVANCED METRICS)
    # =========================================================================
    st.markdown('<div class="section-title">🧠 Aderência Físico-Econômica e Regime Estrutural</div>', unsafe_allow_html=True)
    adv = core.get("advanced_metrics", {})

    if adv:
        ader = adv.get("aderencia_fisico_economica", {})
        capr = adv.get("capacidade_operativa_real", {})
        cls = adv.get("classificacoes", {})
        idxr = adv.get("indices_renovaveis", {})

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("%GFOM", f"{ader.get('gfom_pct'):.2f}%" if ader.get("gfom_pct") is not None else "—")
            st.caption("Σ val_verifgfom / Σ val_verifgeracao")
        with c2:
            st.metric("GFOM × PLD", f"{ader.get('gfom_vs_pld_corr'):.2f}" if ader.get("gfom_vs_pld_corr") is not None else "—")
            st.caption(ader.get("gfom_vs_pld_cenario", "—"))
        with c3:
            st.metric("Curtailment", cls.get("curtailment_estrutural_vs_eletrico", "—"))
            st.caption("Estrutural vs elétrico vs operacional")
        with c4:
            st.metric("Stress Operacional", f"{capr.get('stress_operacional_medio'):.3f}" if capr.get("stress_operacional_medio") is not None else "—")
            st.caption("carga / capacidade disponível real")

        c5, c6, c7 = st.columns(3)
        with c5:
            st.metric("IPR médio", f"{idxr.get('ipr_medio'):.3f}" if idxr.get("ipr_medio") is not None else "—")
        with c6:
            st.metric("ISR médio", f"{idxr.get('isr_medio'):.3f}" if idxr.get("isr_medio") is not None else "—")
        with c7:
            st.metric("Regime abundância", "Sim" if adv.get("regime_abundancia") else "Não" if adv.get("regime_abundancia") is not None else "—")

        regime_anual = adv.get("mudanca_regime_historica_anual", {})
        if regime_anual:
            st.markdown("**Mudança de regime histórica (anual):**")
            df_reg = pd.DataFrame(
                [{"Ano": k, "Regime": v} for k, v in regime_anual.items()]
            ).sort_values("Ano")
            st.dataframe(df_reg, use_container_width=True, hide_index=True)

        margem_media_m = capr.get("margem_operativa_media_mensal", {})
        margem_p5_m = capr.get("margem_operativa_p5_mensal", {})
        if margem_media_m or margem_p5_m:
            rows = sorted(set(list(margem_media_m.keys()) + list(margem_p5_m.keys())))
            df_marg = pd.DataFrame({
                "Mes": rows,
                "Margem média": [margem_media_m.get(r) for r in rows],
                "Margem p5": [margem_p5_m.get(r) for r in rows],
            })
            st.markdown("**Margem operativa real (mensal):**")
            st.dataframe(df_marg, use_container_width=True, hide_index=True)
    else:
        st.info("Métricas avançadas indisponíveis no core.")

    # =========================================================================
    # ANÁLISE TÉRMICA COM DUPLA PERSPECTIVA - REVISADA
    # =========================================================================
    st.markdown('<div class="section-title">🔥 Análise Térmica - Dupla Perspectiva</div>', unsafe_allow_html=True)
    
    thermal = core.get("thermal_analysis", {})
    
    if thermal:
        # Informação de versão da análise
        metadata = core.get("metadata", {})
        if metadata.get("correcao_conceitual"):
            st.success("✅ CVU alto vs PLD baixo = FOLGA (não risco)")
        
        # =============================================
        # PERSPECTIVA DO SISTEMA (MODICIDADE TARIFÁRIA)
        # =============================================
        st.markdown("### 🏭 **Perspectiva do Sistema**")
        st.markdown('<span class="perspectiva-badge badge-sistema">Modicidade Tarifária</span>', unsafe_allow_html=True)
        
        analise_sistema = thermal.get("analise_sistema", {})
        contexto_hidrologico = thermal.get("contexto_hidrologico", {})
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Razão CVU/PLD
            indicadores = thermal.get("indicadores_quantitativos", {})
            percentual_cvu_pld = indicadores.get("percentual_cvu_pld")
            percentual_fmt = formatar_percentual_cvu_pld(percentual_cvu_pld)
            
            st.metric("CVU/PLD", percentual_fmt, 
                     delta=analise_sistema.get("classificacao", "").replace('_', ' ').title())
            st.caption(interpretar_razao_cvu_pld(percentual_cvu_pld))
        
        with col2:
            # Margem de segurança do sistema
            margem_seguranca = indicadores.get("margem_seguranca_sistema")
            margem_fmt = f"{margem_seguranca:.1f}%" if margem_seguranca is not None else "—"
            
            st.metric("Margem Sistema", margem_fmt)
            st.caption("(PLD-CVU)/PLD")
        
        with col3:
            # Margem vs teto
            margem_teto = indicadores.get("margem_vs_teto")
            margem_teto_fmt = f"{margem_teto:.1f}%" if margem_teto is not None else "—"
            
            st.metric("Margem vs Teto", margem_teto_fmt)
            st.caption("Segurança regulatória")
        
        with col4:
            # Dependência térmica efetiva
            dependencia = indicadores.get("dependencia_termica_efetiva")
            dependencia_fmt = f"{dependencia:.2f}" if dependencia is not None else "—"
            
            st.metric("Dependência", dependencia_fmt)
            st.caption("CVU>80% × (1-EAR)")
        
        # Descrição e recomendação do sistema
        if analise_sistema.get("descricao"):
            st.markdown('<div class="card-perspectiva card-sistema">', unsafe_allow_html=True)
            st.markdown(f"**📋 Análise do Sistema:** {analise_sistema['descricao']}")
            if analise_sistema.get("recomendacao"):
                st.markdown(f"**🎯 Recomendação:** {analise_sistema['recomendacao']}")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # =============================================
        # PERSPECTIVA DO GERADOR TÉRMICO
        # =============================================
        st.markdown("### ⚡ **Perspectiva do Gerador Térmico**")
        st.markdown('<span class="perspectiva-badge badge-gerador">Viabilidade Econômica</span>', unsafe_allow_html=True)
        
        analise_gerador = thermal.get("analise_gerador", {})
        dados_referencia = thermal.get("dados_referencia", {})
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Spread absoluto
            spread = analise_gerador.get("spread_absoluto")
            spread_fmt = f"R$ {spread:.1f}" if spread is not None else "—"
            
            st.metric("Spread", spread_fmt, 
                     delta=analise_gerador.get("perspectiva_gerador", "").title())
            st.caption("PLD - CVU")
        
        with col2:
            # Viabilidade econômica
            viabilidade = analise_gerador.get("viabilidade_economica")
            if viabilidade is True:
                viabilidade_fmt = "✅ Econômica"
            elif viabilidade is False:
                viabilidade_fmt = "🔄 Estrutural"
            else:
                viabilidade_fmt = "—"
            
            st.metric("Viabilidade", viabilidade_fmt)
            st.caption("Perspectiva do gerador")
        
        with col3:
            # Valores absolutos
            pld_medio = dados_referencia.get("pld_medio")
            cvu_medio = dados_referencia.get("cvu_medio")
            
            st.metric("PLD vs CVU", 
                     f"R$ {pld_medio:.1f}" if pld_medio else "—",
                     delta=f"CVU: R$ {cvu_medio:.1f}" if cvu_medio else "—")
            st.caption("Valores absolutos")
        
        # Descrição da perspectiva do gerador
        if analise_gerador.get("descricao"):
            st.markdown('<div class="card-perspectiva card-gerador">', unsafe_allow_html=True)
            st.markdown(f"**📋 Perspectiva do Gerador:** {analise_gerador['descricao']}")
            
            # Contexto hídrico
            if contexto_hidrologico.get("interpretacao"):
                st.markdown(f"**💧 Contexto Hídrico:** {contexto_hidrologico['interpretacao']}")
            st.markdown('</div>', unsafe_allow_html=True)
        
    else:
        st.warning("Dados de análise térmica não disponíveis.")

    # =========================================================================
    # RESUMO OPERACIONAL (ENERGIA AGORA)
    # =========================================================================
    st.markdown('<div class="section-title">📋 Resumo Operacional (Energia Agora)</div>', unsafe_allow_html=True)

    gen = core.get("operacao", {}).get("generation", {})
    
    with st.container():
        st.markdown('<div class="resumo-operacional">', unsafe_allow_html=True)
        
        if gen:
            st.markdown("### ⚡ Distribuição da Geração do SIN")
            
            # Mapear as 5 fontes do SIN
            fontes_sin = {
                "hidraulica": {"nome": "Hidráulica", "icone": "💧", "cor": "#3b82f6"},
                "termica": {"nome": "Térmica", "icone": "🔥", "cor": "#ef4444"},
                "eolica": {"nome": "Eólica", "icone": "🌪️", "cor": "#22c55e"},
                "solar": {"nome": "Solar", "icone": "☀️", "cor": "#f59e0b"},
                "nuclear": {"nome": "Nuclear", "icone": "⚛️", "cor": "#a855f7"}
            }
            
            # Coletar dados apenas das fontes do SIN
            dados_fontes = {}
            total_sin = 0
            
            for fonte_key, fonte_info in fontes_sin.items():
                # Buscar dados específicos do SIN
                sin_key = f"sin_{fonte_key}"
                fonte_data = gen.get(sin_key) or gen.get(fonte_key)
                
                if fonte_data:
                    media_mw = fonte_data.get("media", 0)
                    dados_fontes[fonte_key] = {
                        **fonte_info,
                        "media_mw": media_mw,
                        "rampa_max": fonte_data.get("rampa_max", 0)
                    }
                    total_sin += media_mw
            
            if dados_fontes and total_sin > 0:
                # Calcular percentuais
                for fonte_key in dados_fontes:
                    dados_fontes[fonte_key]["percentual"] = (dados_fontes[fonte_key]["media_mw"] / total_sin * 100)
                
                # Ordenar por percentual (maior primeiro)
                fontes_ordenadas = sorted(
                    dados_fontes.items(),
                    key=lambda x: x[1]["percentual"],
                    reverse=True
                )
                
                # Mostrar total em uma coluna
                fontes_lista = []
                for fonte_key, fonte_info in fontes_sin.items():
                    if fonte_key in dados_fontes:
                        fontes_lista.append(f"{fonte_info['icone']} {fonte_info['nome']}")
                
                fontes_texto = " + ".join(fontes_lista)
                
                st.markdown(f"""
                <div style="text-align: center; padding: 1.5rem; background: rgba(30, 58, 138, 0.15); border-radius: 10px; margin: 1rem 0;">
                    <div style="font-size: 0.9rem; color: #9ca3af; margin-bottom: 8px;">Geração Total SIN</div>
                    <div style="font-weight: 700; font-size: 1.5rem; color: #60a5fa; margin-bottom: 8px;">{total_sin:,.0f} MW</div>
                    <div style="font-size: 0.85rem; color: #9ca3af;">Potência total de: {fontes_texto}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Mostrar métricas para cada fonte
                st.markdown("**📊 Participação por Fonte:**")
                
                # Criar 5 colunas para as 5 fontes
                cols = st.columns(5)
                
                for idx, (fonte_key, dados) in enumerate(fontes_ordenadas):
                    with cols[idx]:
                        percentual = dados["percentual"]
                        media_mw = dados["media_mw"]
                        icone = dados["icone"]
                        
                        st.metric(
                            label=f"{icone} {dados['nome']}",
                            value=f"{percentual:.1f}%",
                            delta=f"{media_mw:,.0f} MW",
                            delta_color="normal"
                        )
                
            else:
                st.info("""
                ### ⚠️ Sem Dados de Geração
                
                Não foi possível calcular a distribuição da geração do SIN.
                
                **Verifique se os dados estão disponíveis:**
                1. Hidráulica (SIN_Hidraulica)
                2. Térmica (SIN_Termica)  
                3. Eólica (SIN_Eolica)
                4. Solar (SIN_Solar)
                5. Nuclear (SIN_Nuclear)
                """)
            
        else:
            st.info("### ⚠️ Dados Indisponíveis")
        
        st.markdown('</div>', unsafe_allow_html=True)

    # =========================================================================
    # VISUALIZAÇÕES DE GERAÇÃO E CARGA
    # =========================================================================
    st.markdown("### ⚙️ Geração Horária")
    if gen:
        fig = go.Figure()
        
        # Dicionário para abreviação de regiões
        abreviacoes_regioes = {
            "sudesteecentrooeste": "SE/CO",
            "norte": "N",
            "sul": "S", 
            "nordeste": "NE",
            "sin": "SIN"
        }
        
        # Dicionário para nomes das fontes
        nomes_fontes = {
            "hidraulica": "HIDR",
            "termica": "TERM",
            "eolica": "EOL",
            "solar": "SOL",
            "nuclear": "NUC"
        }
        
        for fonte_key, dados in gen.items():
            # Ignorar dados totais do SIN
            if fonte_key.startswith("sin_"):
                continue
            
            df = pd.DataFrame(dados.get("serie", []))
            
            if df.empty:
                continue
                
            # Extrair região e tipo de fonte
            parts = fonte_key.split("_")
            if len(parts) >= 2:
                # Última parte é o tipo de fonte
                tipo_fonte = parts[-1]
                fonte_nome = nomes_fontes.get(tipo_fonte, tipo_fonte.upper())
                
                # Restante é a região
                regiao_key = "_".join(parts[:-1])
                regiao_nome = abreviacoes_regioes.get(regiao_key, regiao_key.upper())
                
                # Nome da legenda compacto
                nome_legenda = f"{regiao_nome} - {fonte_nome}"
            else:
                nome_legenda = fonte_key.upper()
            
            fig.add_trace(
                go.Bar(
                    x=df["instante"],
                    y=df["geracao"],
                    name=nome_legenda,
                    hoverinfo="x+y+name",
                    hovertemplate="%{x|%H:%M}<br>%{y:,.0f} MW<extra>%{name}</extra>"
                )
            )
        
        fig.update_layout(
            template="plotly_dark",
            title="Geração por Fonte e Região",
            xaxis_title="Hora",
            yaxis_title="MW",
            barmode="stack",
            height=350,
            legend=dict(
                orientation="h",  # Horizontal
                yanchor="top",    # Ancora no TOPO
                y=-0.45,          # MAIS PARA BAIXO (2 quebras de linha)
                xanchor="center", # Centralizado
                x=0.5,
                font=dict(size=10),
                bgcolor="rgba(0,0,0,0.5)",  # Fundo semi-transparente
                bordercolor="rgba(255,255,255,0.2)",
                borderwidth=1
            ),
            margin=dict(t=50, b=150, l=50, r=80),  # Margem direita maior (r=80)
            xaxis=dict(
                tickformat="%H:%M",
                tickangle=0,  # Inclinar labels para melhor leitura
                tickfont=dict(size=10),
                showgrid=True,
                gridcolor="rgba(255,255,255,0.1)",
                range=[None, None],  # Deixar espaço no final
                rangeslider=dict(visible=False)
            ),
            yaxis=dict(
                tickformat=",",
                tickfont=dict(size=10),
                showgrid=True,
                gridcolor="rgba(255,255,255,0.1)",
                zerolinecolor="rgba(255,255,255,0.2)"
            )
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Dados de geração não disponíveis.")
    
    st.markdown("### 🔌 Carga Horária")
    load = core.get("operacao", {}).get("load", {})
    if load:
        fig = go.Figure()
        
        for area, dados in load.items():
            # Ignorar carga total do SIN
            if area.lower() == "sin":
                continue
            
            df = pd.DataFrame(dados.get("serie", []))
            
            if df.empty:
                continue
            
            # Aplicar abreviação para a região
            area_nome = abreviacoes_regioes.get(area.lower(), area.upper())
            
            fig.add_trace(
                go.Bar(
                    x=df["instante"],
                    y=df["carga"],
                    name=area_nome,
                    hoverinfo="x+y+name",
                    hovertemplate="%{x|%H:%M}<br>%{y:,.0f} MW<extra>%{name}</extra>"
                )
            )
        
        fig.update_layout(
            template="plotly_dark",
            title="Carga por Submercado",
            xaxis_title="Hora",
            yaxis_title="MW",
            barmode="stack",
            height=350,
            legend=dict(
                orientation="h",  # Horizontal
                yanchor="top",    # Ancora no TOPO
                y=-0.45,          # MAIS PARA BAIXO
                xanchor="center", # Centralizado
                x=0.5,
                font=dict(size=10),
                bgcolor="rgba(0,0,0,0.5)",
                bordercolor="rgba(255,255,255,0.2)",
                borderwidth=1
            ),
            margin=dict(t=50, b=150, l=50, r=80),  # Margem direita maior
            xaxis=dict(
                tickformat="%H:%M",
                tickangle=0,
                tickfont=dict(size=10),
                showgrid=True,
                gridcolor="rgba(255,255,255,0.1)",
                range=[None, None]
            ),
            yaxis=dict(
                tickformat=",",
                tickfont=dict(size=10),
                showgrid=True,
                gridcolor="rgba(255,255,255,0.1)",
                zerolinecolor="rgba(255,255,255,0.2)"
            )
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Dados de carga não disponíveis.")

    # =========================================================================
    # GRAFICO PLD POR SUBMERCADO
    # =========================================================================
    st.markdown('<div class="section-title">🌐 PLD Horário por Submercado</div>', unsafe_allow_html=True)

    pld_ts = core.get("prices", {}).get("pld_horario_7d", {})

    if pld_ts:
        fig = go.Figure()

        for sm, serie in pld_ts.items():

            if isinstance(serie, dict):
                df = pd.DataFrame(
                    [{"instante": k, "pld": v} for k, v in serie.items()]
                )
            else:
                df = pd.DataFrame(serie)

            if df.empty or "instante" not in df.columns:
                continue

            df["instante"] = pd.to_datetime(df["instante"], errors="coerce")
            df = df.dropna(subset=["instante"])

            fig.add_trace(
                go.Scatter(
                    x=df["instante"],
                    y=df["pld"],
                    mode="lines",
                    name=sm,
                )
            )

        fig.update_layout(
            template="plotly_dark",
            xaxis_title="Data",
            yaxis_title="R$/MWh",
            title="Últimos 7 dias",
            height=300
        )

        st.plotly_chart(fig, use_container_width=True)

    # PREMIUM - análise personalizada
    premium_result = None  # placeholder: fluxo premium ainda não conectado nesta versão
    st.markdown("---")
    st.header("👤 PREMIUM — Visão Personalizada")
    if premium_result is None:
        st.info("Envie o template Excel no sidebar para ativar a visão PREMIUM.")
    else:
        st.info("Série temporal de PLD indisponível.")
    
    # =========================================================================
    # MCP ECONÔMICO
    # =========================================================================
    st.markdown('<div class="section-title">📊 MCP Econômico</div>', unsafe_allow_html=True)
    mcp = core.get("mcp_economico", {})

    if mcp:
        adv = core.get("advanced_metrics", {})
        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown(
            f"""
<div class="insight-card">
<h4>Regime do MCP</h4>
<div class="kpi-value">{mcp.get("regime_mcp", "—")}</div>
<p>{mcp.get("descricao", "")}</p>
</div>
""",
            unsafe_allow_html=True,
            )

        with c2:
            correlacoes = mcp.get("correlacoes", {})
            corr_carga_liq = adv.get("correlacoes", {}).get("pld_vs_carga_liquida")
            corr_show = corr_carga_liq if corr_carga_liq is not None else correlacoes.get("pld_vs_carga")
            st.metric(
                "PLD vs Carga Líquida",
                f"{corr_show:.2f}" if corr_show is not None else "—"
            )

        with c3:
            corr_ear_m = adv.get("correlacoes", {}).get("pld_vs_ear_mensal")
            corr_hshow = corr_ear_m if corr_ear_m is not None else correlacoes.get("pld_vs_hidraulica")
            st.metric(
                "PLD vs EAR (mensal)",
                f"{corr_hshow:.2f}" if corr_hshow is not None else "—"
            )
    else:
        st.info("Dados de MCP indisponíveis.")

    # =========================================================================
    # LIMITES REGULATÓRIOS
    # =========================================================================
    st.markdown('<div class="section-title">📏 Limites Regulatórios do PLD (2026)</div>', unsafe_allow_html=True)
    
    prices = core.get("prices", {})
    limites = prices.get("limites_regulatorios", {})
    pld_medio = prices.get("pld_medio")
    
    if limites and pld_medio:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Piso", f"R$ {limites.get('piso', 58.60):.2f}")
        
        with col2:
            st.metric("PLD Médio", f"R$ {pld_medio:.2f}")
        
        with col3:
            st.metric("Teto Estrutural", f"R$ {limites.get('teto_estrutural', 751.73):.2f}")
        
        with col4:
            st.metric("Teto Horário", f"R$ {limites.get('teto_horario', 1542.23):.2f}")

    # =========================================================================
    # METADATA
    # =========================================================================
    with st.expander("ℹ️ Metadados do CORE"):
        st.json(core.get("metadata", {}))

    st.markdown("---")
    meta = core.get("metadata", {}) if isinstance(core, dict) else {}
    ultima_atualizacao = (
        meta.get("generated_at")
        or core.get("timestamp")
        or "N/A"
    )

    st.caption(f"""
    ⚡ **Kintuadi Energy Platform v2.0** | Dados em tempo real | 
    Última atualização: {ultima_atualizacao} | 
    Desenvolvido para gestores de energia
    """)

if __name__ == "__main__":
    main()
