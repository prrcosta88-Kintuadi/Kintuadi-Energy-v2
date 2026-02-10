"""
Premium user-data module (v2).

Handles user-provided consumption, generation and contracts data,
aligns with MCP hourly structure and computes physical and financial exposure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import pandas as pd


# ----------------------------
# CONSTANTS
# ----------------------------

PREMIUM_SHEET = "dados_usuario"
SHEET_CONSUMO = "consumo"
SHEET_GERACAO = "geracao"
SHEET_CONTRATOS = "contratos"

SUBMERCADO_MAP = {
    "SE": "SE",
    "SE/CO": "SE",
    "SUDESTE": "SE",
    "SUL": "S",
    "S": "S",
    "NE": "NE",
    "NORTE": "N",
    "N": "N",
}

TEMPLATE_COLUMNS = [
    "data",
    "hora",
    "submercado",
    "consumo_mwh",
    "geracao_mwh",
    "contratos_mwh",
    "preco_contrato",
]


# ----------------------------
# DATA STRUCTURES
# ----------------------------

@dataclass
class PremiumResult:
    data: pd.DataFrame
    resumo: Dict[str, float]
    alertas: List[str]


# ----------------------------
# TEMPLATE
# ----------------------------

def generate_premium_template(path: str) -> None:
    df = pd.DataFrame(columns=TEMPLATE_COLUMNS)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=PREMIUM_SHEET, index=False)


# ----------------------------
# LOAD & NORMALIZE
# ----------------------------

def load_premium_excel(file_path_or_buffer: Any) -> pd.DataFrame:
    xls = pd.ExcelFile(file_path_or_buffer)
    sheets = xls.sheet_names

    if PREMIUM_SHEET in sheets:
        df = pd.read_excel(xls, PREMIUM_SHEET)
        return _normalize_single_sheet(df)

    if all(s in sheets for s in [SHEET_CONSUMO, SHEET_GERACAO, SHEET_CONTRATOS]):
        consumo = pd.read_excel(xls, SHEET_CONSUMO)
        geracao = pd.read_excel(xls, SHEET_GERACAO)
        contratos = pd.read_excel(xls, SHEET_CONTRATOS)
        return _merge_multi_sheet(consumo, geracao, contratos)

    raise ValueError("Template inválido.")


def _normalize_single_sheet(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in TEMPLATE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas ausentes: {missing}")
    return _normalize_types(df.copy())


def _merge_multi_sheet(consumo, geracao, contratos) -> pd.DataFrame:
    consumo = _normalize_basic(consumo, "consumo_mwh")
    geracao = _normalize_basic(geracao, "geracao_mwh")
    contratos = _normalize_basic(contratos, "contratos_mwh")

    merged = consumo.merge(geracao, on=["data", "hora", "submercado"], how="outer")
    merged = merged.merge(contratos, on=["data", "hora", "submercado"], how="outer")

    merged["preco_contrato"] = merged.get("preco_contrato", 0)
    return _normalize_types(merged)


def _normalize_basic(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    required = {"data", "hora", "submercado", value_col}
    if not required.issubset(df.columns):
        raise ValueError(f"Colunas obrigatórias ausentes em {value_col}")
    return df.copy()


def _normalize_types(df: pd.DataFrame) -> pd.DataFrame:
    df["data"] = pd.to_datetime(df["data"]).dt.date
    df["hora"] = pd.to_numeric(df["hora"], errors="coerce").astype(int)

    if not df["hora"].between(1, 24).all():
        raise ValueError("Hora deve estar entre 1 e 24 (hora MCP).")

    df["hora_mcp"] = df["hora"] - 1  # ajuste técnico
    df["submercado"] = (
        df["submercado"]
        .astype(str)
        .str.upper()
        .map(SUBMERCADO_MAP)
        .fillna("DESCONHECIDO")
    )

    for col in ["consumo_mwh", "geracao_mwh", "contratos_mwh", "preco_contrato"]:
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0.0)

    df["timestamp"] = pd.to_datetime(df["data"].astype(str)) + pd.to_timedelta(
        df["hora_mcp"], unit="h"
    )

    return df


# ----------------------------
# PLD & EXPOSURE
# ----------------------------

def build_pld_lookup(ccee_records: List[Dict[str, Any]]) -> Dict[Tuple[str, int, str], float]:
    lookup = {}
    for r in ccee_records:
        try:
            data = pd.to_datetime(r.get("data") or r.get("DATA")).date()
            hora = int(r.get("hora") or r.get("HORA"))
            sub = SUBMERCADO_MAP.get(str(r.get("submercado") or r.get("SUBMERCADO")).upper())
            pld = float(r.get("pld") or r.get("PLD") or r.get("PLD_HORA"))
            lookup[(str(data), hora, sub)] = pld
        except Exception:
            continue
    return lookup


def calculate_exposures(df: pd.DataFrame, pld_lookup: Dict) -> pd.DataFrame:
    df = df.copy()

    # Exposição física
    df["exposicao_mwh"] = df["consumo_mwh"] - df["geracao_mwh"]

    # Liquidação financeira MCP
    df["pld"] = df.apply(
        lambda r: pld_lookup.get((str(r["data"]), r["hora"], r["submercado"]), 0.0),
        axis=1,
    )

    df["resultado_mcp"] = df["exposicao_mwh"] * df["pld"]

    # Resultado contratual
    df["resultado_contratos"] = (
        df["contratos_mwh"] * (df["pld"] - df["preco_contrato"])
    )

    df["resultado_total"] = df["resultado_mcp"] + df["resultado_contratos"]
    return df


# ----------------------------
# SUMMARY
# ----------------------------

def build_premium_summary(df: pd.DataFrame) -> PremiumResult:
    if df.empty:
        return PremiumResult(df, {}, ["Sem dados do usuário."])

    resumo = {
        "exposicao_mwh_total": float(df["exposicao_mwh"].sum()),
        "resultado_financeiro_total": float(df["resultado_total"].sum()),
        "pld_medio": float(df["pld"].mean()) if not df["pld"].empty else 0,
    }

    alertas = []
    if resumo["exposicao_mwh_total"] > 0:
        alertas.append("Perfil estruturalmente exposto ao MCP (comprador líquido).")
    if resumo["resultado_financeiro_total"] < 0:
        alertas.append("Resultado financeiro negativo no período.")

    return PremiumResult(df, resumo, alertas)
