# dashboard_integrado.py - VERSÃO CORRIGIDA E ROBUSTA
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
from datetime import datetime
import os
import glob
import logging

# Configura logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração da página
st.set_page_config(
    page_title="Kintuadi Energy Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS melhorado
st.markdown("""
<style>
    /* Tema escuro */
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    
    /* Cabeçalho */
    .main-header {
        background: linear-gradient(90deg, #00b4d8 0%, #0077b6 100%);
        padding: 2rem;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px rgba(0, 180, 216, 0.3);
    }
    
    /* Cards */
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1.5rem;
        border-left: 4px solid #00b4d8;
        margin: 0.5rem 0;
    }
    
    .metric-card.critical {
        border-left-color: #f44336;
        background: linear-gradient(135deg, rgba(244, 67, 54, 0.1) 0%, rgba(244, 67, 54, 0.05) 100%);
    }
    
    .metric-card.warning {
        border-left-color: #ff9800;
        background: linear-gradient(135deg, rgba(255, 152, 0, 0.1) 0%, rgba(255, 152, 0, 0.05) 100%);
    }
    
    .metric-card.success {
        border-left-color: #4caf50;
        background: linear-gradient(135deg, rgba(76, 175, 80, 0.1) 0%, rgba(76, 175, 80, 0.05) 100%);
    }
    
    .kpi-value {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(90deg, #00b4d8, #0077b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0.5rem 0;
    }
    
    /* Containers */
    .plot-container {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    /* Tabelas */
    .dataframe {
        background-color: rgba(255, 255, 255, 0.05) !important;
        color: white !important;
    }
    
    .dataframe th {
        background-color: rgba(0, 180, 216, 0.2) !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

def load_latest_data():
    """Carrega os dados mais recentes - VERSÃO ROBUSTA"""
    try:
        data_dir = "data"
        
        if not os.path.exists(data_dir):
            st.error("❌ Pasta 'data' não encontrada.")
            return None
        
        # Procura diferentes padrões de arquivos
        patterns = [
            "kintuadi_dashboard_*.json",
            "kintuadi_latest.json", 
            "kintuadi_simple_*.json",
            "kintuadi_*.json"
        ]
        
        for pattern in patterns:
            files = glob.glob(os.path.join(data_dir, pattern))
            if files:
                latest_file = max(files, key=os.path.getmtime)
                logger.info(f"Carregando: {os.path.basename(latest_file)}")
                
                with open(latest_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Valida estrutura básica
                if isinstance(data, dict):
                    return data
                
        return None
        
    except Exception as e:
        logger.error(f"Erro ao carregar dados: {e}")
        return None

def extract_data_for_display(raw_data):
    """Extrai dados para exibição com fallbacks"""
    if not raw_data:
        return get_fallback_data()
    
    try:
        # Extrai dados ONS
        ons_stats = raw_data.get('ons', {}).get('statistics', {}).get('geral', {})
        volume_medio = ons_stats.get('volume_medio', 50)
        status_sistema = ons_stats.get('status_sistema', 'N/A')
        total_reservatorios = ons_stats.get('total_reservatorios', 0)
        
        # Extrai dados CCEE
        ccee_stats = raw_data.get('ccee', {}).get('statistics', {}).get('geral', {})
        pld_medio = ccee_stats.get('pld_medio', 150)
        pld_registros = ccee_stats.get('quantidade', 0)
        
        # Extrai análise
        analysis = raw_data.get('analysis', {})
        tendencia = analysis.get('tendencia_mercado', 'N/A')
        alerta = analysis.get('alerta', False)
        indice_seguranca = analysis.get('indice_seguranca', 50)
        
        # Subsistemas
        subsistemas = raw_data.get('ons', {}).get('subsistemas', {})
        subsistema_stats = raw_data.get('ons', {}).get('statistics', {}).get('por_subsistema', {})
        
        # Submercados
        submercados = raw_data.get('ccee', {}).get('statistics', {}).get('por_submercado', {})
        
        # Timeseries
        timeseries = raw_data.get('ccee', {}).get('timeseries', [])
        
        return {
            'ons': {
                'volume_medio': volume_medio,
                'status': status_sistema,
                'total_reservatorios': total_reservatorios,
                'subsistemas': subsistemas,
                'subsistema_stats': subsistema_stats
            },
            'ccee': {
                'pld_medio': pld_medio,
                'registros': pld_registros,
                'submercados': submercados,
                'timeseries': timeseries
            },
            'analysis': {
                'tendencia': tendencia,
                'alerta': alerta,
                'indice_seguranca': indice_seguranca,
                'recomendacoes': analysis.get('recomendacoes', [])
            },
            'metadata': raw_data.get('metadata', {})
        }
        
    except Exception as e:
        logger.error(f"Erro ao extrair dados: {e}")
        return get_fallback_data()

def get_fallback_data():
    """Dados de fallback caso não consiga carregar"""
    return {
        'ons': {
            'volume_medio': 50,
            'status': 'N/A',
            'total_reservatorios': 0,
            'subsistemas': {},
            'subsistema_stats': {}
        },
        'ccee': {
            'pld_medio': 150,
            'registros': 0,
            'submercados': {},
            'timeseries': []
        },
        'analysis': {
            'tendencia': 'DADOS NÃO DISPONÍVEIS',
            'alerta': True,
            'indice_seguranca': 0,
            'recomendacoes': ['Execute o coletor primeiro']
        },
        'metadata': {'timestamp': 'N/A', 'status': 'error'}
    }

def create_gauge_chart(value, title, min_val=0, max_val=100):
    """Cria gráfico de gauge"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={'text': title},
        gauge={
            'axis': {'range': [min_val, max_val]},
            'bar': {'color': "#00b4d8"},
            'steps': [
                {'range': [0, 40], 'color': "#f44336"},
                {'range': [40, 60], 'color': "#ff9800"},
                {'range': [60, 80], 'color': "#ffc107"},
                {'range': [80, 100], 'color': "#4caf50"}
            ]
        }
    ))
    
    fig.update_layout(
        height=300,
        paper_bgcolor='rgba(0,0,0,0)',
        font={'color': "white"}
    )
    
    return fig

