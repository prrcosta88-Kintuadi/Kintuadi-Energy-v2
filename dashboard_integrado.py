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
from datetime import datetime, timedelta, date
import logging
import streamlit.components.v1 as components
from analises_tecnicas import mostrar_analises_tecnicas
from scripts.core_analysis import build_core_analysis, calcular_indicadores_termicos_revisados
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

def is_mirror_mode() -> bool:
    return os.environ.get("KINTUADI_DASHBOARD_MODE", "integrado").lower() == "espelho"


def load_core_analysis():
    """
    Modo integrado: SEMPRE executa build_core_analysis como primeira ação da sessão.
    Modo espelho: nunca executa build; lê apenas core_analysis_latest.json.
    """
    cached_core = st.session_state.get("core_runtime")
    if isinstance(cached_core, dict) and st.session_state.get("core_built_this_session"):
        return cached_core

    core_file = os.path.join("data", "core_analysis_latest.json")

    # Modo espelho: somente leitura do core persistido
    if is_mirror_mode():
        if isinstance(cached_core, dict):
            return cached_core
        if os.path.exists(core_file):
            try:
                with open(core_file, "r", encoding="utf-8") as f:
                    core = json.load(f)
                if isinstance(core, dict):
                    st.session_state["core_runtime"] = core
                    return core
            except Exception as e:
                logger.warning(f"Falha ao carregar core_analysis_latest.json: {e}")
        logger.error("Modo espelho: core_analysis_latest.json indisponível.")
        return None

    # Modo integrado: build obrigatório no bootstrap da sessão
    raw = load_latest_raw()
    if not raw:
        logger.error("Dados brutos indisponíveis para executar build_core_analysis.")
        return None

    try:
        logger.info("Executando build_core_analysis (ação obrigatória no bootstrap do dashboard_integrado)...")
        core = build_core_analysis(raw, output_dir="data")

        if isinstance(core, dict):
            st.session_state["core_runtime"] = core
            st.session_state["core_built_this_session"] = True
            return core

        logger.error("build_core_analysis retornou estrutura inválida.")
        return None

    except Exception as e:
        logger.error(f"Falha ao executar build_core_analysis: {e}")

        # fallback de leitura local apenas para não derrubar UI
        if os.path.exists(core_file):
            try:
                with open(core_file, "r", encoding="utf-8") as f:
                    core = json.load(f)
                if isinstance(core, dict):
                    st.session_state["core_runtime"] = core
                    return core
            except Exception:
                pass
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


