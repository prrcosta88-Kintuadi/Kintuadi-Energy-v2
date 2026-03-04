import json
import os
from datetime import datetime, date, time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def _load_core() -> Dict[str, Any]:
    for p in [Path("data/core_analysis_latest.json"), Path("core_analysis_latest.json")]:
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                return json.load(f)
    return {}


def _series_from_hourly(d: Dict[str, Any], name: str) -> pd.Series:
    if not isinstance(d, dict) or not d:
        return pd.Series(dtype=float, name=name)
    s = pd.Series(d, name=name)
    s.index = pd.to_datetime(s.index, errors="coerce")
    try:
        if getattr(s.index, "tz", None) is not None:
            s.index = s.index.tz_localize(None)
    except Exception:
        pass
    s = pd.to_numeric(s, errors="coerce")
    return s.dropna()


def _series_from_operacao(records, value_key: str, name: str) -> pd.Series:
    if not isinstance(records, list) or not records:
        return pd.Series(dtype=float, name=name)
    df = pd.DataFrame(records)
    if "instante" not in df.columns or value_key not in df.columns:
        return pd.Series(dtype=float, name=name)
    df["instante"] = pd.to_datetime(df["instante"], errors="coerce")
    df[value_key] = pd.to_numeric(df[value_key], errors="coerce")
    df = df.dropna(subset=["instante", value_key])
    s = df.groupby("instante")[value_key].sum().sort_index().rename(name)
    try:
        if getattr(s.index, "tz", None) is not None:
            s.index = s.index.tz_localize(None)
    except Exception:
        pass
    return s


