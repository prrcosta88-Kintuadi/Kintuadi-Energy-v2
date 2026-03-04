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

    return _ensure_hourly(df)


def _fmt_ptbr(value: Any, decimals: int = 2) -> str:
    try:
        if value is None or pd.isna(value):
            return "-"
        s = f"{float(value):,.{decimals}f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def _fmt_money_compact(value: Any) -> str:
    if value is None or pd.isna(value):
        return "-"
    v = float(value)
    av = abs(v)
    if av >= 1_000_000:
        return f"R$ {_fmt_ptbr(v/1_000_000, 2)} MM"
    if av >= 1_000:
        return f"R$ {_fmt_ptbr(v/1_000, 2)} k"
    return f"R$ {_fmt_ptbr(v, 2)}"


def _prepare_logo(path: Path) -> Optional[Path]:
    """Recorta bordas escuras do PNG para reduzir fundo/preenchimento visual."""
    if not path.exists():
        return None
    try:
        from PIL import Image

        img = Image.open(path).convert("RGBA")
        arr = np.array(img)
        # pixels não quase-pretos e não transparentes
        mask = (arr[:, :, 3] > 5) & ((arr[:, :, 0] > 20) | (arr[:, :, 1] > 20) | (arr[:, :, 2] > 20))
        if not mask.any():
            return path
        ys, xs = np.where(mask)
        x0, x1 = xs.min(), xs.max()
        y0, y1 = ys.min(), ys.max()
        cropped = img.crop((max(0, x0 - 4), max(0, y0 - 4), min(img.width, x1 + 5), min(img.height, y1 + 5)))
        out = Path("data") / "emblema_maatria_trimmed.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(out)
        return out
    except Exception:
        return path