def _compute_monthly_period_correlations(core: Dict[str, Any], dt_ini: date, dt_fim: date) -> Dict[str, Any]:
    """Calcula correlações mensais por período selecionado e histórico total para comparação."""
    result = {
        "ok": False,
        "erro": None,
        "corr_periodo_carga": None,
        "corr_periodo_ear": None,
        "corr_total_carga": None,
        "corr_total_ear": None,
        "meses_no_periodo": 0,
    }

    try:
        # PLD mensal a partir do bloco ccee.data
        rows = ((core.get("ccee") or {}).get("data") or []) if isinstance(core, dict) else []
        if not isinstance(rows, list) or not rows:
            result["erro"] = "PLD indisponível no core."
            return result

        df = pd.DataFrame(rows)
        required = {"mes_referencia", "dia", "hora", "pld_hora"}
        if not required.issubset(df.columns):
            result["erro"] = "Estrutura de PLD incompatível."
            return result

        df["mes_referencia"] = df["mes_referencia"].astype(str).str.zfill(6)
        df["dia"] = pd.to_numeric(df["dia"], errors="coerce")
        df["hora"] = pd.to_numeric(df["hora"], errors="coerce")
        df["pld_hora"] = pd.to_numeric(df["pld_hora"], errors="coerce")
        df["instante"] = (
            pd.to_datetime(df["mes_referencia"] + "01", format="%Y%m%d", errors="coerce", utc=True).dt.tz_localize(None)
            + pd.to_timedelta(df["dia"].fillna(1) - 1, unit="D")
            + pd.to_timedelta(df["hora"].fillna(0), unit="h")
        )
        df = df.dropna(subset=["instante", "pld_hora"])
        pld_m = df.set_index("instante")["pld_hora"].resample("ME").mean().dropna()

        # EAR mensal já pronto no advanced_metrics
        adv = core.get("advanced_metrics", {}) if isinstance(core, dict) else {}
        ear_dict = adv.get("ear_media_mensal") or {}
        ear_m = pd.Series({pd.to_datetime(k + "-01", errors="coerce") + pd.offsets.MonthEnd(0): v for k, v in ear_dict.items()})
        ear_m = pd.to_numeric(ear_m, errors="coerce").dropna().sort_index()

        # Carga líquida mensal (derivada de operacao)
        op = core.get("operacao", {}) if isinstance(core, dict) else {}
        gen = op.get("generation", {}) if isinstance(op, dict) else {}
        load = op.get("load", {}) if isinstance(op, dict) else {}

        def _series_from_records(records, val_key):
            if not isinstance(records, list) or not records:
                return pd.Series(dtype=float)
            dfr = pd.DataFrame(records)
            if "instante" not in dfr.columns or val_key not in dfr.columns:
                return pd.Series(dtype=float)
            dfr["instante"] = pd.to_datetime(dfr["instante"], errors="coerce", utc=True).dt.tz_localize(None)
            dfr[val_key] = pd.to_numeric(dfr[val_key], errors="coerce")
            dfr = dfr.dropna(subset=["instante", val_key])
            return dfr.set_index("instante")[val_key].sort_index()

        carga = _series_from_records(((load.get("sin") or {}).get("serie") or []), "carga")
        solar_key = next((k for k in gen.keys() if "solar" in str(k).lower()), None)
        eolica_key = next((k for k in gen.keys() if "eolica" in str(k).lower()), None)
        solar = _series_from_records(((gen.get(solar_key) or {}).get("serie") or []), "geracao") if solar_key else pd.Series(dtype=float)
        eolica = _series_from_records(((gen.get(eolica_key) or {}).get("serie") or []), "geracao") if eolica_key else pd.Series(dtype=float)

        carga_liq_m = pd.Series(dtype=float)
        if not carga.empty:
            renov = solar.add(eolica, fill_value=0)
            carga_liq = carga.sub(renov, fill_value=float("nan"))
            carga_liq_m = carga_liq.resample("ME").mean().dropna()

        # Correlações históricas mensais
        m_total = pd.DataFrame({"pld": pld_m, "ear": ear_m, "carga": carga_liq_m}).sort_index()
        df_total_ear = m_total[["pld", "ear"]].dropna()
        df_total_carga = m_total[["pld", "carga"]].dropna()
        result["corr_total_ear"] = float(df_total_ear["pld"].corr(df_total_ear["ear"])) if len(df_total_ear) >= 3 else None
        result["corr_total_carga"] = float(df_total_carga["pld"].corr(df_total_carga["carga"])) if len(df_total_carga) >= 3 else None

        # Recorte do período selecionado (mensal)
        m1 = pd.Timestamp(dt_ini).replace(day=1)
        m2 = pd.Timestamp(dt_fim).replace(day=1) + pd.offsets.MonthEnd(0)
        m_per = m_total[(m_total.index >= m1) & (m_total.index <= m2)]
        result["meses_no_periodo"] = int(len(m_per.index.unique()))

        if result["meses_no_periodo"] < 3:
            result["erro"] = "Selecione um período com pelo menos 3 meses."
            return result

        df_per_ear = m_per[["pld", "ear"]].dropna()
        df_per_carga = m_per[["pld", "carga"]].dropna()
        result["corr_periodo_ear"] = float(df_per_ear["pld"].corr(df_per_ear["ear"])) if len(df_per_ear) >= 3 else None
        result["corr_periodo_carga"] = float(df_per_carga["pld"].corr(df_per_carga["carga"])) if len(df_per_carga) >= 3 else None

        result["ok"] = True
        return result
    except Exception as e:
        result["erro"] = str(e)
        return result