def _build_hourly_df(core: Dict[str, Any]) -> pd.DataFrame:
    econ = core.get("economic", {}) or core.get("advanced_metrics", {}).get("economic", {}) or {}
    adv = core.get("advanced_metrics", {})

    df = pd.DataFrame()
    # economic-driven
    for k, col in [
        ("sin_cost_hourly", "sin_cost"),
        ("T_prudencia_hourly", "t_prudencia"),
        ("T_hidro_hourly", "t_hidro"),
        ("T_eletric_hourly", "t_eletric"),
        ("CVaR_implicit_hourly", "cvar_implicit"),
        ("Risk_Aversion_Gap_hourly", "risk_gap"),
        ("curtailment_loss_hourly", "curtailment_loss"),
        ("hydro_gap_hourly", "hydro_gap"),
        ("required_hydro_hourly", "required_hydro"),
        ("mandatory_generation_hourly", "mandatory_generation"),
        ("thermal_prudential_dispatch_hourly", "thermal_prudential_dispatch"),
    ]:
        s = _series_from_hourly(econ.get(k, {}), col)
        if not s.empty:
            df = df.join(s, how="outer") if not df.empty else s.to_frame()

    # system state
    st_h = econ.get("system_state_hourly", {})
    if isinstance(st_h, dict) and st_h:
        s = pd.Series(st_h, name="system_state")
        s.index = pd.to_datetime(s.index, errors="coerce")
        s = s.dropna()
        df = df.join(s, how="outer") if not df.empty else s.to_frame()

    # from operacao
    oper = core.get("operacao", {})
    gen = oper.get("generation", {})
    load = oper.get("load", {})

    load_sin = _series_from_operacao((load.get("sin") or {}).get("serie", []), "carga", "load")
    if not load_sin.empty:
        df = df.join(load_sin, how="outer") if not df.empty else load_sin.to_frame()

    for source_key, col in [
        ("sin_fotovoltaica", "solar"),
        ("sin_eolica", "wind"),
        ("sin_termica", "thermal"),
        ("sin_hidraulica", "hydro"),
        ("sin_nuclear", "nuclear"),
    ]:
        s = _series_from_operacao((gen.get(source_key) or {}).get("serie", []), "geracao", col)
        if not s.empty:
            df = df.join(s, how="outer") if not df.empty else s.to_frame()

    # pld from ccee records
    ccee = core.get("ccee", {}).get("data", [])
    if ccee:
        cdf = pd.DataFrame(ccee)
        if {"mes_referencia", "dia", "hora", "pld_hora"}.issubset(cdf.columns):
            cdf["mr"] = cdf["mes_referencia"].astype(str).str.zfill(6)
            cdf["ts"] = pd.to_datetime(cdf["mr"].str[:4] + "-" + cdf["mr"].str[4:6] + "-" + cdf["dia"].astype(str).str.zfill(2) + " " + cdf["hora"].astype(str).str.zfill(2) + ":00:00", errors="coerce")
            cdf["pld_hora"] = pd.to_numeric(cdf["pld_hora"], errors="coerce")
            cdf = cdf.dropna(subset=["ts", "pld_hora"])
            if not cdf.empty:
                pld = cdf.groupby("ts")["pld_hora"].mean().rename("pld")
                try:
                    if getattr(pld.index, "tz", None) is not None:
                        pld.index = pld.index.tz_localize(None)
                except Exception:
                    pass
                df = df.join(pld, how="outer") if not df.empty else pld.to_frame()

    # panel from advanced metrics
    panel = pd.DataFrame(adv.get("painel_horario_renovavel", []))
    if not panel.empty and "instante" in panel.columns:
        panel["instante"] = pd.to_datetime(panel["instante"], errors="coerce")
        panel = panel.dropna(subset=["instante"]).set_index("instante")
        for src, dst in [("gfom_pct", "gfom_pct"), ("ipr", "ipr"), ("isr", "isr"), ("ear", "ear"), ("ena", "ena")]:
            if src in panel.columns:
                s = pd.to_numeric(panel[src], errors="coerce").rename(dst)
                df = df.join(s, how="outer") if not df.empty else s.to_frame()

    # curtailment series
    for key, col in [("solar", "curtail_solar"), ("eolica", "curtail_wind")]:
        ser = pd.DataFrame(((core.get("renewables", {}).get("curtailment", {}).get(key, {}) or {}).get("serie", [])))
        if not ser.empty and {"instante", "valor"}.issubset(ser.columns):
            ser["instante"] = pd.to_datetime(ser["instante"], errors="coerce")
            ser["valor"] = pd.to_numeric(ser["valor"], errors="coerce")
            s = ser.dropna().set_index("instante")["valor"].groupby(level=0).sum().rename(col)
            try:
                if getattr(s.index, "tz", None) is not None:
                    s.index = s.index.tz_localize(None)
            except Exception:
                pass
            df = df.join(s, how="outer") if not df.empty else s.to_frame()

    if not df.empty:
        df = df.sort_index()
        z = pd.Series(0.0, index=df.index)
        load_s = pd.to_numeric(df["load"], errors="coerce") if "load" in df.columns else pd.Series(np.nan, index=df.index)
        solar_s = pd.to_numeric(df["solar"], errors="coerce") if "solar" in df.columns else z
        wind_s = pd.to_numeric(df["wind"], errors="coerce") if "wind" in df.columns else z
        cur_solar = pd.to_numeric(df["curtail_solar"], errors="coerce") if "curtail_solar" in df.columns else z
        cur_wind = pd.to_numeric(df["curtail_wind"], errors="coerce") if "curtail_wind" in df.columns else z
        df["net_load"] = load_s - solar_s.fillna(0) - wind_s.fillna(0)
        df["curtail_total"] = cur_solar.fillna(0) + cur_wind.fillna(0)
        if "cmo_dominante" not in df.columns:
            cmo_sm = ((adv.get("aderencia_fisico_economica", {}) or {}).get("cmo_horario_por_submercado", {}) or {})
            if isinstance(cmo_sm, dict) and cmo_sm:
                # prefer SUDESTE
                first_key = "SUDESTE" if "SUDESTE" in cmo_sm else list(cmo_sm.keys())[0]
                s = _series_from_hourly(cmo_sm.get(first_key, {}), "cmo_dominante")
                if not s.empty:
                    df = df.join(s, how="left")

    return df


def _kpi_card(label: str, value: Any, suffix: str = ""):
    st.markdown(f"""
    <div style='background:#131722;border:1px solid #2a2f3a;border-radius:12px;padding:10px 12px;height:95px;'>
      <div style='font-size:12px;color:#9ba3af;'>{label}</div>
      <div style='font-size:24px;color:#f3f4f6;font-weight:700;line-height:1.2'>{value}{suffix}</div>
    </div>
    """, unsafe_allow_html=True)