def _kpi_card(label: str, value: str, border_color: str):
    st.markdown(
        f"""
        <div style='background:#131722;border:1px solid #2a2f3a;border-top:3px solid {border_color};
                    border-radius:12px;padding:10px 12px;height:95px;'>
          <div style='font-size:12px;color:#9ba3af;'>{label}</div>
          <div style='font-size:23px;color:#f3f4f6;font-weight:700;line-height:1.2'>{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _system_text(row: pd.Series) -> str:
    s = row.get("system_state")
    if isinstance(s, str) and s:
        return f"Regime {s} com carga líquida de {_fmt_ptbr(row.get('net_load', np.nan), 0)} MWmed."
    return "Sem dados suficientes para diagnóstico automático da hora selecionada."


def _plot_df(dff: pd.DataFrame) -> pd.DataFrame:
    out = dff.copy().reset_index()
    first_col = out.columns[0]
    if first_col != "instante":
        out = out.rename(columns={first_col: "instante"})
    return out


def _ensure_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """Consolida qualquer série semihorária em base horária (média de :00 e :30)."""
    if df.empty:
        return df
    out = df.copy()
    out.index = pd.to_datetime(out.index, errors="coerce")
    out = out[~out.index.isna()]
    if out.empty:
        return out
    out["hora_ref"] = out.index.floor("h")
    num_cols = out.select_dtypes(include=[np.number]).columns.tolist()
    other_cols = [c for c in out.columns if c not in num_cols + ["hora_ref"]]
    agg_map = {c: "mean" for c in num_cols}
    agg_map.update({c: "last" for c in other_cols})
    out = out.groupby("hora_ref", as_index=True).agg(agg_map).sort_index()
    out.index.name = "instante"
    return out


def main():
    st.set_page_config(page_title="MAÁTria Energia", layout="wide", initial_sidebar_state="collapsed")

    st.markdown(
        """
        <style>
          .stApp { background-color:#0b0f14; color:#f3f4f6; }
          [data-testid="stSidebar"] { display:none !important; }
          .block-container { padding-top: 40px; }
          .fixed-header { position: fixed; top: 0; left:0; right:0; z-index:999; background:#0b0f14; }
          .full-bleed-line { height:1px; background:#c8a44d; width:100vw; margin-left:calc(50% - 50vw); }
          .tabs-layer { background: linear-gradient(180deg, #0b1222 0%, #070d1a 100%); padding:0.25rem 0.4rem 0.05rem 0.4rem; }
          label { color:#ffffff !important; font-weight:700 !important; }
          .stTabs [data-baseweb="tab-list"] { gap: 0.15rem; flex-wrap: nowrap !important; overflow-x: auto !important; scrollbar-width: thin; }
          .stTabs [data-baseweb="tab"] { color:#e5e7eb; border-radius:6px; padding:0.25rem 0.45rem; font-size:0.78rem; white-space:nowrap; }
          .stTabs [aria-selected="true"] { background:#152238 !important; color:#f8fafc !important; border:1px solid #c8a44d !important; }
          div[data-testid="stFormSubmitButton"] > button {
            background:#d4af37 !important; color:#111827 !important; font-weight:100 !important; border:1px solid #b38f2b !important;
          }
          div[data-testid="stFormSubmitButton"] > button:hover { background:#e3bf4c !important; color:#000 !important; }
          .cards-row { margin-bottom: 10px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    core = _load_core()
    if not core:
        st.error("core_analysis_latest.json não encontrado.")
        return

    df = _build_hourly_df(core)
    if df.empty:
        st.warning("Sem séries horárias suficientes no core para renderizar o painel.")
        return

    min_d, max_d = df.index.min().date(), df.index.max().date()
    default_day = date.today() - pd.Timedelta(days=1)
    if default_day < min_d or default_day > max_d:
        default_day = max_d

    if "date_start" not in st.session_state:
        st.session_state["date_start"] = default_day
    if "date_end" not in st.session_state:
        st.session_state["date_end"] = default_day

    st.markdown("<div class='fixed-header'>", unsafe_allow_html=True)
    st.markdown("<div class='full-bleed-line'></div>", unsafe_allow_html=True)

    colc1, colc2, colc3 = st.columns([1, 2, 1])
    with colc2:
        logo = _prepare_logo(Path("streamlit/img/emblema_maatria.png"))
        if logo and logo.exists():
            st.image(str(logo), width=210)
        else:
            st.markdown("## MAÁTria Energia")

    st.markdown("<div class='full-bleed-line'></div>", unsafe_allow_html=True)
    st.markdown("<div class='header-layer'>", unsafe_allow_html=True)

    analyze_clicked = False
    form_col, _ = st.columns([0.4, 0.6])
    with form_col:
        with st.form("period_form", clear_on_submit=False):
            c1, c2, c3 = st.columns([1.05, 1.05, 0.8])
            with c1:
                dt_start = st.date_input("DE", value=st.session_state["date_start"], min_value=min_d, max_value=max_d)
            with c2:
                dt_end = st.date_input("ATÉ", value=st.session_state["date_end"], min_value=min_d, max_value=max_d)
            with c3:
                st.markdown("<div style='height:1.65rem;'></div>", unsafe_allow_html=True)
                analyze_clicked = st.form_submit_button("ANALISAR", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div class='full-bleed-line'></div>", unsafe_allow_html=True)
    st.markdown("<div class='tabs-layer'>", unsafe_allow_html=True)

    tabs = st.tabs([
        "📸 Fotografia Operativa",
        "💰 Decomposição Econômica",
        "⚡ Curtailment & Restrições",
        "🧠 Coerência Operativa",
        "🔋 Simulação BESS",
        "📊 Matriz Horária do SIN",
        "📘 Metodologia & Glossário",
    ])

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div class='full-bleed-line'></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if analyze_clicked:
        if dt_start > dt_end:
            st.error("Período inválido: DE deve ser menor ou igual a ATÉ.")
        else:
            st.session_state["date_start"] = dt_start
            st.session_state["date_end"] = dt_end

    selected_start = st.session_state.get("date_start", default_day)
    selected_end = st.session_state.get("date_end", default_day)

    dff = df[(df.index.date >= selected_start) & (df.index.date <= selected_end)].copy()
    if dff.empty:
        st.warning("Não há dados para o período selecionado.")
        return

    photo_day = min(max_d, date.today() - pd.Timedelta(days=1))
    if photo_day < selected_start or photo_day > selected_end:
        photo_day = selected_end
    dff_photo = dff[dff.index.date == photo_day].copy()
    if dff_photo.empty:
        dff_photo = dff.copy()

    dff = _ensure_hourly(dff)
    dff_photo = _ensure_hourly(dff_photo)

    current = dff.mean(numeric_only=True)
    current_state = dff["system_state"].dropna().iloc[-1] if "system_state" in dff.columns and not dff["system_state"].dropna().empty else "-"

    # Totais do período selecionado (soma hora a hora)
    total_sin_cost = pd.to_numeric(dff.get("sin_cost", pd.Series(dtype=float)), errors="coerce").sum(min_count=1)
    total_prud = pd.to_numeric(dff.get("t_prudencia", pd.Series(dtype=float)), errors="coerce").sum(min_count=1)
    total_agua = pd.to_numeric(dff.get("t_hidro", pd.Series(dtype=float)), errors="coerce").sum(min_count=1)
    total_curt_loss = pd.to_numeric(dff.get("curtailment_loss", pd.Series(dtype=float)), errors="coerce").sum(min_count=1)
    total_gfom = pd.to_numeric(dff.get("gfom_pct", pd.Series(dtype=float)), errors="coerce").sum(min_count=1)
    total_isr = pd.to_numeric(dff.get("isr", pd.Series(dtype=float)), errors="coerce").sum(min_count=1)
    total_ipr = pd.to_numeric(dff.get("ipr", pd.Series(dtype=float)), errors="coerce").sum(min_count=1)

    kpis = [
        ("PLD médio", f"R$ {_fmt_ptbr(current.get('pld', np.nan),2)}", "#22c55e"),
        ("CMO dominante", f"R$ {_fmt_ptbr(current.get('cmo_dominante', np.nan),2)}", "#3b82f6"),
        ("Custo Total SIN", _fmt_money_compact(total_sin_cost), "#f59e0b"),
        ("Custo Prudência", _fmt_money_compact(total_prud), "#ef4444"),
        ("Valor Água", _fmt_money_compact(total_agua), "#14b8a6"),
        ("Curtailment", f"{_fmt_ptbr(current.get('curtail_total', np.nan),2)} MWmed", "#a78bfa"),
        ("Valor (R$) Curtailment", _fmt_money_compact(total_curt_loss), "#eab308"),
        ("GFOM", _fmt_ptbr(total_gfom,2), "#38bdf8"),
        ("ISR", _fmt_ptbr(total_isr,2), "#f97316"),
        ("IPR", _fmt_ptbr(total_ipr,2), "#84cc16"),
        ("Risk Gap", _fmt_ptbr(current.get("risk_gap", np.nan),2), "#fb7185"),
        ("CVaR Implícito", f"R$ {_fmt_ptbr(current.get('cvar_implicit', np.nan),2)}", "#60a5fa"),
    ]

    for base in (0, 6):
        cols = st.columns(6)
        for i in range(6):
            idx = base + i
            if idx < len(kpis):
                lab, val, color = kpis[idx]
                with cols[i]:
                    _kpi_card(lab, val, color)
        st.markdown("<div class='cards-row'></div>", unsafe_allow_html=True)

    st.info(f"Estado Operativo do SIN: **{current_state}** | Período: **{selected_start}** até **{selected_end}**")

    with tabs[0]:
        st.caption(f"Fotografia operativa do dia **{photo_day}** (D-1 por padrão).")
        st.caption("Montagem: séries horárias observadas de geração por fonte + carga e carga líquida (`Carga - (Solar + Eólica)`).")
        st.write(_system_text(current))
        fig = go.Figure()
        labels = {
            "hydro": "Hidro", "thermal": "Térmica", "nuclear": "Nuclear", "solar": "Solar", "wind": "Eólica"
        }
        for src in ["hydro", "thermal", "nuclear", "solar", "wind"]:
            if src in dff_photo.columns:
                fig.add_bar(x=dff_photo.index, y=dff_photo[src], name=labels[src])
        if "load" in dff_photo.columns:
            fig.add_scatter(x=dff_photo.index, y=dff_photo["load"], name="Carga", mode="lines")
        if "net_load" in dff_photo.columns:
            fig.add_scatter(x=dff_photo.index, y=dff_photo["net_load"], name="Carga Líquida", mode="lines")
        fig.update_layout(template="plotly_dark", barmode="stack", height=420)
        st.plotly_chart(fig, width="stretch")
        with st.expander("Ver dados do gráfico (hora a hora)"):
            plot_cols = [c for c in ["load", "net_load", "solar", "wind", "hydro", "thermal", "nuclear"] if c in dff_photo.columns]
            st.dataframe(_plot_df(dff_photo[plot_cols]), width="stretch", height=280)

    with tabs[1]:
        pdf = _plot_df(dff)
        decomp_cols = [c for c in ["t_hidro", "t_eletric", "t_prudencia"] if c in pdf.columns]
        if decomp_cols:
            st.caption("Montagem: decomposição econômica horária `T_total = T_hidro + T_elétrico + T_prudência`.")
            fig = px.bar(pdf, x="instante", y=decomp_cols, template="plotly_dark", barmode="stack")
            fig.update_layout(title="Decomposição horária empilhada (R$/h)")
            st.plotly_chart(fig, width="stretch")
            with st.expander("Ver dados do gráfico (hora a hora)"):
                st.dataframe(pdf[["instante"] + decomp_cols], width="stretch", height=280)

        if {"thermal", "thermal_prudential_dispatch"}.issubset(dff.columns):
            g2 = _plot_df(dff[["thermal", "thermal_prudential_dispatch"]])
            fig2 = px.line(g2, x="instante", y=["thermal", "thermal_prudential_dispatch"], template="plotly_dark")
            fig2.update_layout(title="Despacho térmico total vs despacho prudencial (MWmed)")
            st.plotly_chart(fig2, width="stretch")
            st.caption("A segunda curva mostra a parcela térmica associada à prudência operativa.")
            with st.expander("Ver dados do gráfico térmico (hora a hora)"):
                st.dataframe(g2, width="stretch", height=260)

    with tabs[2]:
        cdf = _plot_df(dff)
        cols = [c for c in ["curtail_solar", "curtail_wind", "curtail_total"] if c in cdf.columns]
        if cols:
            st.caption("Montagem: curtailment horário por fonte (solar/eólica) e total agregado.")
            fig = px.bar(cdf, x="instante", y=cols, template="plotly_dark", barmode="group")
            st.plotly_chart(fig, width="stretch")
            with st.expander("Ver dados do gráfico (hora a hora)"):
                st.dataframe(cdf[["instante"] + cols], width="stretch", height=280)
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
        if norm and not dff.empty:
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
        sim_shift = st.slider("Percentual de deslocamento do curtailment solar para 19h–23h", 0, 100, 0)
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
                out = pd.DataFrame({
                    "SIN cost before": sim.get("sin_cost", pd.Series(np.nan, index=sim.index)),
                    "SIN cost after": sim.get("load", pd.Series(np.nan, index=sim.index)) * pld_proxy_after,
                    "thermal before": thermal_before,
                    "thermal after": thermal_after,
                    "hydro before": hydro_before,
                    "hydro after": hydro_after,
                })
                op = _plot_df(out)
                st.plotly_chart(px.line(op, x="instante", y=[c for c in op.columns if c != "instante"], template="plotly_dark"), width="stretch")
                with st.expander("Ver dados da simulação (hora a hora)"):
                    st.dataframe(op, width="stretch", height=280)

    with tabs[5]:
        matrix_cols = [
            c for c in ["pld","cmo_dominante","load","net_load","hydro","thermal","nuclear","solar","wind","gfom_pct","curtail_total","ear","ena","risk_gap","system_state"] if c in dff.columns
        ]
        m = dff[matrix_cols].copy()
        if not m.empty:
            m["interpretacao"] = m.apply(_system_text, axis=1)
            st.dataframe(m, width="stretch", height=420)
            st.download_button("Exportar CSV", data=m.reset_index().to_csv(index=False).encode("utf-8"), file_name="matriz_horaria_sin.csv", mime="text/csv")

    with tabs[6]:
        st.markdown("### 📘 Metodologia & Glossário")
        st.caption("Visão prática para operação e mercado: o que é calculado, por que importa e como interpretar.")

        with st.expander("🎯 1) Propósito da Plataforma", expanded=False):
            st.markdown("""
            - A plataforma **não prevê PLD**.
            - O foco é avaliar a **coerência operativa** entre:
              - hidrologia
              - disponibilidade de geração
              - penetração renovável
              - despacho térmico
              - curtailment
              - preços marginais

            **Fotografia Operativa do SIN** = diagnóstico **hora a hora** da condição física e econômica do sistema.
            """)
            st.info("Use esta aba como guia de leitura operacional, não como modelo de previsão.")

        with st.expander("⚙️ 2) Conceitos Fundamentais do SIN", expanded=False):
            st.markdown("""
            **Carga (Demanda)**  
            Consumo elétrico total observado em uma hora.

            **Geração**  
            Energia efetivamente produzida pelas fontes.

            **Carga Líquida**  
            Demanda que sobra para fontes flexíveis (hidro + térmica).

            **Fórmula:**  
            `Carga Líquida = Carga − (Solar + Eólica)`

            **Valor da Água**  
            Custo de oportunidade de usar água agora versus guardar para frente.

            **Proxy usado:** `CMO`.
            """)

        with st.expander("📊 3) Métricas Principais", expanded=False):
            st.markdown("""
            **GFOM (%)**  
            Despacho térmico fora da ordem de mérito.

            **Fórmula:** `GFOM = Térmica_GFOM / Térmica_Total`

            **Leitura típica:**
            - Baixo: `< 5%`
            - Moderado: `5–15%`
            - Alto: `> 15%`

            ---
            **Curtailment**  
            Renovável disponível que não foi despachada.

            **Causas comuns:**
            - limite de transmissão
            - controle de frequência
            - saturação do sistema
            - inflexibilidade térmica

            **Leitura econômica:** energia barata perdida.

            ---
            **IPR (Índice de Pressão Renovável)**  
            `IPR = Renovável Disponível / Carga`

            ---
            **ISR (Índice de Saturação Renovável)**  
            `ISR = Renovável Disponível / Carga Líquida`

            `ISR > 1` indica risco de saturação estrutural.

            ---
            **EAR (Energia Armazenada)**  
            Estoque dos reservatórios (segurança futura).

            **ENA (Energia Natural Afluente)**  
            Energia hidrológica que entra no sistema.
            - ENA alta: alívio futuro
            - ENA baixa: risco de escassez
            """)
            st.warning("Olhe IPR/ISR junto com curtailment para separar excesso renovável de restrição elétrica.")

        with st.expander("💰 4) Decomposição Econômica do Sistema", expanded=False):
            st.markdown("""
            **Estrutura central:**

            `T_total = T_hidro + T_elétrico + T_prudência`

            - **T_hidro:** custo associado ao valor de oportunidade da água
            - **T_elétrico:** custo estrutural para atender carga
            - **T_prudência:** custo adicional por decisão conservadora de operação

            **Custo da Prudência** = valor extra pago hoje para preservar reservatório.
            """)

        with st.expander("🛡️ 5) CVaR e Aversão ao Risco", expanded=False):
            st.markdown("""
            O ONS otimiza considerando cenários hidrológicos adversos.

            Exemplo de calibração: `(15%, 40%)`
            - piores 15% cenários hidrológicos
            - com peso de 40% na decisão operativa

            Mais aversão a risco tende a gerar:
            `mais térmica → maior PLD`

            **CVaR Implícito:**
            `CVaR_implícito = PLD − CMO dominante`
            """)

        with st.expander("📉 6) Risk Aversion Gap", expanded=False):
            st.markdown("""
            **Definição:**
            `Risk Gap = CVaR_implícito − CVU_médio`

            **Leitura:**
            - positivo: regime de forte precaução
            - próximo de zero: operação neutra
            - negativo: regime de abundância
            """)

        with st.expander("💧 7) Teste de Necessidade Hidráulica", expanded=False):
            st.markdown("""
            **Passo 1 — Geração mandatória:**
            `Renováveis + Nuclear + Térmica inflexível`

            **Passo 2 — Hidro necessária:**
            `Hidro_necessária = Carga − Geração_mandatória`

            **Passo 3 — Comparação com hidro observada:**
            - Hidro observada > necessária → sistema hidro-dominante
            - Hidro observada < necessária → dependência térmica
            """)

        with st.expander("🧾 8) Custo do SIN (R$/h)", expanded=False):
            st.markdown("""
            **Exposição econômica horária:**

            `Custo SIN = Carga × PLD`

            Representa o sinal econômico total de liquidação naquela hora.
            """)

        with st.expander("🔋 9) Curtailment como Armazenamento Implícito", expanded=False):
            st.markdown("""
            Quando solar/eólica entram e reduzem despacho hidráulico,
            parte da água fica guardada.

            Nesse sentido, renováveis funcionam como:
            **"armazenamento hídrico virtual"**.

            **Valor estimado:**
            `Hidro evitada × CMO`
            """)

        with st.expander("🏷️ 10) Classificação Operativa do SIN", expanded=False):
            st.markdown("""
            **Regimes do painel (exemplos):**

            - **Escassez Hidrológica:** baixa folga hídrica e maior pressão térmica
            - **Preservação Hídrica:** estratégia de poupar reservatório
            - **Saturação Renovável:** renovável acima da capacidade de absorção
            - **Stress Operativo:** sinais simultâneos de risco físico e econômico
            - **Equilíbrio Estrutural:** operação estável, sem pressão relevante
            """)

        with st.expander("🧭 11) Como Interpretar o Dashboard", expanded=False):
            st.markdown("""
            **Roteiro rápido de uso:**

            1. Selecione hora/período
            2. Leia os KPIs principais
            3. Verifique o score de coerência
            4. Analise a decomposição de custos
            5. Confira causas de curtailment
            6. Rode a simulação BESS
            7. Compare a resposta do sistema

            **Objetivo final:** entender se o comportamento do PLD está fisicamente coerente.
            """)
            st.success("Leitura executiva: combine sempre sinais físicos (carga, geração, reservatórios) com sinais econômicos (PLD, CMO, custos).")


if __name__ == "__main__":
    main()