def _compute_thermal_by_period(core: Dict[str, Any], dt_ini: date, dt_fim: date) -> Optional[Dict[str, Any]]:
    """Recalcula análise térmica para o período selecionado."""
    try:
        if dt_fim < dt_ini:
            return None

        # PLD médio do período (a partir de ccee.data)
        rows = ((core.get("ccee") or {}).get("data") or [])
        if not isinstance(rows, list) or not rows:
            return None
        df = pd.DataFrame(rows)
        req = {"mes_referencia", "dia", "hora", "pld_hora"}
        if not req.issubset(df.columns):
            return None
        df["mes_referencia"] = df["mes_referencia"].astype(str).str.zfill(6)
        df["dia"] = pd.to_numeric(df["dia"], errors="coerce")
        df["hora"] = pd.to_numeric(df["hora"], errors="coerce")
        df["pld_hora"] = pd.to_numeric(df["pld_hora"], errors="coerce")
        df["instante"] = (
            pd.to_datetime(df["mes_referencia"] + "01", format="%Y%m%d", errors="coerce", utc=True).dt.tz_localize(None)
            + pd.to_timedelta(df["dia"].fillna(1) - 1, unit="D")
            + pd.to_timedelta(df["hora"].fillna(0), unit="h")
        )
        dfi = df.dropna(subset=["instante", "pld_hora"])
        dfi = dfi[(dfi["instante"] >= pd.Timestamp(dt_ini)) & (dfi["instante"] <= pd.Timestamp(dt_fim) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))]
        if dfi.empty:
            return None
        pld_medio = float(dfi["pld_hora"].mean())

        # CVU médio semanal no período (se disponível); fallback para valor de referência do core
        thermal_base = core.get("thermal_analysis", {}) if isinstance(core, dict) else {}
        cvu_diario = thermal_base.get("cvu_diario", {}) if isinstance(thermal_base, dict) else {}
        cvu_semanal = thermal_base.get("cvu_semanal", {}) if isinstance(thermal_base, dict) else {}
        cvu_medio = None
        if isinstance(cvu_diario, dict) and cvu_diario:
            sd = pd.Series({pd.to_datetime(k, errors="coerce"): v for k, v in cvu_diario.items()})
            sd = pd.to_numeric(sd, errors="coerce").dropna()
            sd = sd[(sd.index >= pd.Timestamp(dt_ini)) & (sd.index <= pd.Timestamp(dt_fim))]
            if not sd.empty:
                cvu_medio = float(sd.mean())

        if cvu_medio is None and isinstance(cvu_semanal, dict) and cvu_semanal:
            sw = pd.Series({pd.to_datetime(k, errors="coerce"): v for k, v in cvu_semanal.items()})
            sw = pd.to_numeric(sw, errors="coerce").dropna()
            sw = sw[(sw.index >= pd.Timestamp(dt_ini)) & (sw.index <= pd.Timestamp(dt_fim))]
            if not sw.empty:
                cvu_medio = float(sw.mean())

        if cvu_medio is None:
            cvu_medio = ((thermal_base.get("dados_referencia") or {}).get("cvu_medio")) if isinstance(thermal_base, dict) else None

        # EAR médio do período (diário se disponível)
        adv = core.get("advanced_metrics", {}) if isinstance(core, dict) else {}
        ear_diario = adv.get("ear_media_diaria", {}) if isinstance(adv, dict) else {}
        ear_medio = None
        if isinstance(ear_diario, dict) and ear_diario:
            se = pd.Series({pd.to_datetime(k, errors="coerce"): v for k, v in ear_diario.items()})
            se = pd.to_numeric(se, errors="coerce").dropna()
            se = se[(se.index >= pd.Timestamp(dt_ini)) & (se.index <= pd.Timestamp(dt_fim))]
            if not se.empty:
                ear_medio = float(se.mean())
        if ear_medio is None:
            ear_medio = ((core.get("hydrology") or {}).get("ear_medio")) if isinstance(core, dict) else None

        return calcular_indicadores_termicos_revisados(pld_medio=pld_medio, cvu_medio=cvu_medio, ear_medio=ear_medio)
    except Exception:
        return None


def _normalize_submercado_dashboard(value: Any) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip().upper().replace("/", "").replace("-", "").replace(" ", "")
    mapping = {
        "1": "SUDESTE", "2": "SUL", "3": "NORDESTE", "4": "NORTE",
        "N": "NORTE", "NE": "NORDESTE", "SE": "SUDESTE", "SECO": "SUDESTE", "S": "SUL",
        "NORTE": "NORTE", "NORDESTE": "NORDESTE", "SUDESTE": "SUDESTE", "SUL": "SUL",
    }
    return mapping.get(v)


def _classificar_cenario_horario(pld: Optional[float], ear_mensal: Optional[float], termica_mensal: Optional[float], pld_medio_global: Optional[float]) -> str:
    if pld is None or ear_mensal is None:
        return "dados_insuficientes"
    if pld >= 785.27 * 0.8 and ear_mensal < 50:
        return "estresse_hidrico"
    if pld <= 57.31 * 1.2 and ear_mensal > 65:
        return "abundancia_hidrica"
    if termica_mensal is not None and termica_mensal > 25 and pld_medio_global is not None and pld > pld_medio_global:
        return "pressao_termica"
    return "equilibrio_operacional"


