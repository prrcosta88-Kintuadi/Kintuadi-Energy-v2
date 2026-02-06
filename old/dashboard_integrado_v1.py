# dashboard_integrado.py - VERSÃO CORRIGIDA COM TEMA ESCURO
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
from datetime import datetime
import os
import glob

# Configuração da página com tema escuro
st.set_page_config(
    page_title="Kintuadi Energy Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS para tema escuro
st.markdown("""
<style>
    /* Tema escuro personalizado */
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    
    .main-header {
        color: #00FFAA;
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    .metric-card {
        background-color: #1E1E1E;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #00FFAA;
        margin-bottom: 1rem;
    }
    
    .warning-card {
        background-color: #2D1B00;
        border-left: 4px solid #FFAA00;
    }
    
    .critical-card {
        background-color: #2D0000;
        border-left: 4px solid #FF5555;
    }
    
    .plot-container {
        background-color: #1E1E1E;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Função para carregar dados
@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_latest_data():
    """Carrega os dados mais recentes da pasta data/"""
    data_dir = "data"
    
    if not os.path.exists(data_dir):
        st.error("❌ Pasta 'data' não encontrada. Execute o coletor primeiro.")
        return None
    
    # Procura arquivos dashboard
    dashboard_files = glob.glob(os.path.join(data_dir, "kintuadi_dashboard_*.json"))
    
    if not dashboard_files:
        # Procura arquivo latest
        latest_file = os.path.join(data_dir, "kintuadi_latest.json")
        if os.path.exists(latest_file):
            dashboard_files = [latest_file]
        else:
            # Procura qualquer JSON recente
            json_files = glob.glob(os.path.join(data_dir, "*.json"))
            if json_files:
                # Pega o mais recente
                dashboard_files = [max(json_files, key=os.path.getmtime)]
    
    if not dashboard_files:
        return None
    
    # Carrega o arquivo mais recente
    latest_file = max(dashboard_files, key=os.path.getmtime)
    
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # DEBUG: Mostra estrutura no terminal
        print(f"📂 Carregado: {os.path.basename(latest_file)}")
        print(f"📊 Estrutura: {list(data.keys())}")
        
        return data
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados: {e}")
        return None

# Função para extrair dados de forma robusta
def extract_data(data):
    """Extrai dados de forma robusta, lidando com diferentes estruturas"""
    if not data:
        return {}
    
    result = {
        'ons': {'volume_medio': 0, 'status': 'N/A', 'total_reservatorios': 0},
        'ccee': {'pld_medio': 0, 'registros': 0},
        'analysis': {'tendencia': 'N/A', 'alerta': False},
        'timestamp': data.get('timestamp', 'N/A')
    }
    
    # Tenta diferentes caminhos para dados ONS
    ons_paths = [
        data.get('ons', {}),
        data.get('ons_summary', {}),
        data.get('data', {}).get('ons_reservatorios', {}).get('summary', {}).get('geral', {})
    ]
    
    for ons in ons_paths:
        if isinstance(ons, dict):
            # Volume médio
            for key in ['volume_medio_geral', 'volume_medio', 'volume_util_medio']:
                if key in ons and ons[key]:
                    result['ons']['volume_medio'] = float(ons[key])
                    break
            
            # Status
            for key in ['status', 'status_sistema']:
                if key in ons and ons[key]:
                    result['ons']['status'] = ons[key]
                    break
            
            # Total reservatórios
            for key in ['total_reservatorios', 'quantidade']:
                if key in ons and ons[key]:
                    result['ons']['total_reservatorios'] = int(ons[key])
                    break
    
    # Tenta diferentes caminhos para dados CCEE
    ccee_paths = [
        data.get('ccee', {}),
        data.get('ccee_stats', {}),
        data.get('data', {}).get('ccee_pld', {}).get('statistics', {}).get('geral', {})
    ]
    
    for ccee in ccee_paths:
        if isinstance(ccee, dict):
            # PLD médio
            for key in ['pld_medio', 'media']:
                if key in ccee and ccee[key]:
                    result['ccee']['pld_medio'] = float(ccee[key])
                    break
            
            # Registros
            for key in ['registros', 'total_registros', 'count']:
                if key in ccee and ccee[key]:
                    result['ccee']['registros'] = int(ccee[key])
                    break
    
    # Análise
    analysis_paths = [
        data.get('analysis', {}),
        data.get('analise_integrada', {})
    ]
    
    for analysis in analysis_paths:
        if isinstance(analysis, dict):
            # Tendência
            for key in ['tendencia_mercado', 'tendencia', 'market_trend']:
                if key in analysis and analysis[key]:
                    result['analysis']['tendencia'] = analysis[key]
                    break
            
            # Alerta
            for key in ['alerta', 'alert']:
                if key in analysis:
                    result['analysis']['alerta'] = bool(analysis[key])
                    break
    
    return result

# Função para criar gradiente de cor sem matplotlib
def apply_color_gradient(df, column, low_color='#FF5555', high_color='#00FFAA'):
    """Aplica gradiente de cor manualmente sem usar matplotlib"""
    if df.empty or column not in df.columns:
        return df
    
    min_val = df[column].min()
    max_val = df[column].max()
    range_val = max_val - min_val if max_val > min_val else 1
    
    def get_color(value):
        if pd.isna(value):
            return ''
        
        # Interpolação linear entre duas cores
        norm = (value - min_val) / range_val
        
        # Converter cores hex para RGB
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        rgb_low = hex_to_rgb(low_color)
        rgb_high = hex_to_rgb(high_color)
        
        # Interpolar
        r = int(rgb_low[0] + (rgb_high[0] - rgb_low[0]) * norm)
        g = int(rgb_low[1] + (rgb_high[1] - rgb_low[1]) * norm)
        b = int(rgb_low[2] + (rgb_high[2] - rgb_low[2]) * norm)
        
        return f'background-color: rgb({r}, {g}, {b}); color: white'
    
    return df.style.apply(lambda x: [get_color(x[column]) if i == df.columns.get_loc(column) else '' 
                                     for i in range(len(x))], axis=1)

# Interface principal
def main():
    # Cabeçalho
    st.markdown('<h1 class="main-header">⚡ KINTUADI ENERGY INTELLIGENCE</h1>', unsafe_allow_html=True)
    st.caption("Plataforma de Análise do Mercado de Energia | Dados em tempo real")
    
    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/energy.png", width=80)
        st.title("Painel de Controle")
        
        st.divider()
        
        # Seletor de fonte de dados
        st.subheader("📊 Fonte de Dados")
        data_option = st.radio(
            "Escolha a fonte:",
            ["Última coleta", "Arquivo específico", "Testar conexão"],
            index=0
        )
        
        if data_option == "Arquivo específico":
            data_files = glob.glob("data/*.json")
            if data_files:
                selected_file = st.selectbox("Selecione arquivo:", data_files)
                # Aqui você pode carregar o arquivo selecionado
            else:
                st.warning("Nenhum arquivo encontrado")
        
        st.divider()
        
        # Informações do sistema
        st.subheader("ℹ️ Sistema")
        st.metric("Status", "🟢 Online" if load_latest_data() else "🔴 Offline")
        st.caption(f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")
        
        st.divider()
        
        # Ações rápidas
        st.subheader("⚡ Ações")
        if st.button("🔄 Atualizar Dados", width='stretch'):
            st.rerun()
        
        if st.button("📊 Executar Coletor", width='stretch'):
            st.info("Execute: python run_collector.py")
    
    # Carrega dados
    raw_data = load_latest_data()
    data = extract_data(raw_data)
    
    if not data:
        st.error("""
        ## 📭 Dados não encontrados
        
        **Solução:**
        1. Execute o coletor primeiro:
        ```bash
        python run_collector.py
        ```
        2. Escolha a opção 2 (apenas coletar dados)
        3. Recarregue esta página
        
        **Ou execute diretamente:**
        ```bash
        python -c "from scripts.integrated_collector import KintuadiIntegratedCollector; c = KintuadiIntegratedCollector(); c.collect_all()"
        ```
        """)
        return
    
    # DEBUG: Mostra dados extraídos
    with st.expander("🔍 Dados Extraídos (Debug)"):
        st.json(data)
        if raw_data:
            st.caption(f"Arquivo: {data.get('timestamp', 'N/A')}")
    
    # KPIs PRINCIPAIS
    st.subheader("📈 INDICADORES PRINCIPAIS")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        volume = data['ons']['volume_medio']
        status = data['ons']['status']
        
        # Card colorido baseado no status
        if volume < 40:
            card_class = "critical-card"
            icon = "🔥"
            status_text = "CRÍTICO"
        elif volume < 60:
            card_class = "warning-card"
            icon = "⚠️"
            status_text = "ALERTA"
        else:
            card_class = "metric-card"
            icon = "💧"
            status_text = "NORMAL"
        
        st.markdown(f"""
        <div class="{card_class}">
            <h3>{icon} Reservatórios SIN</h3>
            <h1>{volume:.1f}%</h1>
            <p>Status: {status_text}</p>
            <small>{data['ons']['total_reservatorios']} reservatórios</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        pld = data['ccee']['pld_medio']
        
        if pld > 300:
            card_class = "critical-card"
            icon = "💸"
            status_text = "ALTO"
        elif pld > 200:
            card_class = "warning-card"
            icon = "📈"
            status_text = "ELEVADO"
        else:
            card_class = "metric-card"
            icon = "💰"
            status_text = "NORMAL"
        
        st.markdown(f"""
        <div class="{card_class}">
            <h3>{icon} PLD Médio</h3>
            <h1>R$ {pld:.2f}/MWh</h1>
            <p>Mercado: {status_text}</p>
            <small>{data['ccee']['registros']} registros</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        tendencia = data['analysis']['tendencia']
        alerta = data['analysis']['alerta']
        
        if alerta:
            card_class = "critical-card"
            icon = "🚨"
        else:
            card_class = "metric-card"
            icon = "📊"
        
        st.markdown(f"""
        <div class="{card_class}">
            <h3>{icon} Tendência</h3>
            <h2>{tendencia}</h2>
            <p>{"⚠️ ALERTA ATIVO" if alerta else "✅ Sistema estável"}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        # Índice de segurança energética
        seguranca = min(100, max(0, data['ons']['volume_medio'] * 1.2))
        
        st.markdown(f"""
        <div class="metric-card">
            <h3>🛡️ Segurança</h3>
            <h1>{seguranca:.0f}/100</h1>
            <div style="background: #333; border-radius: 5px; height: 10px; margin: 10px 0;">
                <div style="background: {'#FF5555' if seguranca < 50 else '#FFAA00' if seguranca < 70 else '#00FFAA'}; 
                            width: {seguranca}%; height: 100%; border-radius: 5px;"></div>
            </div>
            <small>Índice de segurança energética</small>
        </div>
        """, unsafe_allow_html=True)
    
    # GRÁFICOS E ANÁLISES
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["📊 Análise Detalhada", "🗺️ Mapa do Sistema", "🎯 Simulador"])
    
    with tab1:
        st.subheader("Análise Detalhada do Mercado")
        
        # Gráfico 1: Reservatórios
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="plot-container">', unsafe_allow_html=True)
            st.write("**📉 Nível dos Reservatórios**")
            
            # Gauge chart para volume
            fig1 = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = volume,
                title = {'text': "Volume Útil (%)"},
                gauge = {
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "#00FFAA"},
                    'steps': [
                        {'range': [0, 40], 'color': "#FF5555"},
                        {'range': [40, 60], 'color': "#FFAA00"},
                        {'range': [60, 100], 'color': "#00FFAA"}
                    ],
                    'threshold': {
                        'line': {'color': "white", 'width': 3},
                        'thickness': 0.8,
                        'value': volume
                    }
                }
            ))
            
            fig1.update_layout(
                height=300,
                paper_bgcolor='rgba(0,0,0,0)',
                font={'color': "white"}
            )
            
            st.plotly_chart(fig1, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="plot-container">', unsafe_allow_html=True)
            st.write("**💰 Evolução do PLD**")
            
            # Bar chart simulado para PLD
            fig2 = go.Figure(data=[
                go.Bar(
                    x=['Min', 'Médio', 'Max'],
                    y=[pld * 0.7, pld, pld * 1.3],  # Valores simulados
                    marker_color=['#00FFAA', '#FFAA00', '#FF5555'],
                    text=[f'R$ {pld*0.7:.0f}', f'R$ {pld:.0f}', f'R$ {pld*1.3:.0f}'],
                    textposition='auto'
                )
            ])
            
            fig2.update_layout(
                height=300,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font={'color': "white"},
                xaxis={'gridcolor': '#333'},
                yaxis={'gridcolor': '#333', 'title': 'R$/MWh'}
            )
            
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Recomendações
        st.markdown("---")
        st.subheader("🎯 Recomendações Estratégicas")
        
        if volume < 40:
            st.error("""
            ## 🔥 ALERTA CRÍTICO - AÇÃO IMEDIATA RECOMENDADA
            
            **Para Geradores:**
            - Aumentar exposição ao mercado spot (PLD tende a subir)
            - Preparar geração térmica para possível despacho
            
            **Para Consumidores:**
            - Aumentar contratação no ACR para proteção
            - Revisar contratos de fornecimento
            
            **Para Comercializadores:**
            - Incluir prêmio de risco significativo nos preços
            - Revisar limites de exposição
            """)
        elif volume < 60:
            st.warning("""
            ## ⚠️ SISTEMA EM ALERTA - MONITORAMENTO INTENSIVO
            
            **Para Geradores:**
            - Considerar vender parte da energia no spot
            - Manter térmicas em standby
            
            **Para Consumidores:**
            - Balancear contratação ACR/ACL
            - Monitorar preços diariamente
            
            **Para Comercializadores:**
            - Incluir prêmio de risco moderado
            - Oferecer opções de hedge
            """)
        else:
            st.success("""
            ## ✅ SISTEMA ESTÁVEL - OPORTUNIDADES DE MERCADO
            
            **Para Geradores:**
            - Oportunidade para contratos de longo prazo
            - Considerar manutenção programada
            
            **Para Consumidores:**
            - Momento favorável para migração ao ACL
            - Negociar melhores condições
            
            **Para Comercializadores:**
            - Preços competitivos para captação
            - Expansão de carteira de clientes
            """)
    
    with tab2:
        st.subheader("Mapa do Sistema Interligado Nacional")
        
        # Mapa simulado
        st.info("""
        **⚡ Sistema Interligado Nacional - Visão Simplificada**
        
        ```
        NORTE (Amazonas)        NORDESTE
          │ 50.5%                │ 24.5%
          ▼                      ▼
        ┌─────────────────────────────────┐
        │          INTERLIGAÇÃO           │
        └─────────────────────────────────┘
          ▲                      ▲
          │ 4.6%                 │ 8.2%
        SUDESTE/CO              SUL
        ```
        
        **Status por Subsistema:**
        - **Norte:** 50.5% ⚡ (Estável)
        - **Nordeste:** 24.5% ⚠️ (Atenção)
        - **Sudeste/Centro-Oeste:** 4.6% 🔥 (Crítico)
        - **Sul:** 8.2% 🔥 (Crítico)
        """)
        
        # Tabela de subsistemas
        subsistemas = {
            'Norte': 50.5,
            'Nordeste': 24.5,
            'Sudeste/Centro-Oeste': 4.6,
            'Sul': 8.2
        }
        
        df_subsistemas = pd.DataFrame({
            'Subsistema': list(subsistemas.keys()),
            'Volume (%)': list(subsistemas.values()),
            'Status': ['Estável', 'Atenção', 'Crítico', 'Crítico']
        })
        
        # Aplica gradiente de cor manualmente
        styled_df = apply_color_gradient(df_subsistemas, 'Volume (%)', low_color='#FF5555', high_color='#00FFAA')
        
        # Formata os valores
        styled_df = styled_df.format({'Volume (%)': '{:.1f}%'})
        
        st.dataframe(
            styled_df,
            width='stretch'
        )
    
    with tab3:
        st.subheader("Simulador de Contratação")
        
        col1, col2 = st.columns(2)
        
        with col1:
            perfil = st.selectbox(
                "Seu Perfil",
                ["Gerador", "Consumidor Livre", "Comercializador", "Consumidor Cativo"],
                key="sim_perfil"
            )
            
            exposicao = st.slider(
                "Exposição ao Mercado Spot (%)",
                0, 100, 30,
                help="Percentual da energia exposta à variação do PLD"
            )
            
            horizonte = st.selectbox(
                "Horizonte de Contratação",
                ["Curto Prazo (até 1 ano)", "Médio Prazo (1-3 anos)", "Longo Prazo (+3 anos)"]
            )
        
        with col2:
            risco = st.select_slider(
                "Tolerância a Risco",
                options=['Muito Conservador', 'Conservador', 'Moderado', 'Agressivo', 'Muito Agressivo'],
                value='Moderado'
            )
            
            if st.button("🎯 SIMULAR ESTRATÉGIA", type="primary", width='stretch'):
                # Simulação básica
                custo_base = pld * 0.8 if perfil == "Consumidor Livre" else pld * 1.2
                custo_ajustado = custo_base * (1 + (100 - exposicao) * 0.005)
                
                st.success(f"""
                ## 📊 Resultado da Simulação
                
                **Estratégia Recomendada:**
                - {exposicao}% no mercado spot
                - {100-exposicao}% em contratos {horizonte.split(' ')[0].lower()}
                
                **Estimativas:**
                - Custo médio estimado: **R$ {custo_ajustado:.2f}/MWh**
                - Proteção contra volatilidade: **{(100-exposicao)*0.8:.0f}%**
                - Flexibilidade operacional: **{exposicao*0.9:.0f}%**
                
                **Recomendação:** {"Manter estratégia conservadora" if risco in ['Muito Conservador', 'Conservador'] else "Considerar aumento de exposição"}
                """)
    
    # RODAPÉ
    st.markdown("---")
    st.caption(f"""
    ⚡ **Kintuadi Energy Platform v1.2** | Dados: ONS + CCEE | 
    Última coleta: {data.get('timestamp', 'N/A')} | 
    Desenvolvido para gestores de energia
    """)

if __name__ == "__main__":
    main()