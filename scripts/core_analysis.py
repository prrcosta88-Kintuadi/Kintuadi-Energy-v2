"""Core analysis utilities for Kintuadi Energy.

This module generates CORE insights from ONS + CCEE data without any
user-specific inputs. All outputs are designed to be explainable and
aligned with SIN physical fundamentals.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def _safe_get(dct: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    current = dct
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return current if current is not None else default


def _extract_sources(raw_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if "sources" in raw_data:
        return {
            "ons": raw_data.get("sources", {}).get("ons", {}),
            "ccee": raw_data.get("sources", {}).get("ccee", {}),
        }
    return {
        "ons": raw_data.get("ons", {}),
        "ccee": raw_data.get("ccee", {}),
    }


def _hydrology_status(volume_medio: Optional[float]) -> Dict[str, Any]:
    if volume_medio is None:
        return {
            "status": "indisponível",
            "classe": "dados ausentes",
            "descricao": "Volume médio não disponível.",
        }

    if volume_medio < 40:
        classe = "crítico"
    elif volume_medio < 55:
        classe = "alerta"
    elif volume_medio < 70:
        classe = "atenção"
    elif volume_medio < 85:
        classe = "confortável"
    else:
        classe = "abundante"

    return {
        "status": "disponível",
        "classe": classe,
        "descricao": "Classificação baseada no volume médio dos reservatórios.",
    }


def _price_alignment(volume_medio: Optional[float], pld_medio: Optional[float]) -> Dict[str, Any]:
    if volume_medio is None or pld_medio is None:
        return {
            "coerencia": "indisponível",
            "descricao": "Sem dados suficientes para avaliar coerência preço-fundamento.",
        }

    if volume_medio > 75 and pld_medio > 300:
        return {
            "coerencia": "desalinhado",
            "descricao": "PLD elevado em cenário de conforto hídrico.",
        }
    if volume_medio < 50 and pld_medio < 150:
        return {
            "coerencia": "desalinhado",
            "descricao": "PLD baixo em cenário hidrológico restrito.",
        }

    return {
        "coerencia": "coerente",
        "descricao": "PLD compatível com fundamentos hidrológicos.",
    }


def build_core_analysis(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build CORE analysis output with KPIs, indicators, and timeseries.

    This function is resilient to partial datasets and returns explainable
    placeholders when information is not available yet.
    """
    sources = _extract_sources(raw_data)
    ons = sources.get("ons", {})
    ccee = sources.get("ccee", {})

    ons_stats = _safe_get(ons, "statistics", "geral", default={})
    ccee_stats = _safe_get(ccee, "statistics", "geral", default={})

    volume_medio = ons_stats.get("volume_medio")
    pld_medio = ccee_stats.get("pld_medio")
    pld_std = ccee_stats.get("pld_std")

    hydrology = {
        "volume_medio": volume_medio,
        "ena": ons_stats.get("ena_medio"),
        "ear": ons_stats.get("ear_medio"),
        "tendencia": ons_stats.get("tendencia"),
        "conforto_hidrico": _hydrology_status(volume_medio),
    }

    operation = {
        "geracao": _safe_get(ons, "operacao", "geracao", default=None),
        "carga": _safe_get(ons, "operacao", "carga", default=None),
        "termicas": _safe_get(ons, "operacao", "termicas", default=None),
        "cvu": _safe_get(ons, "operacao", "cvu", default=None),
        "status": "parcial" if _safe_get(ons, "operacao") else "indisponível",
    }

    prices = {
        "pld_medio": pld_medio,
        "pld_volatilidade": pld_std,
        "pld_volatilidade_percentual": (
            (pld_std / pld_medio * 100) if pld_medio else None
        ),
        "coerencia_fundamentos": _price_alignment(volume_medio, pld_medio),
        "timeseries": ccee.get("timeseries", []),
    }

    mcp = {
        "sumario_mensal": _safe_get(ccee, "mcp_summary"),
        "status": "parcial" if _safe_get(ccee, "mcp_summary") else "indisponível",
    }

    consumo = {
        "acl_vs_acr": _safe_get(ccee, "consumo", "acl_vs_acr"),
        "status": "indisponível" if _safe_get(ccee, "consumo") is None else "parcial",
    }

    perdas = {
        "rede_basica": _safe_get(ons, "perdas", "rede_basica"),
        "status": "indisponível" if _safe_get(ons, "perdas") is None else "parcial",
    }

    contratos = {
        "agregados_por_duracao": _safe_get(ccee, "contratos", "agregados"),
        "status": "indisponível" if _safe_get(ccee, "contratos") is None else "parcial",
    }

    alerts: List[str] = []
    if volume_medio is not None and volume_medio < 40:
        alerts.append("Estresse hídrico elevado (volume médio < 40%).")
    if pld_medio is not None and pld_medio > 300:
        alerts.append("PLD elevado indica pressão estrutural de preços.")
    alignment = prices["coerencia_fundamentos"].get("coerencia")
    if alignment == "desalinhado":
        alerts.append("Desalinhamento entre fundamentos físicos e PLD.")

    return {
        "timestamp": datetime.now().isoformat(),
        "hydrology": hydrology,
        "operation": operation,
        "prices": prices,
        "mcp": mcp,
        "consumo": consumo,
        "perdas": perdas,
        "contratos": contratos,
        "alerts": alerts,
    }
