#!/usr/bin/env python3
"""
Dashboard Espelho (read-only)
- Lê somente core_analysis_latest.json (sem executar coleta/análise)
- Sem sidebar, para publicação leve no Render
"""

import json
import os
from datetime import datetime, date
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(
    page_title="Kintuadi Energy Espelho",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def _load_core() -> Optional[Dict[str, Any]]:
    candidates = ["core_analysis_latest.json", os.path.join("data", "core_analysis_latest.json")]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
    return None


def _norm_sub(value: Any) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip().upper().replace("/", "").replace("-", "").replace(" ", "")
    mapping = {
        "1": "SUDESTE", "2": "SUL", "3": "NORDESTE", "4": "NORTE",
        "N": "NORTE", "NE": "NORDESTE", "SE": "SUDESTE", "SECO": "SUDESTE", "S": "SUL",
        "NORTE": "NORTE", "NORDESTE": "NORDESTE", "SUDESTE": "SUDESTE", "SUL": "SUL",
    }
    return mapping.get(v)


def _classify_hour(pld: Optional[float], ear_mensal: Optional[float], termica_mensal: Optional[float], pld_ref: Optional[float]) -> str:
    if pld is None or ear_mensal is None:
        return "dados_insuficientes"
    if pld >= 785.27 * 0.8 and ear_mensal < 50:
        return "estresse_hidrico"
    if pld <= 57.31 * 1.2 and ear_mensal > 65:
        return "abundancia_hidrica"
    if termica_mensal is not None and termica_mensal > 25 and pld_ref is not None and pld > pld_ref:
        return "pressao_termica"
    return "equilibrio_operacional"


def _hourly_table(core: Dict[str, Any], selected_day: date, submercado: str = "SIN") -> pd.DataFrame:
    rows = core.get("ccee", {}).get("data", [])
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    req = {"mes_referencia", "dia", "hora", "pld_hora", "submercado"}
    if not req.issubset(df.columns):
        return pd.DataFrame()

    df["mes_referencia"] = df["mes_referencia"].astype(str).str.zfill(6)
    df["dia"] = pd.to_numeric(df["dia"], errors="coerce")
    df["hora"] = pd.to_numeric(df["hora"], errors="coerce")
    df["pld_hora"] = pd.to_numeric(df["pld_hora"], errors="coerce")
    df["submercado_norm"] = df["submercado"].map(_norm_sub)

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
    hourly = hourly.rename(columns={"instante": "hora", "pld_hora": "pld_hora_medio"})

    adv = core.get("advanced_metrics", {})
    month_key = day_ts.strftime("%Y-%m")
    ear_m = (adv.get("ear_media_mensal") or {}).get(month_key)
    ena_m = (adv.get("ena_media_mensal") or {}).get(month_key)

    termica_m = None
    for row in (adv.get("matriz_cenario_mensal") or []):
        if isinstance(row, dict) and row.get("mes") == month_key:
            termica_m = row.get("percentual_termica_medio")
            break

    pld_ref = (core.get("prices") or {}).get("pld_medio")
    hourly["ear_mensal"] = ear_m
    hourly["ena_mensal"] = ena_m
    hourly["percentual_termica_mensal"] = termica_m
    hourly["cenario"] = hourly["pld_hora_medio"].apply(
        lambda v: _classify_hour(
            float(v) if pd.notna(v) else None,
            float(ear_m) if ear_m is not None else None,
            float(termica_m) if termica_m is not None else None,
            float(pld_ref) if pld_ref is not None else None,
        )
    )
    return hourly


def main() -> None:
    core = _load_core()
    st.title("⚡ Kintuadi Energy — Dashboard Espelho")

    if not core:
        st.error("core_analysis_latest.json não encontrado. Publique este arquivo junto do dashboard.")
        return

    ts = core.get("timestamp")
    st.caption(f"Modo leitura | Última atualização: {ts if ts else 'N/A'}")

    hyd = core.get("hydrology", {})
    prices = core.get("prices", {})
    adv = core.get("advanced_metrics", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("EAR médio", f"{hyd.get('ear_medio'):.2f}%" if isinstance(hyd.get("ear_medio"), (int, float)) else "—")
    c2.metric("ENA média", f"{hyd.get('ena_media'):.2f}" if isinstance(hyd.get("ena_media"), (int, float)) else "—")
    c3.metric("PLD médio", f"R$ {prices.get('pld_medio'):.2f}" if isinstance(prices.get("pld_medio"), (int, float)) else "—")
    c4.metric("Status avançado", adv.get("status", "—"))

    st.markdown("### 📈 Consulta horária por dia")
    dcol1, dcol2 = st.columns([1, 1])
    with dcol1:
        dia = st.date_input("Dia", value=datetime.now().date())
    with dcol2:
        sm = st.selectbox("Submercado", ["SIN", "NORTE", "NORDESTE", "SUDESTE", "SUL"], index=0)

    dfh = _hourly_table(core, dia, sm)
    if dfh.empty:
        st.info("Sem dados para o dia/submercado selecionado.")
    else:
        st.dataframe(dfh, width="stretch", hide_index=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dfh["hora"], y=dfh["pld_hora_medio"], mode="lines+markers", name="PLD"))
        fig.update_layout(template="plotly_dark", height=320, xaxis_title="Hora", yaxis_title="R$/MWh")
        st.plotly_chart(fig, width="stretch")

    st.markdown("### 🧠 Matriz mensal de cenário (do core)")
    matriz = adv.get("matriz_cenario_mensal", [])
    if matriz:
        st.dataframe(pd.DataFrame(matriz), width="stretch", hide_index=True)
    else:
        st.info("Matriz mensal não disponível no core atual.")


if __name__ == "__main__":
    main()
