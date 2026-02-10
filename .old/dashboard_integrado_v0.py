# dashboard_integrado.py — CORE REAL • ZERO DADOS FICTÍCIOS

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import glob
from datetime import datetime, timedelta
import logging

from scripts.core_analysis import build_core_analysis

# -----------------------------------------------------------------------------
# Configuração
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Kintuadi Energy Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# CSS
# -----------------------------------------------------------------------------
st.markdown(
    """
<style>
.stApp { background-color:#020617; color:#e5e7eb; }
section[data-testid="stSidebar"] { background-color:#020f2a; }
header[data-testid="stHeader"] { background-color:#020b1f; }

.insight-card {
    background: linear-gradient(135deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
    border-radius: 10px;
    padding: 1.1rem;
    border: 1px solid rgba(255,255,255,0.08);
}
.insight-card.success { border-left: 4px solid #22c55e; }
.insight-card.warning { border-left: 4px solid #f59e0b; }
.insight-card.critical { border-left: 4px solid #ef4444; }

.kpi-value {
    font-size: 2.1rem;
    font-weight: 800;
    background: linear-gradient(90deg, #38bdf8, #0ea5e9);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.section-title { font-size:1.4rem; font-weight:700; margin:1.2rem 0 .8rem; }
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def load_latest_raw():
    files = glob.glob("data/kintuadi_latest.json")
    if not files:
        return None
    with open(files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def badge_status(value: str):
    if value in ("crítico", "inefficient"):
        return "critical"
    if value in ("alerta", "neutral"):
        return "warning"
    if value in ("confortável", "abundante", "efficient"):
        return "success"
    return ""


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    raw = load_latest_raw()

    with st.sidebar:
        st.markdown("## ⚡ **KINTUADI**")
        st.markdown("---")
        st.success("Dados carregados" if raw else "Nenhum dado encontrado")

    if not raw:
        st.error("Execute o coletor antes de abrir o dashboard.")
        return

    core = build_core_analysis(raw)

    # =========================================================================
    # PULSO DO SISTEMA
    # =========================================================================
    st.markdown('<div class="section-title">📈 Pulso do Sistema</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)

    with c1:
        hyd = core["hydrology"]
        ear = hyd.get("ear_medio")
        ear_fmt = f"{ear:.2f}%" if isinstance(ear, (int, float)) else "—"

        st.markdown(
            f"""
<div class="insight-card {badge_status(hyd["classificacao"]["classe"])}">
<h4>💧 Hidrologia</h4>
<div class="kpi-value">{ear_fmt}</div>
<p>{hyd["classificacao"]["descricao"]}</p>
</div>
""",
            unsafe_allow_html=True,
        )

    with c2:
        prices = core["prices"]
        pld = prices.get("pld_medio")
        vol = prices.get("pld_volatilidade")

        st.markdown(
            f"""
    <div class="insight-card">
    <h4>💰 PLD Horário</h4>
    <div class="kpi-value">{f"R$ {pld:.2f}" if pld else "—"}</div>
    <p>Volatilidade: {f"{vol:.1f}" if vol else "—"}</p>
    </div>
    """,
            unsafe_allow_html=True,
        )


    with c3:
        th = core["thermal_dispatch"]
        eff = th.get("efficiency")
        eff_fmt = f"{eff:.0f}%" if isinstance(eff, (int, float)) else "—"
        cvu = th.get("cvu_medio")
        cvu_fmt = f"R$ {cvu:.1f}" if isinstance(cvu, (int, float)) else "—"
        st.markdown(
            f"""
<div class="insight-card {badge_status(th["status"])}">
<h4>🔥 Despacho Térmico</h4>
<div class="kpi-value">{eff_fmt}</div>
<p>
PLD − CVU: R$ {th["spread"]:.1f}<br>
CVU médio: {cvu_fmt}
</p>
</div>
""",
            unsafe_allow_html=True,
        )

    # =========================================================================
    # CICLO DO SIN
    # =========================================================================
    st.markdown('<div class="section-title">🌎 Ciclo do SIN</div>', unsafe_allow_html=True)

    cycle = core.get("sin_cycle", {})

    if cycle:
        st.markdown(
            f"""
<div class="insight-card {badge_status(cycle.get("cycle"))}">
<h4>Regime Hidroenergético</h4>
<div class="kpi-value">{cycle.get("cycle", "—").upper()}</div>
<p>{cycle.get("description", "")}</p>
</div>
""",
            unsafe_allow_html=True,
        )

    # =========================================================================
    # RESUMO OPERACIONAL (ENERGIA AGORA)
    # =========================================================================
    gen = core["operacao"]["generation"]

    st.markdown("### 📋 Resumo Operacional (Energia Agora)")

    if gen:
        rows = []

        for fonte, dados in gen.items():
            rows.append({
                "Fonte": fonte.upper(),
                "Geração Média (MW)": round(dados.get("media", 0), 0),
                "Rampa Máx (MW/h)": round(dados.get("rampa_max", 0), 0),
            })

        df_resumo = pd.DataFrame(rows)

        st.dataframe(
            df_resumo,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Resumo operacional indisponível.")

    # =========================================================================
    # GERAÇÃO ONS — ENERGIA AGORA (CORE)
    # =========================================================================
    st.markdown('<div class="section-title">⚙️ Geração Horária (ONS)</div>', unsafe_allow_html=True)

    if gen:
        fig = go.Figure()

        for fonte, dados in gen.items():

            # 🚫 ignora SIN (soma do sistema)
            if "sin" in fonte.lower():
                continue

            df = pd.DataFrame(dados["serie"])

            fig.add_trace(
                go.Bar(
                    x=df["instante"],
                    y=df["geracao"],
                    name=fonte.upper(),
                )
            )

        fig.update_layout(
            template="plotly_dark",
            title="Geração Horária por Fonte (Energia Agora)",
            xaxis_title="Hora",
            yaxis_title="MW",
            barmode="stack",  # 🔑 empilhado
            legend_title="Fonte",
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Dados de geração ONS indisponíveis.")


    # =========================================================================
    # CARGA ONS
    # =========================================================================
    st.markdown('<div class="section-title">🔌 Carga Horária (ONS)</div>', unsafe_allow_html=True)

    load = core["operacao"]["load"]

    if load:
        fig = go.Figure()

        for area, dados in load.items():
            if area.upper() == "SIN":
                continue

            df = pd.DataFrame(dados["serie"])

            fig.add_trace(
                go.Bar(
                    x=df["instante"],
                    y=df["carga"],
                    name=area.upper(),
                )
            )

        fig.update_layout(
            template="plotly_dark",
            title="Carga Horária por Submercado (ONS)",
            xaxis_title="Hora",
            yaxis_title="MW",
            barmode="stack",
        )


        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Dados de carga ONS indisponíveis.")

    # =========================================================================
    # GRAFICO PLD MEDIO POR SUBMERCADO
    # =========================================================================
    st.markdown("### 🌐 PLD Horário por Submercado — Últimos 7 dias")

    pld_ts = core["prices"].get("pld_horario_7d", {})

    if pld_ts:
        fig = go.Figure()

        for sm, serie in pld_ts.items():
            df = pd.DataFrame(serie)
            df["instante"] = pd.to_datetime(df["instante"])

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
            title="PLD Horário por Submercado (últimos 7 dias)",
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Série temporal de PLD indisponível.")

    
    # =========================================================================
    # MCP ECONÔMICO
    # =========================================================================
    st.markdown('<div class="section-title">📊 MCP Econômico</div>', unsafe_allow_html=True)

    mcp = core.get("mcp_economico", {})

    if mcp:
        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown(
                f"""
<div class="insight-card">
<h4>Regime do MCP</h4>
<div class="kpi-value">{mcp.get("regime_mcp", "—").upper()}</div>
<p>{mcp.get("interpretação", {}).get("preço", "")}</p>
</div>
""",
                unsafe_allow_html=True,
            )

        with c2:
            si = mcp.get("stress_index")
            st.markdown(
                f"""
<div class="insight-card {badge_status('alerta' if si and si > 1 else 'confortável')}">
<h4>Stress Index</h4>
<div class="kpi-value">{f"{si:.2f}" if si else "—"}</div>
<p>Demanda / Oferta hidráulica</p>
</div>
""",
                unsafe_allow_html=True,
            )

        with c3:
            corr = mcp.get("correlacoes", {})
            st.markdown(
                f"""
<div class="insight-card">
<h4>Correlação PLD × Hidro</h4>
<div class="kpi-value">
{f"{corr.get('pld_vs_hidraulica'):.2f}" if corr.get("pld_vs_hidraulica") is not None else "—"}
</div>
<p>Preço vs oferta hídrica</p>
</div>
""",
                unsafe_allow_html=True,
            )
    else:
        st.info("MCP econômico indisponível.")


    # =========================================================================
    # TENDENCIA
    # =========================================================================
    t = hyd.get("tendencia")
    if t is not None:
        st.caption(f"Tendência EAR (7d vs 30d): {t:+.2f} p.p.")

    # =========================================================================
    # METADATA
    # =========================================================================
    with st.expander("ℹ️ Metadados do CORE"):
        st.json(core["metadata"])


if __name__ == "__main__":
    main()