def build_hourly_scenario_table(core: Dict[str, Any], selected_day: datetime.date, submercado: str = "SIN") -> pd.DataFrame:
    ccee = core.get("ccee", {}) if isinstance(core, dict) else {}
    rows = ccee.get("data", []) if isinstance(ccee, dict) else []
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    required = {"mes_referencia", "dia", "hora", "pld_hora", "submercado"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    df["mes_referencia"] = df["mes_referencia"].astype(str).str.zfill(6)
    df["dia"] = pd.to_numeric(df["dia"], errors="coerce")
    df["hora"] = pd.to_numeric(df["hora"], errors="coerce")
    df["pld_hora"] = pd.to_numeric(df["pld_hora"], errors="coerce")
    df["submercado_norm"] = df["submercado"].map(_normalize_submercado_dashboard)

    df["instante"] = (
        pd.to_datetime(df["mes_referencia"] + "01", format="%Y%m%d", errors="coerce")
        + pd.to_timedelta(df["dia"].fillna(1) - 1, unit="D")
        + pd.to_timedelta(df["hora"].fillna(0), unit="h")
    )
    df = df.dropna(subset=["instante", "pld_hora"])

    if submercado != "SIN":
        df = df[df["submercado_norm"] == submercado]

    day_ts = pd.Timestamp(selected_day)
    df = df[df["instante"].dt.floor("D") == day_ts]
    if df.empty:
        return pd.DataFrame()

    hourly = df.groupby(df["instante"].dt.floor("h"))["pld_hora"].mean().reset_index()
    hourly = hourly.rename(columns={"pld_hora": "pld_hora_medio"})

    adv = core.get("advanced_metrics", {}) if isinstance(core, dict) else {}
    month_key = day_ts.strftime("%Y-%m")
    day_key = day_ts.strftime("%Y-%m-%d")
    ear_mensal = (adv.get("ear_media_diaria") or {}).get(day_key)
    ena_mensal = (adv.get("ena_media_diaria") or {}).get(day_key)

    termica_mensal = None
    for row in (adv.get("matriz_cenario_mensal") or []):
        if isinstance(row, dict) and row.get("mes") == month_key:
            termica_mensal = row.get("percentual_termica_medio")
            break

    pld_medio_global = (core.get("prices") or {}).get("pld_medio")

    hourly["ear_mensal"] = ear_mensal
    hourly["ena_mensal"] = ena_mensal
    hourly["percentual_termica_mensal"] = termica_mensal
    hourly["cenario"] = hourly["pld_hora_medio"].apply(
        lambda p: _classificar_cenario_horario(
            float(p) if pd.notna(p) else None,
            float(ear_mensal) if ear_mensal is not None else None,
            float(termica_mensal) if termica_mensal is not None else None,
            float(pld_medio_global) if pld_medio_global is not None else None,
        )
    )

    hourly = hourly.rename(columns={"instante": "hora"})
    return hourly


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    # Carregar CSS dinâmico
    css = load_custom_css()
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="collapsedControl"] {display:none !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )

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

    st.markdown("**Comparar correlações mensais por período selecionado (mín. 3 meses):**")
    pr1, pr2, pr3 = st.columns([1, 1, 2])
    with pr1:
        corr_ini = st.date_input("Início (mensal)", value=datetime.now().date().replace(day=1) - timedelta(days=180), key="corr_period_ini")
    with pr2:
        corr_fim = st.date_input("Fim (mensal)", value=datetime.now().date(), key="corr_period_fim")
    with pr3:
        run_corr = st.button("Comparar correlações do período", key="btn_corr_period")

    if run_corr:
        cmp = _compute_monthly_period_correlations(core, corr_ini, corr_fim)
        if not cmp.get("ok"):
            st.warning(cmp.get("erro") or "Não foi possível calcular as correlações por período.")
        else:
            cpa, cpb = st.columns(2)
            with cpa:
                st.metric("PLD vs Carga Líquida (período)", f"{cmp.get('corr_periodo_carga'):.2f}" if cmp.get("corr_periodo_carga") is not None else "—")
                st.caption(f"Histórico total mensal: {cmp.get('corr_total_carga'):.2f}" if cmp.get("corr_total_carga") is not None else "Histórico total mensal: —")
            with cpb:
                st.metric("PLD vs EAR (período)", f"{cmp.get('corr_periodo_ear'):.2f}" if cmp.get("corr_periodo_ear") is not None else "—")
                st.caption(f"Histórico total mensal: {cmp.get('corr_total_ear'):.2f}" if cmp.get("corr_total_ear") is not None else "Histórico total mensal: —")
    
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

        # Período default: último mês fechado (cards c1..c7)
        today = datetime.now().date()
        first_day_this_month = today.replace(day=1)
        last_closed_end = first_day_this_month - timedelta(days=1)
        last_closed_start = last_closed_end.replace(day=1)

        if "adv_period_ini" not in st.session_state:
            st.session_state["adv_period_ini"] = last_closed_start
        if "adv_period_fim" not in st.session_state:
            st.session_state["adv_period_fim"] = last_closed_end

        p1, p2, p3 = st.columns([1, 1, 1])
        with p1:
            dt_ini = st.date_input("Início", value=st.session_state["adv_period_ini"], key="adv_period_ini")
        with p2:
            dt_fim = st.date_input("Fim", value=st.session_state["adv_period_fim"], key="adv_period_fim")
        with p3:
            run_period = st.button("Verificar métricas", key="btn_verificar_metricas")

        if run_period:
            st.session_state["adv_period_ini"] = dt_ini
            st.session_state["adv_period_fim"] = dt_fim

        dt_ini = st.session_state["adv_period_ini"]
        dt_fim = st.session_state["adv_period_fim"]
        st.caption(f"Período ativo dos cards: **{dt_ini.strftime('%Y-%m-%d')}** até **{dt_fim.strftime('%Y-%m-%d')}**")

        mtx_d = pd.DataFrame(adv.get("matriz_cenario_diaria", []))
        if not mtx_d.empty and "dia" in mtx_d.columns:
            mtx_d["dia_dt"] = pd.to_datetime(mtx_d["dia"], errors="coerce")
            mtx_d = mtx_d[(mtx_d["dia_dt"] >= pd.Timestamp(dt_ini)) & (mtx_d["dia_dt"] <= pd.Timestamp(dt_fim))]

        def _mean_col(df, col):
            if df.empty or col not in df.columns:
                return None
            v = pd.to_numeric(df[col], errors="coerce").dropna()
            return float(v.mean()) if not v.empty else None

        gfom_pct_show = _mean_col(mtx_d, "gfom_pct") or ader.get("gfom_pct")
        gfom_corr_show = _mean_col(mtx_d, "gfom_vs_pld_corr") if not mtx_d.empty else ader.get("gfom_vs_pld_corr")
        stress_show = _mean_col(mtx_d, "stress_operacional_medio") or capr.get("stress_operacional_medio")
        ipr_show = _mean_col(mtx_d, "ipr_medio") or idxr.get("ipr_medio")
        isr_show = _mean_col(mtx_d, "isr_medio") or idxr.get("isr_medio")

        curt_show = cls.get("curtailment_estrutural_vs_eletrico", "-")
        if not mtx_d.empty and "curtailment_estado" in mtx_d.columns:
            mode_c = mtx_d["curtailment_estado"].dropna()
            if not mode_c.empty:
                curt_show = mode_c.mode().iloc[0]

        abund_show = adv.get("regime_abundancia")
        if not mtx_d.empty and "regime_abundancia" in mtx_d.columns:
            s_ab = mtx_d["regime_abundancia"].dropna()
            if not s_ab.empty:
                abund_show = bool((s_ab == True).mean() >= 0.5)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("%GFOM", f"{gfom_pct_show:.2f}%" if gfom_pct_show is not None else "-")
            st.caption("Média diária no período ativo: ΣGFOM/ΣGeração")
        with c2:
            st.metric("GFOM × PLD", f"{gfom_corr_show:.2f}" if gfom_corr_show is not None else "-")
            st.caption((ader.get("gfom_vs_pld_cenario", "-") or "-") + " | 0E-8 e notação científica tratados como 0.")
        with c3:
            st.metric("Curtailment", curt_show)
            st.caption("Estado dominante diário no período")
        with c4:
            st.metric("Stress Operacional", f"{stress_show:.3f}" if stress_show is not None else "-")
            st.caption("Média diária de carga/capacidade")

        c5, c6, c7 = st.columns(3)
        with c5:
            st.metric("IPR médio", f"{ipr_show:.3f}" if ipr_show is not None else "-")
        with c6:
            st.metric("ISR médio", f"{isr_show:.3f}" if isr_show is not None else "-")
        with c7:
            st.metric("Regime abundância", "Sim" if abund_show else "Não" if abund_show is not None else "-")

        if not mtx_d.empty:
            st.markdown("**Matriz diária das métricas (c1..c7) no período selecionado:**")
            st.dataframe(mtx_d.drop(columns=["dia_dt"], errors="ignore"), width="stretch", hide_index=True)

        regime_trimestral = adv.get("mudanca_regime_historica_trimestral", {})
        if regime_trimestral:
            st.markdown("**Mudança de regime histórica (trimestral):**")
            df_reg = pd.DataFrame(
                [{"Trimestre": k, "Regime": v} for k, v in regime_trimestral.items()]
            ).sort_values("Trimestre")
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
            st.dataframe(df_marg, width="stretch", hide_index=True)

        with st.expander("📘 Conceitos e critérios das métricas avançadas"):
            met = adv.get("metodologia", {})
            st.markdown("**GFOM vs PLD**")
            st.write(met.get("gfom_vs_pld", "GFOM% = GFOM/geração verificada; correlação com PLD horário alinhado."))
            st.markdown("**Margem operativa real (mensal)**")
            st.write(met.get("margem_operativa_real", "Margem média = média horária mensal; Margem p5 = percentil 5% mensal."))
            st.markdown("**Curtailment (operacional/elétrico/estrutural)**")
            st.write(met.get("curtailment", "Critérios operacionais combinando intercâmbio, IPR, EAR e PLD."))
            st.markdown("**IPR / ISR**")
            st.write(met.get("ipr_isr", "IPR e ISR medem penetração renovável em relação à carga e carga líquida."))
            st.markdown("**Regime de abundância**")
            st.write(met.get("regime_abundancia", "Critério baseado em dependência térmica, EAR e PLD."))
            st.markdown("**Mudança de regime (trimestral)**")
            st.write(met.get("mudanca_regime_trimestral", "Classificação trimestral por stress e PLD."))

        st.markdown("**Consulta horária por dia (sem reprocessar o build_core_analysis):**")
        c_sel1, c_sel2 = st.columns([1, 1])
        with c_sel1:
            dia_consulta = st.date_input(
                "Selecione o dia",
                value=datetime.now().date(),
                key="dia_consulta_horaria",
                help="A consulta lê apenas o core_analysis_latest.json carregado.",
            )
        with c_sel2:
            sub_opt = st.selectbox(
                "Submercado",
                options=["SIN", "NORTE", "NORDESTE", "SUDESTE", "SUL"],
                index=0,
                key="submercado_consulta_horaria",
            )

        df_horario = build_hourly_scenario_table(core, dia_consulta, submercado=sub_opt)
        if not df_horario.empty:
            st.dataframe(df_horario, width="stretch", hide_index=True)
        else:
            st.info("Sem dados horários no dia/submercado selecionado dentro do core carregado.")
    else:
        st.info("Métricas avançadas indisponíveis no core.")

    # =========================================================================
    # ANÁLISE TÉRMICA COM DUPLA PERSPECTIVA - REVISADA
    # =========================================================================
    st.markdown('<div class="section-title">🔥 Análise Térmica - Dupla Perspectiva</div>', unsafe_allow_html=True)

    t1, t2, t3 = st.columns([1, 1, 1])
    today = datetime.now().date()
    with t1:
        thermal_ini = st.date_input("Período térmico - início", value=today - timedelta(days=30), key="thermal_period_ini")
    with t2:
        thermal_fim = st.date_input("Período térmico - fim", value=today, key="thermal_period_fim")
    with t3:
        run_thermal = st.button("Verificar análise térmica", key="btn_thermal_period")

    thermal = st.session_state.get("thermal_period_result") if not run_thermal else None
    if run_thermal:
        thermal = _compute_thermal_by_period(core, thermal_ini, thermal_fim)
        st.session_state["thermal_period_result"] = thermal

    if thermal:
        st.caption(f"Análise térmica calculada para o período {thermal_ini.strftime('%Y-%m-%d')} a {thermal_fim.strftime('%Y-%m-%d')}.")
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
        st.info("Selecione o período e clique em **Verificar análise térmica** para exibir os resultados.")

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