def _system_text(row: pd.Series) -> str:
    s = row.get("system_state")
    if isinstance(s, str) and s:
        return f"Regime {s} com carga líquida de {row.get('net_load', np.nan):,.0f} MWmed."
    return "Sem dados suficientes para diagnóstico automático da hora selecionada."


def main():
    st.set_page_config(page_title="MAÁTria Energia", layout="wide")

    st.markdown("""
    <style>
      .stApp { background-color:#0b0f14; color:#f3f4f6; }
      [data-testid="stSidebar"] { background-color:#0f172a; }
      .block-container { padding-top: 0.5rem; }

      .header-line { border-top:1px solid #c8a44d; margin: 0.25rem 0; }
      .header-layer {
        background:#0f172a;
        border-top:1px solid #c8a44d;
        border-bottom:1px solid #c8a44d;
        border-radius:8px;
        padding:0.75rem 1rem;
        margin:0.35rem 0 0.55rem 0;
      }
      .tabs-layer {
        background: linear-gradient(180deg, #0b1222 0%, #070d1a 100%);
        border-top:1px solid #c8a44d;
        border-bottom:1px solid #c8a44d;
        border-radius:8px;
        padding:0.4rem 0.6rem 0.1rem 0.6rem;
        margin-bottom:0.75rem;
      }
      .stTabs [data-baseweb="tab-list"] { gap: 0.4rem; }
      .stTabs [data-baseweb="tab"] {
        background: transparent;
        color:#e5e7eb;
        border-radius:6px;
        padding: 0.35rem 0.65rem;
      }
      .stTabs [aria-selected="true"] {
        background:#152238 !important;
        color:#f8fafc !important;
        border:1px solid #c8a44d !important;
      }
      div[data-testid="stFormSubmitButton"] > button {
        background:#d4af37 !important;
        color:#111827 !important;
        font-weight:800 !important;
        border:1px solid #b38f2b !important;
      }
      div[data-testid="stFormSubmitButton"] > button:hover {
        background:#e3bf4c !important;
        color:#000 !important;
      }
    </style>
    """, unsafe_allow_html=True)

    core = _load_core()
    if not core:
        st.error("core_analysis_latest.json não encontrado.")
        return

    df = _build_hourly_df(core)
    if df.empty:
        st.warning("Sem séries horárias suficientes no core para renderizar o painel.")
        return

    min_d, max_d = df.index.min().date(), df.index.max().date()

    st.markdown("<div class='header-line'></div>", unsafe_allow_html=True)
    colc1, colc2, colc3 = st.columns([1, 2, 1])
    with colc2:
        logo = Path("streamlit/img/emblema_maatria.png")
        if logo.exists():
            st.image(str(logo), width='stretch')
        else:
            st.markdown("## MAÁTria Energia")
    st.markdown("<div class='header-line'></div>", unsafe_allow_html=True)

    with st.container():
        st.markdown("<div class='header-layer'>", unsafe_allow_html=True)
        with st.form("period_form", clear_on_submit=False):
            c1, c2, c3 = st.columns([1.2, 1.2, 0.7])
            if "date_start" not in st.session_state:
                st.session_state["date_start"] = min_d
            if "date_end" not in st.session_state:
                st.session_state["date_end"] = max_d
            with c1:
                dt_start = st.date_input("DE", value=st.session_state["date_start"], min_value=min_d, max_value=max_d)
            with c2:
                dt_end = st.date_input("ATÉ", value=st.session_state["date_end"], min_value=min_d, max_value=max_d)
            with c3:
                st.markdown("<div style='height:1.65rem;'></div>", unsafe_allow_html=True)
                analyze_clicked = st.form_submit_button("ANALISAR", use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

    if analyze_clicked:
        if dt_start > dt_end:
            st.error("Período inválido: DE deve ser menor ou igual a ATÉ.")
        else:
            st.session_state["date_start"] = dt_start
            st.session_state["date_end"] = dt_end

    selected_start = st.session_state.get("date_start", min_d)
    selected_end = st.session_state.get("date_end", max_d)

    dff = df[(df.index.date >= selected_start) & (df.index.date <= selected_end)].copy()
    if dff.empty:
        st.warning("Não há dados para o período selecionado.")
        return

    current = dff.mean(numeric_only=True)
    if "system_state" in dff.columns and not dff["system_state"].dropna().empty:
        current_state = dff["system_state"].dropna().iloc[-1]
    else:
        current_state = "-"

    st.sidebar.header("Filtros")
    subsystem = st.sidebar.selectbox("Submercado", ["SIN", "SUDESTE", "SUL", "NORDESTE", "NORTE"], index=0)
    source = st.sidebar.multiselect("Fontes", ["hydro", "thermal", "nuclear", "solar", "wind"], default=["hydro", "thermal", "nuclear", "solar", "wind"])
    norm_toggle = st.sidebar.toggle("Exibir normalizados", value=True)
    sim_shift = st.sidebar.slider("BESS shift solar curtailed (%)", 0, 100, 0)

    st.markdown("<div class='tabs-layer'>", unsafe_allow_html=True)
    tabs = st.tabs([
        "📸 Fotografia Operativa",
        "💰 Decomposição Econômica",
        "⚡ Curtailment & Restrições",
        "🧠 Coerência Operativa",
        "🔋 Simulação BESS (Curtailment Shift)",
        "📊 Matriz Horária do SIN",
        "📘 Metodologia & Glossário",
    ])
    st.markdown("</div>", unsafe_allow_html=True)

    # KPI cards abaixo das abas
    cols = st.columns(6)
    kpis = [
        ("PLD médio", current.get("pld", np.nan), " R$/MWh"),
        ("CMO dominante", current.get("cmo_dominante", np.nan), " R$/MWh"),
        ("Custo Total SIN", current.get("sin_cost", np.nan), " R$/h"),
        ("Custo Prudência", current.get("t_prudencia", np.nan), " R$/h"),
        ("Valor Água", current.get("t_hidro", np.nan), " R$/h"),
        ("Curtailment", current.get("curtail_total", np.nan), " MWmed"),
        ("Energia Curtailada", current.get("curtailment_loss", np.nan), " R$/h"),
        ("GFOM", current.get("gfom_pct", np.nan), " %"),
        ("ISR", current.get("isr", np.nan), ""),
        ("IPR", current.get("ipr", np.nan), ""),
        ("Risk Gap", current.get("risk_gap", np.nan), ""),
        ("CVaR Implícito", current.get("cvar_implicit", np.nan), " R$/MWh"),
    ]
    for i, (lab, val, suf) in enumerate(kpis):
        with cols[i % 6]:
            _kpi_card(lab, "-" if pd.isna(val) else f"{val:,.2f}", suf)
    st.info(f"Estado Operativo do SIN: **{current_state}** | Período: **{selected_start}** até **{selected_end}**")

    with tabs[0]:
        st.write(_system_text(current))
        fig = go.Figure()
        for src in [s for s in ["hydro", "thermal", "nuclear", "solar", "wind"] if s in dff.columns and s in source]:
            fig.add_bar(x=dff.index, y=dff[src], name=src)
        if "load" in dff.columns:
            fig.add_scatter(x=dff.index, y=dff["load"], name="load", mode="lines")
        if "net_load" in dff.columns:
            fig.add_scatter(x=dff.index, y=dff["net_load"], name="net_load", mode="lines")
        fig.update_layout(template="plotly_dark", barmode="stack", height=420)
        st.plotly_chart(fig, width='stretch')

    with tabs[1]:
        decomp_cols = [c for c in ["t_hidro", "t_eletric", "t_prudencia"] if c in dff.columns]
        if decomp_cols:
            fig = px.area(dff.reset_index(), x="index", y=decomp_cols, template="plotly_dark")
            st.plotly_chart(fig, width='stretch')
        if "t_prudencia" in dff.columns and "sin_cost" in dff.columns:
            prud_share = (dff["t_prudencia"] / dff["sin_cost"].replace(0, np.nan) * 100)
            st.line_chart(prud_share)

    with tabs[2]:
        if "curtail_total" in dff.columns:
            st.plotly_chart(
                px.bar(
                    dff.reset_index(),
                    x="index",
                    y=[c for c in ["curtail_solar", "curtail_wind", "curtail_total"] if c in dff.columns],
                    template="plotly_dark",
                ),
                width='stretch',
            )
        st.caption("Distribuição por tipo de restrição disponível no painel horário do core quando fornecido pelo ONS.")

    with tabs[3]:
        metrics = {
            "Risk Gap": current.get("risk_gap", np.nan),
            "CVaR": current.get("cvar_implicit", np.nan),
            "EAR_norm": np.nan,
            "ENA_norm": np.nan,
            "Load pressure": np.nan,
        }
        norm = ((core.get("economic") or {}).get("normalization_hourly") or {})
        if norm_toggle and norm and not dff.empty:
            tkey = dff.index[-1].strftime("%Y-%m-%d %H:%M:%S")
            metrics["EAR_norm"] = (norm.get("EAR_norm") or {}).get(tkey, np.nan)
            metrics["ENA_norm"] = (norm.get("ENA_norm") or {}).get(tkey, np.nan)
            metrics["Load pressure"] = (norm.get("Load_norm") or {}).get(tkey, np.nan)
        score_vals = [v for v in metrics.values() if pd.notna(v)]
        coherence = 100 - np.clip(np.nanmean(np.abs(score_vals)) * 25 if score_vals else np.nan, 0, 100)
        color = "🟢" if coherence >= 70 else ("🟡" if coherence >= 40 else "🔴")
        st.metric("Coherence score", "-" if pd.isna(coherence) else f"{coherence:.1f}")
        st.markdown(f"Classificação: {color}")
        st.json(metrics)

    with tabs[4]:
        sim = dff.copy()
        if not sim.empty and "curtail_solar" in sim.columns:
            frac = sim_shift / 100.0
            energy_shift = sim["curtail_solar"].fillna(0) * frac
            night = sim.index.hour.isin([19, 20, 21, 22, 23])
            if night.any():
                per_hour = energy_shift.sum() / max(int(night.sum()), 1)
                thermal_before = sim.get("thermal", pd.Series(0, index=sim.index)).fillna(0)
                hydro_before = sim.get("hydro", pd.Series(0, index=sim.index)).fillna(0)
                thermal_reduction = np.minimum(thermal_before.where(night, 0), per_hour)
                rem = np.maximum(per_hour - thermal_reduction, 0)
                hydro_reduction = np.minimum(hydro_before.where(night, 0), rem)
                thermal_after = thermal_before - thermal_reduction
                hydro_after = hydro_before - hydro_reduction
                pld_proxy_after = sim.get("pld", pd.Series(np.nan, index=sim.index)) * (1 - 0.15 * (thermal_reduction / thermal_before.replace(0, np.nan)).fillna(0))
                out = pd.DataFrame(
                    {
                        "SIN cost before": sim.get("sin_cost", pd.Series(np.nan, index=sim.index)),
                        "SIN cost after": sim.get("load", pd.Series(np.nan, index=sim.index)) * pld_proxy_after,
                        "thermal before": thermal_before,
                        "thermal after": thermal_after,
                        "hydro before": hydro_before,
                        "hydro after": hydro_after,
                    }
                )
                st.plotly_chart(px.line(out.reset_index(), x="index", y=out.columns, template="plotly_dark"), width='stretch')

    with tabs[5]:
        matrix_cols = [
            c
            for c in [
                "pld",
                "cmo_dominante",
                "load",
                "net_load",
                "hydro",
                "thermal",
                "nuclear",
                "solar",
                "wind",
                "gfom_pct",
                "curtail_total",
                "ear",
                "ena",
                "risk_gap",
                "system_state",
            ]
            if c in dff.columns
        ]
        m = dff[matrix_cols].copy()
        if not m.empty:
            m["interpretacao"] = m.apply(_system_text, axis=1)
            st.dataframe(m, width='stretch', height=420)
            st.download_button(
                "Exportar CSV",
                data=m.reset_index().to_csv(index=False).encode("utf-8"),
                file_name="matriz_horaria_sin.csv",
                mime="text/csv",
            )

    with tabs[6]:
        with st.expander("Decomposição T_total"):
            st.markdown("T_total = T_hidro + T_eletric + T_prudencia")
        with st.expander("CVaR implícito"):
            st.markdown("CVaR_implicit = max(PLD - CMO, 0)")
        with st.expander("GFOM, ISR, IPR"):
            st.markdown("GFOM% relaciona despacho fora de mérito; ISR/IPR representam saturação renovável versus carga/carga líquida.")
        with st.expander("Curtailment"):
            st.markdown("Perda econômica = curtailed_renewable × PLD; curtailment evitável depende da inflexibilidade térmica.")


if __name__ == "__main__":
    main()