def main():
    """Função principal do dashboard"""
    
    # Cabeçalho
    st.markdown('<div class="main-header"><h1>⚡ KINTUADI ENERGY INTELLIGENCE</h1><p>Plataforma de Análise do Mercado de Energia</p></div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.title("⚙️ Controles")
        
        # Botão para recarregar
        if st.button("🔄 Atualizar Dados", use_container_width=True):
            st.rerun()
        
        st.divider()
        
        # Status do sistema
        st.subheader("📊 Status do Sistema")
        raw_data = load_latest_data()
        
        if raw_data and raw_data.get('metadata', {}).get('status') != 'error':
            st.success("✅ Dados carregados")
            timestamp = raw_data.get('metadata', {}).get('timestamp', 'N/A')
            st.caption(f"Última atualização: {timestamp}")
        else:
            st.error("❌ Sem dados")
            st.caption("Execute o coletor primeiro")
        
        st.divider()
        
        # Ações rápidas
        st.subheader("⚡ Ações Rápidas")
        if st.button("📊 Executar Coletor", use_container_width=True):
            st.info("Execute: python run_collector.py")
        
        if st.button("🔍 Ver Logs", use_container_width=True):
            st.info("Verifique: logs/kintuadi.log")
    
    # Carrega e processa dados
    raw_data = load_latest_data()
    data = extract_data_for_display(raw_data)
    
    # Se não tem dados, mostra mensagem clara
    if not raw_data or raw_data.get('metadata', {}).get('status') == 'error':
        st.error("""
        ## 📭 DADOS NÃO ENCONTRADOS
        
        **Para obter dados:**
        
        1. **Execute o coletor:**
        ```bash
        python run_collector.py
        ```
        
        2. **Escolha opção 2** (apenas coletar dados)
        
        3. **Recarregue esta página**
        
        **Ou teste rápido:**
        ```bash
        python -c "from scripts.ccee_simple_collector import CCEESimpleCollector; c = CCEESimpleCollector(); c.collect_recent_pld()"
        ```
        """)
        
        # Mostra dados de fallback para teste
        st.warning("📊 **MODO DE DEMONSTRAÇÃO (dados simulados)**")
    
    # KPIs PRINCIPAIS
    st.subheader("📈 INDICADORES PRINCIPAIS")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        volume = data['ons']['volume_medio']
        status_class = "critical" if volume < 40 else "warning" if volume < 60 else "success" if volume > 70 else ""
        
        st.markdown(f"""
        <div class="metric-card {status_class}">
            <h3>💧 Reservatórios SIN</h3>
            <h1 class="kpi-value">{volume:.1f}%</h1>
            <p>Status: {data['ons']['status']}</p>
            <small>{data['ons']['total_reservatorios']} reservatórios</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        pld = data['ccee']['pld_medio']
        status_class = "critical" if pld > 300 else "warning" if pld > 200 else "success" if pld < 100 else ""
        
        st.markdown(f"""
        <div class="metric-card {status_class}">
            <h3>💰 PLD Médio</h3>
            <h1 class="kpi-value">R$ {pld:.2f}</h1>
            <p>Preço médio do MWh</p>
            <small>{data['ccee']['registros']} registros</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        tendencia = data['analysis']['tendencia']
        alerta = data['analysis']['alerta']
        status_class = "critical" if alerta else "success"
        
        st.markdown(f"""
        <div class="metric-card {status_class}">
            <h3>📈 Tendência</h3>
            <h2>{tendencia}</h2>
            <p>{"⚠️ ALERTA ATIVO" if alerta else "✅ Sistema estável"}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        seguranca = data['analysis']['indice_seguranca']
        status_class = "critical" if seguranca < 40 else "warning" if seguranca < 60 else "success"
        
        st.markdown(f"""
        <div class="metric-card {status_class}">
            <h3>🛡️ Segurança</h3>
            <h1 class="kpi-value">{seguranca:.0f}/100</h1>
            <div style="background: #333; border-radius: 5px; height: 10px; margin: 10px 0;">
                <div style="background: {'#f44336' if seguranca < 40 else '#ff9800' if seguranca < 60 else '#4caf50'}; 
                            width: {seguranca}%; height: 100%; border-radius: 5px;"></div>
            </div>
            <small>Índice de segurança energética</small>
        </div>
        """, unsafe_allow_html=True)
    
    # GRÁFICOS
    st.markdown("---")
    st.subheader("📊 VISUALIZAÇÕES")
    
    tab1, tab2, tab3 = st.tabs(["Análise", "Subsistemas", "Detalhes"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="plot-container">', unsafe_allow_html=True)
            st.write("**💧 Volume dos Reservatórios**")
            fig1 = create_gauge_chart(volume, "Volume Útil (%)")
            st.plotly_chart(fig1, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="plot-container">', unsafe_allow_html=True)
            st.write("**💰 Evolução do PLD**")
            
            # Gráfico de linha simples
            if data['ccee']['timeseries']:
                timeseries_data = data['ccee']['timeseries'][-7:]  # Últimos 7 dias
                dates = [item['data'] for item in timeseries_data]
                values = [item['pld_medio'] for item in timeseries_data]
                
                fig2 = go.Figure(data=go.Scatter(
                    x=dates, y=values,
                    mode='lines+markers',
                    line=dict(color='#00b4d8', width=3),
                    marker=dict(size=8, color='white')
                ))
                
                fig2.update_layout(
                    height=300,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font={'color': "white"},
                    xaxis_title="Data",
                    yaxis_title="R$/MWh",
                    yaxis=dict(tickprefix="R$ ")
                )
                
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Sem dados históricos disponíveis")
            st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        # Tabela de subsistemas
        if data['ons']['subsistema_stats']:
            subsistemas_data = []
            for subsis, stats in data['ons']['subsistema_stats'].items():
                subsistemas_data.append({
                    'Subsistema': subsis,
                    'Volume Médio (%)': stats.get('volume_medio', 0),
                    'Status': stats.get('status', 'N/A'),
                    'Reservatórios': stats.get('quantidade', 0)
                })
            
            df_subsistemas = pd.DataFrame(subsistemas_data)
            
            # Aplica cores baseadas no volume
            def color_volume(val):
                if val < 40:
                    color = '#f44336'
                elif val < 60:
                    color = '#ff9800'
                elif val < 70:
                    color = '#ffc107'
                else:
                    color = '#4caf50'
                return f'background-color: {color}; color: white'
            
            styled_df = df_subsistemas.style.applymap(
                color_volume, 
                subset=['Volume Médio (%)']
            ).format({'Volume Médio (%)': '{:.1f}%'})
            
            st.dataframe(styled_df, use_container_width=True)
        else:
            st.info("Sem dados de subsistemas disponíveis")
        
        # Tabela de submercados
        if data['ccee']['submercados']:
            st.write("**💰 PLD por Submercado**")
            submercados_data = []
            for subm, stats in data['ccee']['submercados'].items():
                submercados_data.append({
                    'Submercado': subm,
                    'PLD Médio (R$/MWh)': stats.get('pld_medio', 0),
                    'Registros': stats.get('quantidade', 0)
                })
            
            df_submercados = pd.DataFrame(submercados_data)
            st.dataframe(df_submercados.style.format({'PLD Médio (R$/MWh)': 'R$ {:.2f}'}), use_container_width=True)
    
    with tab3:
        # Debug info
        with st.expander("🔍 Dados Técnicos (Debug)"):
            if raw_data:
                st.json(raw_data)
            else:
                st.write("Nenhum dado carregado")
        
        # Recomendações
        st.write("**🎯 Recomendações Estratégicas**")
        
        if data['analysis']['recomendacoes']:
            for rec in data['analysis']['recomendacoes']:
                st.write(f"- {rec}")
        else:
            if volume < 40:
                st.error("""
                **🔥 ALERTA CRÍTICO**
                - Aumentar exposição ao mercado spot
                - Preparar geração térmica
                - Revisar contratos de fornecimento
                """)
            elif volume < 60:
                st.warning("""
                **⚠️ SISTEMA EM ALERTA**
                - Monitorar preços diariamente
                - Balancear contratação ACR/ACL
                - Considerar ajustes na estratégia
                """)
            else:
                st.success("""
                **✅ SISTEMA ESTÁVEL**
                - Oportunidade para contratos longos
                - Momento para migração ao ACL
                - Manter estratégia atual
                """)
    
    # Rodapé
    st.markdown("---")
    st.caption(f"""
    ⚡ **Kintuadi Energy Platform v2.0** | Dados em tempo real | 
    Última atualização: {data['metadata'].get('timestamp', 'N/A')} | 
    Desenvolvido para gestores de energia
    """)

if __name__ == "__main__":
    main()