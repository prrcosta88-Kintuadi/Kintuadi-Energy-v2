"""
Core analysis utilities for Kintuadi Energy.

CORE = visão sistêmica do SIN
- ONS (CSV) como fonte física primária
- CCEE como fonte econômica

VERSÃO REVISADA: Análise térmica com dupla perspectiva (sistema vs gerador)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json
import os

import pandas as pd
import numpy as np

# =====================================================================
# CONSTANTES REGULATÓRIAS - ANEEL/CCEE 2025
# =====================================================================
PLD_PISO = 57.31  # R$/MWh
PLD_TETO_ESTRUTURAL = 785.27  # R$/MWh (média semanal)
PLD_TETO_HORARIO = 1611.04  # R$/MWh (máximo horário)

# =====================================================================
# Utilities
# =====================================================================

def _safe_get(dct: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur = dct
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def _extract_sources(raw: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        "ons": raw.get("sources", {}).get("ons", {}),
        "ccee": raw.get("sources", {}).get("ccee", {}),
    }

def _find_ons_csv(ons: Dict[str, Any], dataset_prefix: str) -> Optional[str]:
    """
    Busca o dataset mais recente baseado no prefixo.
    Ex: dataset_prefix="EAR_Diario_Subsistema"
    Vai encontrar EAR_Diario_Subsistema_2026
    """

    candidates = []

    for ds in ons.get("datasets", []):
        name = ds.get("dataset", "")
        file = ds.get("file")

        # Compatibilidade com paths em formato Windows (ex.: data\ons\2026\arquivo.csv)
        if isinstance(file, str):
            file = file.replace("\\", os.sep)

        if name.startswith(dataset_prefix) and file and os.path.exists(file):
            candidates.append((name, file))

    if not candidates:
        return None

    # Ordena por nome (ano no final)
    candidates.sort(reverse=True)

    return candidates[0][1]

def _extract_ccee_records(obj: Any) -> List[Dict[str, Any]]:
    if not obj:
        return []
    if isinstance(obj, dict):
        return obj.get("records", []) or obj.get("data", []) or []
    if isinstance(obj, list):
        return obj
    return []


def _status_from_records(records: List[Dict[str, Any]]) -> str:
    return "disponível" if records else "indisponível"


# =====================================================================
# Hidrologia
# =====================================================================

def _hydrology_status(ear: Optional[float]) -> Dict[str, Any]:
    if ear is None:
        return {"classe": "dados ausentes", "descricao": "EAR não disponível."}

    if ear < 40:
        c = "crítico"
    elif ear < 55:
        c = "alerta"
    elif ear < 70:
        c = "atenção"
    elif ear < 85:
        c = "confortável"
    else:
        c = "abundante"

    return {
        "classe": c,
        "descricao": "Classificação baseada no EAR médio dos subsistemas.",
    }


def _compute_hydrology_from_csv(ons: Dict[str, Any]) -> Dict[str, Any]:
    ear_file = _find_ons_csv(ons, "EAR_Diario_Subsistema")
    ena_file = _find_ons_csv(ons, "ENA_Diario_Subsistema")

    ear_medio = ena_media = tendencia = None

    try:
        if ear_file and os.path.exists(ear_file):
            df = pd.read_csv(ear_file, sep=None, engine="python")

            col = "ear_verif_subsistema_percentual"
            if col in df.columns:
                df[col] = _normalize_br_numeric_series(df[col])
                if "ear_data" in df.columns:
                    df["ear_data"] = pd.to_datetime(df["ear_data"], errors="coerce", dayfirst=True)
                    df = df.sort_values("ear_data")
                df = df.dropna(subset=[col])

                if not df.empty:
                    ear_medio = float(df[col].mean())

                    recent = df.tail(7)[col].mean()
                    past = df.tail(30)[col].mean()
                    tendencia = float(recent - past) if past else None

        if ena_file and os.path.exists(ena_file):
            df = pd.read_csv(ena_file, sep=None, engine="python")

            # Prioridade: ENA armazenável regional (subsistema) > ENA bruta regional > legado
            ena_candidates = [
                "ena_armazenavel_regiao_mwmed",
                "ena_bruta_regiao_mwmed",
                "ena_verificada_mwmed",
            ]
            col = next((c for c in ena_candidates if c in df.columns), None)

            if col is not None:
                df[col] = _normalize_br_numeric_series(df[col])
                df = df.dropna(subset=[col])
                if not df.empty:
                    ena_media = float(df[col].mean())

    except Exception:
        pass

    return {
        "ear_medio": ear_medio,
        "ena_media": ena_media,
        "tendencia": tendencia,
        "classificacao": _hydrology_status(ear_medio),
    }


# =====================================================================
# Energia Agora (ONS) — SÉRIES HORÁRIAS
# =====================================================================

def _extract_energia_agora(ons: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processa geração e carga horária (Energia Agora).
    Retorna métricas + séries preservadas.
    """
    geracao = {}
    carga = {}

    for ds in ons.get("datasets", []):
        if ds.get("origin") != "energia_agora":
            continue

        name = ds.get("dataset", "").lower()
        file = ds.get("file")

        if not file or not os.path.exists(file):
            continue

        try:
            df = pd.read_csv(file)
            if "instante" not in df.columns:
                continue

            df["instante"] = pd.to_datetime(df["instante"])
            df = df.sort_values("instante")

            # ---------------- GERAÇÃO ----------------
            if name.startswith("geracao_") and "geracao" in df.columns:
                fonte = name.replace("geracao_", "")
                v = df["geracao"]

                geracao[fonte] = {
                    "media": float(v.mean()),
                    "max": float(v.max()),
                    "min": float(v.min()),
                    "rampa_max": float(v.diff().abs().max()),
                    "serie": df[["instante", "geracao"]].to_dict("records"),
                }

            # ---------------- CARGA ----------------
            if name.startswith("carga_") and "carga" in df.columns:
                area = name.replace("carga_", "")
                v = df["carga"]

                carga[area] = {
                    "media": float(v.mean()),
                    "max": float(v.max()),
                    "min": float(v.min()),
                    "rampa_max": float(v.diff().abs().max()),
                    "serie": df[["instante", "carga"]].to_dict("records"),
                }

        except Exception:
            continue

    status = "disponível" if (
        any(v.get("media", 0) > 0 for v in geracao.values()) or
        any(v.get("media", 0) > 0 for v in carga.values())
    ) else "indisponível"

    return {
        "generation": geracao,
        "load": carga,
        "status": status,
    }


def _normalize_power_to_mw(series: pd.Series) -> pd.Series:
    """
    Normaliza potência para MW quando os dados parecem estar em Watts.
    Heurística: medianas muito altas (>1e6) são tratadas como W.
    """
    if series.empty:
        return series

    med = series.dropna().abs().median() if not series.dropna().empty else 0
    if med > 1_000_000:
        return series / 1_000_000.0
    return series


def _extract_open_data_historical_operation(ons: Dict[str, Any]) -> Dict[str, Any]:
    """
    Consolida séries históricas de operação via Open Data:
    - Geração por usina horária (GERACAO_USINA-2)
    - Curva de carga (CURVA_CARGA)
    """
    generation: Dict[str, Dict[str, Any]] = {}
    load: Dict[str, Dict[str, Any]] = {}

    ger_frames = []
    carga_frames = []

    for ds in ons.get("datasets", []):
        name = ds.get("dataset", "")
        file = ds.get("file")
        if not file or not os.path.exists(file):
            continue

        name_lower = name.lower()

        # Geração usina horária
        if name_lower.startswith("geracao_usina_horaria"):
            try:
                df = pd.read_csv(file, sep=None, engine="python")
                required = {"din_instante", "nom_tipousina", "val_geracao"}
                if not required.issubset(df.columns):
                    continue

                df["din_instante"] = pd.to_datetime(df["din_instante"], errors="coerce", dayfirst=True)
                df["val_geracao"] = _normalize_br_numeric_series(df["val_geracao"])
                df = df.dropna(subset=["din_instante", "val_geracao"])
                if df.empty:
                    continue
                ger_frames.append(df[["din_instante", "nom_tipousina", "val_geracao"]])
            except Exception:
                continue

        # Curva de carga anual em XLSX
        if name_lower.startswith("curva_carga_"):
            try:
                df = pd.read_excel(file)
                required = {"id_subsistema", "din_instante", "val_cargaenergiahomwmed"}
                if not required.issubset(df.columns):
                    continue

                df["din_instante"] = pd.to_datetime(df["din_instante"], errors="coerce", dayfirst=True)
                df["val_cargaenergiahomwmed"] = _normalize_br_numeric_series(df["val_cargaenergiahomwmed"])
                df = df.dropna(subset=["din_instante", "id_subsistema", "val_cargaenergiahomwmed"])
                if df.empty:
                    continue
                carga_frames.append(df[["din_instante", "id_subsistema", "val_cargaenergiahomwmed"]])
            except Exception:
                continue

    # ---------- Consolidação de geração ----------
    if ger_frames:
        g = pd.concat(ger_frames, ignore_index=True)
        g["val_geracao"] = _normalize_power_to_mw(g["val_geracao"])

        total_h = g.groupby("din_instante")["val_geracao"].sum().sort_index()
        generation["sin"] = {
            "media": float(total_h.mean()),
            "max": float(total_h.max()),
            "min": float(total_h.min()),
            "rampa_max": float(total_h.diff().abs().max()) if len(total_h) > 1 else 0,
            "serie": total_h.reset_index().rename(columns={"din_instante": "instante", "val_geracao": "geracao"}).to_dict("records"),
        }

        tip_map = {
            "EOL": "sin_eolica",
            "FOTOV": "sin_solar",
            "SOLAR": "sin_solar",
            "TÉRM": "sin_termica",
            "TERM": "sin_termica",
            "HIDRO": "sin_hidraulica",
            "HIDR": "sin_hidraulica",
            "NUCL": "sin_nuclear",
        }
        for key_part, out_key in tip_map.items():
            grp = g[g["nom_tipousina"].astype(str).str.upper().str.contains(key_part, na=False)]
            if grp.empty:
                continue
            s = grp.groupby("din_instante")["val_geracao"].sum().sort_index()
            generation[out_key] = {
                "media": float(s.mean()),
                "max": float(s.max()),
                "min": float(s.min()),
                "rampa_max": float(s.diff().abs().max()) if len(s) > 1 else 0,
                "serie": s.reset_index().rename(columns={"din_instante": "instante", "val_geracao": "geracao"}).to_dict("records"),
            }

    # ---------- Consolidação de carga ----------
    if carga_frames:
        c = pd.concat(carga_frames, ignore_index=True)
        c["id_subsistema"] = c["id_subsistema"].astype(str).str.upper()
        c = c[c["id_subsistema"].isin(["N", "NE", "SE", "S"])]

        sin = c.groupby("din_instante")["val_cargaenergiahomwmed"].sum().sort_index()
        load["sin"] = {
            "media": float(sin.mean()),
            "max": float(sin.max()),
            "min": float(sin.min()),
            "rampa_max": float(sin.diff().abs().max()) if len(sin) > 1 else 0,
            "serie": sin.reset_index().rename(columns={"din_instante": "instante", "val_cargaenergiahomwmed": "carga"}).to_dict("records"),
        }

    status = "disponível" if generation or load else "indisponível"
    return {"generation": generation, "load": load, "status": status}


def _merge_operation_data(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Dict[str, Any]:
    """Mescla dados de operação, priorizando séries mais longas do secondary."""
    merged_gen = dict(primary.get("generation", {}))
    merged_load = dict(primary.get("load", {}))

    for k, v in secondary.get("generation", {}).items():
        if k not in merged_gen or len(v.get("serie", [])) > len(merged_gen[k].get("serie", [])):
            merged_gen[k] = v

    for k, v in secondary.get("load", {}).items():
        if k not in merged_load or len(v.get("serie", [])) > len(merged_load[k].get("serie", [])):
            merged_load[k] = v

    status = "disponível" if merged_gen or merged_load else "indisponível"
    return {"generation": merged_gen, "load": merged_load, "status": status}

# =====================================================================
# CURTAILMENT RENOVÁVEL (ONS)
# =====================================================================

def _compute_curtailment_from_csv(
    ons: Dict[str, Any],
    dataset_name: str,
    col_estimada: str,
    col_verificada: str,
    col_flag_invalido: Optional[str] = None,
) -> Dict[str, Any]:

    file = _find_ons_csv(ons, dataset_name)

    if not file or not os.path.exists(file):
        return {"status": "indisponível"}

    try:
        df = pd.read_csv(file, sep=None, engine="python")

        if "din_instante" not in df.columns:
            return {"status": "indisponível"}

        df["din_instante"] = pd.to_datetime(df["din_instante"], errors="coerce", dayfirst=True)
        df = df.dropna(subset=["din_instante"])

        if col_flag_invalido and col_flag_invalido in df.columns:
            df = df[df[col_flag_invalido] == False]

        df[col_estimada] = _normalize_br_numeric_series(df[col_estimada])
        df[col_verificada] = _normalize_br_numeric_series(df[col_verificada])

        df = df[
            (df[col_estimada] > 0) &
            df[col_estimada].notna() &
            df[col_verificada].notna()
        ]

        df["curtailment_abs"] = (
            df[col_estimada] - df[col_verificada]
        ).clip(lower=0)

        df["curtailment_pct"] = np.where(
            df[col_estimada] > 0,
            df["curtailment_abs"] / df[col_estimada],
            0
        )

        serie = (
            df.groupby("din_instante")["curtailment_abs"]
            .sum()
            .sort_index()
        )

        return {
            "status": "disponível",
            "curtailment_total_mwh": float(df["curtailment_abs"].sum()),
            "geracao_disponivel_total_mwh": float(df[col_estimada].sum()),
            "geracao_realizada_total_mwh": float(df[col_verificada].sum()),
            "curtailment_pct_total": float(df["curtailment_abs"].sum() / df[col_estimada].sum()) if float(df[col_estimada].sum()) > 0 else None,
            "curtailment_medio_hora": float(serie.mean()) if not serie.empty else 0,
            "curtailment_max_hora": float(serie.max()) if not serie.empty else 0,
            "serie": serie.reset_index().rename(
                columns={"din_instante": "instante", "curtailment_abs": "valor"}
            ).to_dict("records"),
        }

    except Exception:
        return {"status": "erro"}


def _compute_renewable_curtailment(ons: Dict[str, Any]) -> Dict[str, Any]:

    solar = _compute_curtailment_from_csv(
        ons,
        dataset_name="Restricao_fotovoltaica",
        col_estimada="val_geracaoestimada",
        col_verificada="val_geracaoverificada",
        col_flag_invalido="flg_dadoirradianciainvalido"
    )

    eolica = _compute_curtailment_from_csv(
        ons,
        dataset_name="Restricao_eolica",
        col_estimada="val_geracaoestimada",
        col_verificada="val_geracaoverificada",
        col_flag_invalido="flg_dadoventoinvalido"
    )

    total = 0
    disponivel_total = 0
    if solar.get("curtailment_total_mwh"):
        total += solar["curtailment_total_mwh"]
    if solar.get("geracao_disponivel_total_mwh"):
        disponivel_total += solar["geracao_disponivel_total_mwh"]
    if eolica.get("curtailment_total_mwh"):
        total += eolica["curtailment_total_mwh"]
    if eolica.get("geracao_disponivel_total_mwh"):
        disponivel_total += eolica["geracao_disponivel_total_mwh"]

    return {
        "solar": solar,
        "eolica": eolica,
        "total_mwh": total,
        "curtailment_pct_total": float(total / disponivel_total) if disponivel_total > 0 else None,
    }
# =====================================================================
# INDICE DE SATURAÇÃO RENOVÁVEL
# =====================================================================

def _compute_isr(
    geracao_solar: pd.Series,
    geracao_eolica: pd.Series,
    carga_liquida: pd.Series
) -> Optional[float]:

    if geracao_solar.empty or geracao_eolica.empty or carga_liquida.empty:
        return None

    renovavel_total = geracao_solar.mean() + geracao_eolica.mean()
    carga_media = carga_liquida.mean()

    if carga_media <= 0:
        return None

    return renovavel_total / carga_media


def _normalize_br_numeric_series(series: pd.Series) -> pd.Series:
    """Converte números em formato brasileiro/ambíguo para float."""
    if series.empty:
        return pd.Series(dtype=float)

    raw = series.astype(str).str.strip()

    has_comma = raw.str.contains(",", regex=False)
    many_dots = raw.str.count(r"\.") > 1

    parsed = raw.copy()

    # Padrão BR: 1.234,56 -> 1234.56
    parsed.loc[has_comma] = (
        parsed.loc[has_comma]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    # Valores com múltiplos pontos: 25.000.000.000 -> 25000000000
    parsed.loc[~has_comma & many_dots] = parsed.loc[~has_comma & many_dots].str.replace(".", "", regex=False)

    return pd.to_numeric(parsed, errors="coerce")


def _to_series(records: List[Dict[str, Any]], value_key: str) -> pd.Series:
    if not records:
        return pd.Series(dtype=float)

    try:
        df = pd.DataFrame(records)
        if "instante" not in df.columns or value_key not in df.columns:
            return pd.Series(dtype=float)

        df["instante"] = pd.to_datetime(df["instante"], errors="coerce", dayfirst=True)
        df[value_key] = _normalize_br_numeric_series(df[value_key])
        df = df.dropna(subset=["instante", value_key]).sort_values("instante")
        if df.empty:
            return pd.Series(dtype=float)
        return df.set_index("instante")[value_key]
    except Exception:
        return pd.Series(dtype=float)


def _safe_corr(a: pd.Series, b: pd.Series, min_points: int = 24) -> Optional[float]:
    try:
        if a.empty or b.empty:
            return None
        df = pd.DataFrame({"a": a, "b": b}).dropna()
        if len(df) < min_points:
            return None
        return float(df["a"].corr(df["b"]))
    except Exception:
        return None


def _dataset_file(ds: Dict[str, Any]) -> Optional[str]:
    file = ds.get("file")
    if isinstance(file, str):
        file = file.replace("\\", os.sep)
    return file


def _load_gfom_hourly(ons: Dict[str, Any]) -> pd.DataFrame:
    frames = []
    for ds in ons.get("datasets", []):
        name = ds.get("dataset", "")
        if not name.startswith("Despacho_GFOM_"):
            continue
        file = _dataset_file(ds)
        if not file or not os.path.exists(file):
            continue
        try:
            df = pd.read_csv(file, sep=None, engine="python")
            if "din_instante" not in df.columns:
                continue
            col_ger = "val_verifgeracao" if "val_verifgeracao" in df.columns else None
            col_gfom = "val_verifgfom" if "val_verifgfom" in df.columns else None
            if not col_ger or not col_gfom:
                continue
            df["din_instante"] = pd.to_datetime(df["din_instante"], errors="coerce", dayfirst=True)
            df[col_ger] = _normalize_br_numeric_series(df[col_ger])
            df[col_gfom] = _normalize_br_numeric_series(df[col_gfom])
            df = df.dropna(subset=["din_instante", col_ger, col_gfom])
            if df.empty:
                continue
            frames.append(df[["din_instante", col_ger, col_gfom]].rename(columns={col_ger: "ger", col_gfom: "gfom"}))
        except Exception:
            continue

    if not frames:
        return pd.DataFrame(columns=["ger", "gfom"])

    all_df = pd.concat(frames, ignore_index=True)
    return all_df.groupby("din_instante")[["ger", "gfom"]].sum().sort_index()


def _load_disponibilidade_horaria(ons: Dict[str, Any]) -> pd.Series:
    frames = []
    for ds in ons.get("datasets", []):
        name = ds.get("dataset", "")
        if not name.startswith("Disponibilidade_Usina_"):
            continue
        file = _dataset_file(ds)
        if not file or not os.path.exists(file):
            continue
        try:
            df = pd.read_csv(file, sep=None, engine="python")
            if "din_instante" not in df.columns:
                continue
            col_val = next((c for c in ["val_dispoperacional", "val_dispsincronizada", "val_potenciainstalada"] if c in df.columns), None)
            if not col_val:
                continue
            df["din_instante"] = pd.to_datetime(df["din_instante"], errors="coerce", dayfirst=True)
            df[col_val] = _normalize_power_to_mw(_normalize_br_numeric_series(df[col_val]))
            df = df.dropna(subset=["din_instante", col_val])
            if df.empty:
                continue
            frames.append(df[["din_instante", col_val]].rename(columns={col_val: "disp"}))
        except Exception:
            continue

    if not frames:
        return pd.Series(dtype=float)
    all_df = pd.concat(frames, ignore_index=True)
    return all_df.groupby("din_instante")["disp"].sum().sort_index()


def _compute_effective_availability_margin(
    ons: Dict[str, Any],
    carga_sin_series: pd.Series
) -> Dict[str, Any]:
    if carga_sin_series.empty or carga_sin_series.mean() <= 0:
        return {"status": "indisponível"}

    file = _find_ons_csv(ons, "Disponibilidade_Usina")
    if not file or not os.path.exists(file):
        return {"status": "indisponível"}

    try:
        df = pd.read_csv(file, sep=None, engine="python")

        col_ts = "din_instante" if "din_instante" in df.columns else None
        if col_ts is None:
            return {"status": "indisponível"}

        # Preferência explícita pelas colunas reais do dataset ONS informado.
        pref_cols = ["val_dispoperacional", "val_dispsincronizada", "val_potenciainstalada"]
        col_val = next((c for c in pref_cols if c in df.columns), None)
        if col_val is None:
            return {"status": "indisponível"}

        df[col_ts] = pd.to_datetime(df[col_ts], errors="coerce", dayfirst=True)
        df[col_val] = _normalize_br_numeric_series(df[col_val])
        df[col_val] = _normalize_power_to_mw(df[col_val])
        df = df.dropna(subset=[col_ts, col_val])
        if df.empty:
            return {"status": "indisponível"}

        disponibilidade_h = df.groupby(col_ts)[col_val].sum().sort_index()
        cap_disp_media = float(disponibilidade_h.mean()) if not disponibilidade_h.empty else None
        carga_media = float(carga_sin_series.mean())

        if cap_disp_media is None or carga_media <= 0:
            return {"status": "indisponível"}

        margem = (cap_disp_media - carga_media) / carga_media

        return {
            "status": "disponível",
            "capacidade_disponivel_efetiva_media": cap_disp_media,
            "carga_media": carga_media,
            "margem_estrutural_oferta": float(margem),
            "coluna_origem": col_val,
        }
    except Exception:
        return {"status": "erro"}


def _compute_termica_share_from_gfom(ons: Dict[str, Any]) -> Optional[float]:
    """Dependência térmica efetiva (%): Geração térmica / Geração total (GFOM)."""
    file = _find_ons_csv(ons, "Despacho_GFOM")
    if not file or not os.path.exists(file):
        return None

    try:
        df = pd.read_csv(file, sep=None, engine="python")
        if "din_instante" not in df.columns:
            return None

        col_ger = "val_verifgeracao" if "val_verifgeracao" in df.columns else "val_proggeracao" if "val_proggeracao" in df.columns else None
        if col_ger is None:
            return None

        df["din_instante"] = pd.to_datetime(df["din_instante"], errors="coerce", dayfirst=True)
        df[col_ger] = _normalize_br_numeric_series(df[col_ger])
        df = df.dropna(subset=["din_instante", col_ger])
        if df.empty:
            return None

        total_termica = float(df[col_ger].sum())

        # Aproximação de geração total no horizonte horário com Energia Agora (quando disponível)
        return total_termica
    except Exception:
        return None


def _compute_advanced_cross_metrics(
    ons: Dict[str, Any],
    operacao: Dict[str, Any],
    pld_series: pd.Series,
    ear_medio: Optional[float],
    ena_media: Optional[float],
    pld_medio: Optional[float],
    curtailment: Dict[str, Any],
) -> Dict[str, Any]:
    generation = operacao.get("generation", {})
    load = operacao.get("load", {})

    carga_sin = _to_series(load.get("sin", {}).get("serie", []), "carga")

    solar_key = next((k for k in generation.keys() if "solar" in k.lower()), None)
    eolica_key = next((k for k in generation.keys() if "eolica" in k.lower()), None)
    termica_key = next((k for k in generation.keys() if "termica" in k.lower()), None)

    solar = _to_series(generation.get(solar_key, {}).get("serie", []), "geracao") if solar_key else pd.Series(dtype=float)
    eolica = _to_series(generation.get(eolica_key, {}).get("serie", []), "geracao") if eolica_key else pd.Series(dtype=float)
    termica = _to_series(generation.get(termica_key, {}).get("serie", []), "geracao") if termica_key else pd.Series(dtype=float)

    total_key = "sin" if "sin" in generation else None
    geracao_total = _to_series(generation.get(total_key, {}).get("serie", []), "geracao") if total_key else pd.Series(dtype=float)

    if geracao_total.empty:
        sin_parts = [
            _to_series(v.get("serie", []), "geracao")
            for k, v in generation.items()
            if k.startswith("sin_")
        ]
        if sin_parts:
            df_sum = pd.concat(sin_parts, axis=1).fillna(0)
            geracao_total = df_sum.sum(axis=1)

    carga_liquida = pd.Series(dtype=float)
    horas_renovavel_gt_carga_liquida = None
    if not carga_sin.empty:
        renovaveis = solar.add(eolica, fill_value=0)
        carga_liquida = carga_sin.sub(renovaveis, fill_value=np.nan)
        aligned = pd.DataFrame({"renov": renovaveis, "carga_liquida": carga_liquida}).dropna()
        if not aligned.empty:
            horas_renovavel_gt_carga_liquida = int((aligned["renov"] > aligned["carga_liquida"]).sum())

    # IPR e ISR (horário)
    ipr_medio = None
    isr_medio = None
    if not carga_sin.empty:
        renov = solar.add(eolica, fill_value=0)
        df_ipr = pd.DataFrame({"renov": renov, "carga": carga_sin}).dropna()
        df_ipr = df_ipr[df_ipr["carga"] > 0]
        if not df_ipr.empty:
            ipr_medio = float((df_ipr["renov"] / df_ipr["carga"]).mean())
    if not carga_liquida.empty:
        isr_val = _compute_isr(solar, eolica, carga_liquida)
        isr_medio = float(isr_val) if isr_val is not None else None

    dependencia_termica_pct = None
    if not termica.empty and not geracao_total.empty:
        df_term = pd.DataFrame({"termica": termica, "total": geracao_total}).dropna()
        df_term = df_term[df_term["total"] > 0]
        if not df_term.empty:
            dependencia_termica_pct = float((df_term["termica"].sum() / df_term["total"].sum()) * 100)

    # Fallback para datasets GFOM quando Energia Agora não estiver disponível.
    if dependencia_termica_pct is None:
        total_termica_gfom = _compute_termica_share_from_gfom(ons)
        if total_termica_gfom is not None and not geracao_total.empty and geracao_total.sum() > 0:
            dependencia_termica_pct = float((total_termica_gfom / float(geracao_total.sum())) * 100)

    margem_oferta = _compute_effective_availability_margin(ons, carga_sin)

    # Capacidade disponível real / margem operativa real / stress operacional
    capacidade_disp_h = _load_disponibilidade_horaria(ons)
    margem_operativa_media_mensal = None
    margem_operativa_p5_mensal = None
    stress_operacional_medio = None
    stress_operacional_horario = None
    tendencia_estrutural_mensal = None
    if not capacidade_disp_h.empty and not carga_sin.empty:
        df_cap = pd.DataFrame({"cap": capacidade_disp_h, "carga": carga_sin}).dropna()
        df_cap = df_cap[df_cap["carga"] > 0]
        if not df_cap.empty:
            df_cap["margem"] = (df_cap["cap"] - df_cap["carga"]) / df_cap["carga"]
            df_cap["stress"] = df_cap["carga"] / df_cap["cap"].replace(0, np.nan)
            stress_operacional_horario = (
                df_cap["stress"].dropna().reset_index().rename(columns={"index": "instante", "stress": "valor"}).to_dict("records")
            )
            if not df_cap["stress"].dropna().empty:
                stress_operacional_medio = float(df_cap["stress"].dropna().mean())

            mensal = df_cap.resample("ME").agg({"margem": ["mean", lambda x: x.quantile(0.05)]})
            mensal.columns = ["margem_media", "margem_p5"]
            mensal = mensal.dropna(how="all")
            if not mensal.empty:
                margem_operativa_media_mensal = {
                    i.strftime("%Y-%m"): float(v) for i, v in mensal["margem_media"].dropna().items()
                }
                margem_operativa_p5_mensal = {
                    i.strftime("%Y-%m"): float(v) for i, v in mensal["margem_p5"].dropna().items()
                }
                tendencia_estrutural_mensal = "alta" if mensal["margem_media"].iloc[-1] > mensal["margem_media"].iloc[0] else "baixa"

    corr_pld_carga_liquida = _safe_corr(pld_series, carga_liquida, min_points=24)

    rolling_corr_90d = None
    if not pld_series.empty and not carga_liquida.empty:
        df_rl = pd.DataFrame({"pld": pld_series, "carga_liquida": carga_liquida}).dropna().sort_index()
        if len(df_rl) >= 24:
            rolling = df_rl["pld"].rolling(window=90 * 24, min_periods=24).corr(df_rl["carga_liquida"])
            if not rolling.dropna().empty:
                rolling_corr_90d = float(rolling.dropna().iloc[-1])

    corr_pld_ear_mensal = None
    ear_file = _find_ons_csv(ons, "EAR_Diario_Subsistema")
    if ear_file and os.path.exists(ear_file) and not pld_series.empty:
        try:
            df_ear = pd.read_csv(ear_file, sep=None, engine="python")
            col_ts = "ear_data" if "ear_data" in df_ear.columns else None
            col_ear = "ear_verif_subsistema_percentual" if "ear_verif_subsistema_percentual" in df_ear.columns else None
            if col_ts and col_ear:
                df_ear[col_ts] = pd.to_datetime(df_ear[col_ts], errors="coerce", dayfirst=True)
                df_ear[col_ear] = _normalize_br_numeric_series(df_ear[col_ear])
                s_ear = df_ear.dropna(subset=[col_ts, col_ear]).set_index(col_ts)[col_ear]
                ear_m = s_ear.resample("ME").mean()
                pld_m = pld_series.resample("ME").mean()
                corr_pld_ear_mensal = _safe_corr(pld_m, ear_m, min_points=3)
        except Exception:
            pass

    percentual_termica_h = pd.Series(dtype=float)
    if not termica.empty and not geracao_total.empty:
        df_pctt = pd.DataFrame({"termica": termica, "total": geracao_total}).dropna()
        df_pctt = df_pctt[df_pctt["total"] > 0]
        if not df_pctt.empty:
            percentual_termica_h = (df_pctt["termica"] / df_pctt["total"]) * 100

    corr_pld_pct_termica = _safe_corr(pld_series, percentual_termica_h, min_points=24)

    sigma_pld_intradiario = None
    sigma_carga_intradiario = None
    sigma_eolica_intradiario = None
    if not pld_series.empty:
        s = pld_series.groupby(pld_series.index.floor("D")).std().dropna()
        if not s.empty:
            sigma_pld_intradiario = float(s.mean())
    if not carga_sin.empty:
        s = carga_sin.groupby(carga_sin.index.floor("D")).std().dropna()
        if not s.empty:
            sigma_carga_intradiario = float(s.mean())
    if not eolica.empty:
        s = eolica.groupby(eolica.index.floor("D")).std().dropna()
        if not s.empty:
            sigma_eolica_intradiario = float(s.mean())

    amplificacao_numerica = None
    if sigma_pld_intradiario is not None:
        base = np.nanmean([v for v in [sigma_carga_intradiario, sigma_eolica_intradiario] if v is not None])
        if not np.isnan(base) and base > 0:
            amplificacao_numerica = bool(sigma_pld_intradiario > (2 * base))

    corr_curtail_ear = None
    classificacao_curtail_ear = "indisponível"
    if ear_medio is not None:
        if ear_medio > 70 and curtailment.get("total_mwh", 0) > 0:
            classificacao_curtail_ear = "estrutural"
        elif ear_medio < 50 and curtailment.get("total_mwh", 0) > 0:
            classificacao_curtail_ear = "restricao_local"
        else:
            classificacao_curtail_ear = "indeterminado"

    intercambio_classificacao = "indisponível"
    intercambio_saturado = None
    try:
        intercambio_series = pd.Series(dtype=float)
        limite_series = pd.Series(dtype=float)
        for ds in ons.get("datasets", []):
            name = ds.get("dataset", "").lower()
            file = ds.get("file")
            if "intercambio" not in name or not file or not os.path.exists(file):
                continue
            df_i = pd.read_csv(file)
            if "instante" in df_i.columns and "intercambio" in df_i.columns:
                df_i["instante"] = pd.to_datetime(df_i["instante"], errors="coerce", dayfirst=True)
                df_i["intercambio"] = _normalize_br_numeric_series(df_i["intercambio"])
                s_i = df_i.dropna(subset=["instante", "intercambio"]).set_index("instante")["intercambio"]
                intercambio_series = s_i if intercambio_series.empty else intercambio_series.add(s_i, fill_value=0)
            if "instante" in df_i.columns and "limite" in df_i.columns:
                df_i["instante"] = pd.to_datetime(df_i["instante"], errors="coerce", dayfirst=True)
                df_i["limite"] = _normalize_br_numeric_series(df_i["limite"])
                s_l = df_i.dropna(subset=["instante", "limite"]).set_index("instante")["limite"]
                limite_series = s_l if limite_series.empty else limite_series.add(s_l, fill_value=0)

        if not intercambio_series.empty and not limite_series.empty and curtailment.get("total_mwh", 0) > 0:
            df_x = pd.DataFrame({"interc": intercambio_series.abs(), "lim": limite_series.abs()}).dropna()
            if not df_x.empty:
                sat = (df_x["interc"] >= (0.95 * df_x["lim"]))
                intercambio_saturado = bool(sat.any())
                intercambio_classificacao = "transmissao" if sat.any() else "estrutural"
    except Exception:
        intercambio_classificacao = "indisponível"

    regime_abundancia = None
    if (
        dependencia_termica_pct is not None and ear_medio is not None and pld_medio is not None
    ):
        regime_abundancia = bool(dependencia_termica_pct < 15 and ear_medio > 70 and pld_medio <= PLD_PISO * 1.15)

    # GFOM x PLD
    gfom_h = _load_gfom_hourly(ons)
    gfom_pct = None
    gfom_pld_corr = None
    gfom_pld_cenario = "indisponível"
    gfom_alto_pld_baixo = None
    gfom_alto_pld_alto = None
    if not gfom_h.empty:
        total_ger = float(gfom_h["ger"].sum()) if "ger" in gfom_h else 0
        total_gfom = float(gfom_h["gfom"].sum()) if "gfom" in gfom_h else 0
        if total_ger > 0:
            gfom_pct = float((total_gfom / total_ger) * 100)

        if not pld_series.empty:
            gfom_pct_h = (gfom_h["gfom"] / gfom_h["ger"].replace(0, np.nan)) * 100
            gfom_pct_h = gfom_pct_h.replace([np.inf, -np.inf], np.nan)
            gfom_pld_corr = _safe_corr(pld_series, gfom_pct_h, min_points=24)

            df_gp = pd.DataFrame({"pld": pld_series, "gfom_pct": gfom_pct_h}).dropna()
            if not df_gp.empty:
                pld_low = df_gp["pld"].quantile(0.2)
                pld_high = df_gp["pld"].quantile(0.8)
                gfom_high = df_gp["gfom_pct"].quantile(0.8)
                gfom_low = df_gp["gfom_pct"].quantile(0.2)
                gfom_alto_pld_baixo = int(((df_gp["pld"] <= pld_low) & (df_gp["gfom_pct"] >= gfom_high)).sum())
                gfom_alto_pld_alto = int(((df_gp["pld"] >= pld_high) & (df_gp["gfom_pct"] <= gfom_low)).sum())
                if gfom_alto_pld_baixo > gfom_alto_pld_alto:
                    gfom_pld_cenario = "A: PLD baixo + GFOM alto"
                else:
                    gfom_pld_cenario = "B: PLD alto + GFOM baixo"

    # Curtailement estrutural vs elétrico (nova abordagem)
    curtailment_class_nova = "indisponível"
    if curtailment.get("total_mwh", 0) > 0:
        if intercambio_saturado:
            curtailment_class_nova = "eletrico"
        elif ipr_medio is not None and ipr_medio > 1 and ear_medio is not None and ear_medio > 60 and pld_medio is not None and pld_medio <= PLD_PISO * 1.1:
            curtailment_class_nova = "estrutural"
        else:
            curtailment_class_nova = "operacional"

    # Mudança de regime histórica (anual)
    mudanca_regime_anual = {}
    if not pld_series.empty and not capacidade_disp_h.empty and not carga_sin.empty:
        df_reg = pd.DataFrame({"pld": pld_series, "cap": capacidade_disp_h, "carga": carga_sin}).dropna()
        if not df_reg.empty:
            df_reg["stress"] = df_reg["carga"] / df_reg["cap"].replace(0, np.nan)
            g = df_reg.groupby(df_reg.index.year).agg({"pld": "mean", "stress": "mean"}).dropna()
            for yr, row in g.iterrows():
                if row["stress"] < 0.8 and row["pld"] > pld_series.quantile(0.7):
                    reg = "desalinhamento_estrutural"
                elif row["stress"] > 1:
                    reg = "estresse_operacional"
                else:
                    reg = "equilibrio"
                mudanca_regime_anual[str(int(yr))] = reg

    return {
        "margem_estrutural_oferta": margem_oferta,
        "dependencia_termica_efetiva_pct": dependencia_termica_pct,
        "regime_abundancia": regime_abundancia,
        "ena_media": ena_media,
        "horas_renovavel_gt_carga_liquida": horas_renovavel_gt_carga_liquida,
        "curtailment_percentual_total": curtailment.get("curtailment_pct_total"),
        "correlacoes": {
            "curtailment_vs_ear": corr_curtail_ear,
            "pld_vs_carga_liquida": corr_pld_carga_liquida,
            "pld_vs_carga_liquida_rolling_90d": rolling_corr_90d,
            "pld_vs_ear_mensal": corr_pld_ear_mensal,
            "pld_vs_percentual_termica": corr_pld_pct_termica,
        },
        "classificacoes": {
            "curtailment_x_ear": classificacao_curtail_ear,
            "curtailment_x_intercambio": intercambio_classificacao,
            "curtailment_estrutural_vs_eletrico": curtailment_class_nova,
        },
        "volatilidade_intradiaria": {
            "sigma_pld": sigma_pld_intradiario,
            "sigma_carga": sigma_carga_intradiario,
            "sigma_eolica": sigma_eolica_intradiario,
            "hipotese_amplificacao_numerica": amplificacao_numerica,
        },
        "aderencia_fisico_economica": {
            "pld_vs_carga_liquida": corr_pld_carga_liquida,
            "pld_vs_ear_mensal": corr_pld_ear_mensal,
            "pld_vs_percentual_termica": corr_pld_pct_termica,
            "gfom_pct": gfom_pct,
            "gfom_vs_pld_corr": gfom_pld_corr,
            "gfom_vs_pld_cenario": gfom_pld_cenario,
            "horas_cenario_A": gfom_alto_pld_baixo,
            "horas_cenario_B": gfom_alto_pld_alto,
        },
        "capacidade_operativa_real": {
            "capacidade_disponivel_real_media_mw": float(capacidade_disp_h.mean()) if not capacidade_disp_h.empty else None,
            "margem_operativa_media_mensal": margem_operativa_media_mensal,
            "margem_operativa_p5_mensal": margem_operativa_p5_mensal,
            "stress_operacional_medio": stress_operacional_medio,
            "stress_operacional_horario": stress_operacional_horario,
            "tendencia_estrutural_mensal": tendencia_estrutural_mensal,
        },
        "indices_renovaveis": {
            "ipr_medio": ipr_medio,
            "isr_medio": isr_medio,
        },
        "mudanca_regime_historica_anual": mudanca_regime_anual,
    }


def _classificar_curtailment(
    curtailment_total: float,
    ear_medio: Optional[float],
    pld_medio: Optional[float]
) -> str:

    if curtailment_total <= 0:
        return "inexistente"

    if ear_medio and ear_medio > 70 and pld_medio and pld_medio <= PLD_PISO * 1.05:
        return "excesso_estrutural"

    if ear_medio and ear_medio < 50:
        return "seguranca_operacional"

    return "restricao_rede"



# =====================================================================
# CCEE — Térmica / MCP
# =====================================================================

def compute_mcp_economico(
    pld_series: pd.Series,
    carga_series: pd.Series,
    geracao_hidraulica: pd.Series,
    cvu_medio: Optional[float]
) -> Dict[str, Any]:

    if pld_series.empty or carga_series.empty:
        return {"status": "indisponível"}

    if geracao_hidraulica.empty or geracao_hidraulica.mean() <= 0:
        return {"status": "indisponível"}


    # Calcular correlações com tratamento de dados ausentes
    corr_pld_carga = None
    corr_pld_hidro = None
    
    try:
        # Alinhar séries temporais
        df_correl = pd.DataFrame({
            'pld': pld_series,
            'carga': carga_series.reindex(pld_series.index).ffill().bfill(),
            'hidro': geracao_hidraulica.reindex(pld_series.index).ffill().bfill()
        }).dropna()
        
        if len(df_correl) > 2:  # Mínimo de pontos para correlação
            corr_pld_carga = float(df_correl['pld'].corr(df_correl['carga']))
            corr_pld_hidro = float(df_correl['pld'].corr(df_correl['hidro']))
    except Exception:
        pass

    # Determinar regime baseado no stress index
    stress_index = None

    if (
        not geracao_hidraulica.empty and
        geracao_hidraulica.mean() > 0 and
        not carga_series.empty
    ):
        stress_index = carga_series.mean() / geracao_hidraulica.mean()

    if stress_index is None:
        regime = "indeterminado"
    elif stress_index > 1.1:
        regime = "escassez estrutural"
    elif stress_index > 0.95:
        regime = "equilíbrio"
    else:
        regime = "excedente estrutural"


    # Determinar formação de preço
    if corr_pld_hidro is not None and abs(corr_pld_hidro) > 0.6:
        formacao_preco = "estrutural"
    elif corr_pld_hidro is not None and abs(corr_pld_hidro) > 0.3:
        formacao_preco = "mista"
    else:
        formacao_preco = "conjuntural"

    # Determinar posição térmica - AGORA USANDO A NOVA LÓGICA
    pld_medio = pld_series.mean() if not pld_series.empty else None
    
    # Usar a nova análise térmica para determinar posição
    posicao_termica = "indeterminada"
    if cvu_medio is not None and pld_medio is not None and pld_medio > 0:
        razao_cvu_pld = cvu_medio / pld_medio
        percentual_cvu_pld = razao_cvu_pld * 100
        
        if percentual_cvu_pld > 150:
            posicao_termica = "folga_estrutural"
        elif percentual_cvu_pld >= 100:
            posicao_termica = "risco_custo"
        elif percentual_cvu_pld >= 95:
            posicao_termica = "pressão_moderada"
        else:
            posicao_termica = "folga_operacional"

    return {
        "status": "disponível",
        "stress_index": float(stress_index),
        "correlacoes": {
            "pld_vs_carga": corr_pld_carga,
            "pld_vs_hidraulica": corr_pld_hidro,
        },
        "regime_mcp": regime,
        "interpretação": {
            "preço": formacao_preco,
            "térmica": posicao_termica,
        },
    }


# =====================================================================
# ANÁLISE TÉRMICA REVISADA (V5) - COM DUPLA PERSPECTIVA
# =====================================================================

def calcular_razao_cvu_pld(pld_medio: Optional[float], cvu_medio: Optional[float]) -> Optional[float]:
    """
    Calcula a razão CVU/PLD (indicador fundamental).
    
    Retorna:
    - < 0.8: CVU significativamente menor que PLD
    - 0.8-0.95: CVU próximo do PLD
    - 0.95-1.0: CVU muito próximo do PLD
    - 1.0-1.5: CVU maior que PLD
    - > 1.5: CVU muito maior que PLD (folga estrutural)
    """
    if pld_medio is None or cvu_medio is None or pld_medio <= 0:
        return None
    
    return cvu_medio / pld_medio


def calcular_margem_seguranca_sistema(pld_medio: Optional[float], cvu_medio: Optional[float]) -> Optional[float]:
    """
    Calcula margem de segurança do SISTEMA.
    
    Margem = ((PLD - CVU) / PLD) × 100%  se PLD > CVU
           = 0%                          se PLD <= CVU
    
    Interpretação (perspectiva do sistema):
    - > 20%: Margem adequada
    - 10-20%: Margem reduzida
    - 5-10%: Margem crítica
    - < 5%: Margem insuficiente
    - = 0%: CVU >= PLD (risco de custos)
    """
    if pld_medio is None or cvu_medio is None or pld_medio <= 0:
        return None
    
    if pld_medio > cvu_medio:
        return ((pld_medio - cvu_medio) / pld_medio) * 100
    else:
        return 0.0


def calcular_margem_vs_teto(cvu_medio: Optional[float]) -> Optional[float]:
    """
    Calcula margem de segurança em relação ao teto estrutural.
    
    Margem = ((Teto estrutural - CVU) / Teto estrutural) × 100%
    
    Interpretação:
    - > 5%: Margem adequada
    - 1-5%: Margem reduzida
    - < 1%: Margem crítica
    - <= 0%: Teto comprometido
    """
    if cvu_medio is None:
        return None
    
    return ((PLD_TETO_ESTRUTURAL - cvu_medio) / PLD_TETO_ESTRUTURAL) * 100


def calcular_viabilidade_termica(pld_medio: Optional[float], cvu_medio: Optional[float]) -> Dict[str, Any]:
    """
    Analisa viabilidade das térmicas (perspectiva do GERADOR).
    
    Retorna:
    - spread absoluto (R$/MWh)
    - viabilidade econômica (booleana)
    - classificação da perspectiva do gerador
    """
    if pld_medio is None or cvu_medio is None:
        return {
            "spread_absoluto": None,
            "viabilidade_economica": None,
            "perspectiva_gerador": "indisponível"
        }
    
    spread = pld_medio - cvu_medio
    
    if spread > 0:
        return {
            "spread_absoluto": spread,
            "viabilidade_economica": True,
            "perspectiva_gerador": "competitiva",
            "descricao": "Despacho economicamente viável para térmicas"
        }
    else:
        return {
            "spread_absoluto": spread,
            "viabilidade_economica": False,
            "perspectiva_gerador": "estrutural",
            "descricao": "Despacho por necessidade do sistema (EAR baixo ou restrição)"
        }


def calcular_dependencia_termica_efetiva(
    razao_cvu_pld: Optional[float], 
    ear_medio: Optional[float]
) -> Optional[float]:
    """
    Calcula dependência térmica EFETIVA considerando contexto hídrico.
    
    Fórmula revisada: Dependência = max(0, (razao_cvu_pld - 0.8)) × (1 - EAR_normalizado)
    
    Onde:
    - razao_cvu_pld - 0.8: penaliza apenas quando CVU > 80% do PLD
    - 1 - EAR_normalizado: inverso da condição hídrica
    
    Interpretação:
    - Baixa (< 0.1): Sistema com folga
    - Moderada (0.1-0.3): Atenção
    - Alta (0.3-0.5): Dependência significativa
    - Crítica (> 0.5): Sistema altamente dependente
    """
    if razao_cvu_pld is None or ear_medio is None:
        return None
    
    # Só considera dependência se CVU > 80% do PLD
    excesso_sobre_limiar = max(0, razao_cvu_pld - 0.8)
    
    # Normaliza EAR (0-1)
    ear_norm = max(0, min(1, ear_medio / 100))
    
    # Dependência = excesso de custo × (1 - folga hídrica)
    dependencia = excesso_sobre_limiar * (1 - ear_norm)
    
    return dependencia


def calcular_indicadores_termicos_revisados(
    pld_medio: Optional[float], 
    cvu_medio: Optional[float], 
    ear_medio: Optional[float]
) -> Dict[str, Any]:
    """
    Calcula indicadores térmicos com DUPLA PERSPECTIVA.
    
    Versão V5: Correção do conceito - CVU alto vs PLD baixo = FOLGA, não risco.
    """
    
    # 1. CÁLCULOS FUNDAMENTAIS
    razao_cvu_pld = calcular_razao_cvu_pld(pld_medio, cvu_medio)
    percentual_cvu_pld = razao_cvu_pld * 100 if razao_cvu_pld is not None else None
    
    margem_seguranca = calcular_margem_seguranca_sistema(pld_medio, cvu_medio)
    margem_vs_teto = calcular_margem_vs_teto(cvu_medio)
    dependencia_efetiva = calcular_dependencia_termica_efetiva(razao_cvu_pld, ear_medio)
    
    # Análise de viabilidade do gerador
    analise_gerador = calcular_viabilidade_termica(pld_medio, cvu_medio)
    
    # 2. ANÁLISE DO SISTEMA (PERSPECTIVA DA MODICIDADE TARIFÁRIA)
    
    # Cenário 1: CVU muito maior que PLD → FOLGA ESTRUTURAL
    if percentual_cvu_pld is not None and percentual_cvu_pld > 150:
        classificacao_sistema = "folga_estrutural"
        risco_sistêmico = "muito_baixo"
        descricao_sistema = (
            f"Sistema operando com folga ampla. "
            f"CVU (💰 {cvu_medio:.1f}) muito acima do PLD (💰 {pld_medio:.1f}) "
            f"indica térmicas fora do despacho econômico."
        )
        recomendacao_sistema = "Operação normal. Modicidade tarifária preservada."
    
    # Cenário 2: CVU entre 100-150% do PLD → RISCO DE CUSTOS
    elif percentual_cvu_pld and percentual_cvu_pld >= 100:
        classificacao_sistema = "risco_custo"
        risco_sistêmico = "alto" if ear_medio and ear_medio < 50 else "moderado"
        descricao_sistema = (
            f"Sistema pode requerer despacho térmico com prejuízo econômico. "
            f"CVU (R$ {cvu_medio:.1f}) ≥ PLD (R$ {pld_medio:.1f})."
        )
        if ear_medio and ear_medio < 50:
            recomendacao_sistema = (
                "Despacho térmico necessário por escassez hídrica. "
                "Monitorar impactos tarifários."
            )
        else:
            recomendacao_sistema = (
                "Avaliar necessidade real de despacho térmico. "
                "Considerar alternativas operacionais."
            )
    
    # Cenário 3: CVU entre 95-100% do PLD → PRESSÃO MODERADA
    elif percentual_cvu_pld and percentual_cvu_pld >= 95:
        classificacao_sistema = "pressão_moderada"
        risco_sistêmico = "moderado"
        descricao_sistema = (
            f"CVU (R$ {cvu_medio:.1f}) muito próximo do PLD (R$ {pld_medio:.1f}). "
            f"Térmicas próximas da competitividade econômica."
        )
        recomendacao_sistema = (
            "Acompanhar evolução da relação PLD-CVU. "
            "Preparar planos de contingência se necessário."
        )
    
    # Cenário 4: CVU entre 80-95% do PLD → ATENÇÃO
    elif percentual_cvu_pld and percentual_cvu_pld >= 80:
        classificacao_sistema = "atenção"
        risco_sistêmico = "baixo"
        descricao_sistema = (
            f"CVU (R$ {cvu_medio:.1f}) representa {percentual_cvu_pld:.0f}% do PLD. "
            f"Margem de segurança adequada."
        )
        recomendacao_sistema = "Monitoramento rotineiro. Sistema operando normalmente."
    
    # Cenário 5: CVU < 80% do PLD → FOLGA OPERACIONAL
    elif percentual_cvu_pld and percentual_cvu_pld < 80:
        classificacao_sistema = "folga_operacional"
        risco_sistêmico = "muito_baixo"
        descricao_sistema = (
            f"CVU (R$ {cvu_medio:.1f}) significativamente abaixo do PLD (R$ {pld_medio:.1f}). "
            f"Sistema com ampla folga em relação às térmicas."
        )
        recomendacao_sistema = "Operação confortável. Otimização de custos garantida."
    
    # Cenário 6: Dados insuficientes
    else:
        classificacao_sistema = "indisponível"
        risco_sistêmico = "indeterminado"
        descricao_sistema = "Dados insuficientes para análise térmica."
        recomendacao_sistema = "Aguardar disponibilidade de dados."
    
    # 3. CONTEXTUALIZAÇÃO HIDROLÓGICA
    if ear_medio is not None:
        if ear_medio > 70:
            contexto_hidrologico = "abundante"
            impacto_hidrologico = "mitigante"
        elif ear_medio > 55:
            contexto_hidrologico = "confortável"
            impacto_hidrologico = "neutro"
        elif ear_medio > 40:
            contexto_hidrologico = "atenção"
            impacto_hidrologico = "agravante"
        else:
            contexto_hidrologico = "crítico"
            impacto_hidrologico = "fortemente_agravante"
    else:
        contexto_hidrologico = "indisponível"
        impacto_hidrologico = "indeterminado"
    
    return {
        # =============================================
        # INDICADORES QUANTITATIVOS
        # =============================================
        "indicadores_quantitativos": {
            "razao_cvu_pld": razao_cvu_pld,
            "percentual_cvu_pld": percentual_cvu_pld,
            "spread_absoluto": analise_gerador["spread_absoluto"],
            "margem_seguranca_sistema": margem_seguranca,
            "margem_vs_teto": margem_vs_teto,
            "dependencia_termica_efetiva": dependencia_efetiva,
        },
        
        # =============================================
        # ANÁLISE DO SISTEMA (MODICIDADE TARIFÁRIA)
        # =============================================
        "analise_sistema": {
            "classificacao": classificacao_sistema,
            "risco_sistêmico": risco_sistêmico,
            "descricao": descricao_sistema,
            "recomendacao": recomendacao_sistema,
            "interpretacao": f"CVU representa {percentual_cvu_pld:.0f}% do PLD" if percentual_cvu_pld else "N/A"
        },
        
        # =============================================
        # ANÁLISE DO GERADOR TÉRMICO
        # =============================================
        "analise_gerador": analise_gerador,
        
        # =============================================
        # CONTEXTO HIDROLÓGICO
        # =============================================
        "contexto_hidrologico": {
            "ear_medio": ear_medio,
            "classificacao_hidrologica": contexto_hidrologico,
            "impacto_pressao_termica": impacto_hidrologico,
            "dependencia_efetiva": dependencia_efetiva,
            "interpretacao": (
                f"EAR {ear_medio:.1f}% ({contexto_hidrologico}) "
                f"{'agravando' if impacto_hidrologico in ['agravante', 'fortemente_agravante'] else 'mitigando'} "
                f"pressão térmica" if ear_medio is not None else "N/A"
            )
        },
        
        # =============================================
        # DADOS DE REFERÊNCIA
        # =============================================
        "dados_referencia": {
            "pld_medio": pld_medio,
            "cvu_medio": cvu_medio,
            "teto_estrutural": PLD_TETO_ESTRUTURAL,
            "limite_folga_estrutural": 150,  # % acima do qual é folga estrutural
            "limite_pressao": 95,  # % acima do qual há pressão
            "limite_risco": 100,   # % acima do qual há risco de custos
        },
        
        # =============================================
        # METADADOS DA ANÁLISE
        # =============================================
        "metadados": {
            "versao_analise": "termica_v5_dupla_perspectiva",
            "data_calculo": datetime.now().isoformat(),
            "perspectivas_incluidas": ["sistema_modicidade", "gerador_viabilidade"],
            "explicacao": (
                "Análise térmica revisada com dupla perspectiva: "
                "1) Sistema (modicidade tarifária) e "
                "2) Gerador (viabilidade econômica). "
                "CVU alto vs PLD baixo = FOLGA ESTRUTURAL, não risco."
            )
        }
    }


def _compute_cvu_from_csv(ons: Dict[str, Any]) -> Optional[float]:
    cvu_file = _find_ons_csv(ons, "CVU_Usina_Termica")

    if not cvu_file or not os.path.exists(cvu_file):
        return None

    try:
        df = pd.read_csv(cvu_file, sep=None, engine="python")
        if "val_cvu" not in df.columns:
            return None

        cvus = df["val_cvu"].dropna()
        cvus = cvus[cvus > 0]

        return float(cvus.mean()) if not cvus.empty else None

    except Exception:
        return None


# =====================================================================
# NOVAS FUNÇÕES PARA ANÁLISE DE PLD
# =====================================================================

def _calcular_volatilidade_normalizada(pld_series: pd.Series) -> Optional[float]:
    """Calcula volatilidade normalizada considerando limites regulatórios."""
    if pld_series.empty:
        return None
    
    desvio_padrao = pld_series.std()
    banda_total = PLD_TETO_ESTRUTURAL - PLD_PISO
    
    if banda_total > 0:
        return (desvio_padrao / banda_total) * 100  # Em percentual
    return None


def _calcular_posicao_relativa_pld(pld_medio: Optional[float]) -> Optional[float]:
    """Calcula posição relativa do PLD médio na banda regulatória."""
    if pld_medio is None:
        return None
    
    banda_total = PLD_TETO_ESTRUTURAL - PLD_PISO
    if banda_total > 0:
        posicao = ((pld_medio - PLD_PISO) / banda_total) * 100
        return max(0, min(100, posicao))  # Clip entre 0-100%
    return None


def _classificar_volatilidade_pld(volatilidade_norm: Optional[float]) -> str:
    """Classifica a volatilidade do PLD considerando a banda regulatória."""
    if volatilidade_norm is None:
        return "indisponível"
    
    if volatilidade_norm < 10:
        return "baixa"
    elif volatilidade_norm < 25:
        return "moderada"
    elif volatilidade_norm < 40:
        return "alta"
    else:
        return "extrema"


def _classificar_nivel_pld(pld_medio: Optional[float]) -> str:
    """Classifica o nível do PLD médio."""
    if pld_medio is None:
        return "indisponível"
    
    posicao_relativa = _calcular_posicao_relativa_pld(pld_medio)
    if posicao_relativa is None:
        return "indisponível"
    
    if posicao_relativa < 33:
        return "baixo"
    elif posicao_relativa < 66:
        return "moderado"
    else:
        return "elevado"


def _analisar_tendencia_pld(pld_series: pd.Series) -> Dict[str, Any]:
    """Analisa tendência do PLD nas últimas 24h."""
    if pld_series.empty or len(pld_series) < 24:
        return {"tendencia": None, "descricao": "Dados insuficientes"}
    
    # Últimas 24 horas
    ultimas_24h = pld_series.tail(24)
    if len(ultimas_24h) < 12:
        return {"tendencia": None, "descricao": "Dados insuficientes"}
    
    # Calcular tendência linear
    try:
        x = range(len(ultimas_24h))
        y = ultimas_24h.values
        coeficiente = np.polyfit(x, y, 1)[0] if len(y) > 1 else 0
        
        if coeficiente > 5:
            tendencia = "alta"
            descricao = "Tendência de alta forte (> R$ 5/h)"
        elif coeficiente > 1:
            tendencia = "leve alta"
            descricao = "Tendência de leve alta"
        elif coeficiente < -5:
            tendencia = "baixa"
            descricao = "Tendência de baixa forte"
        elif coeficiente < -1:
            tendencia = "leve baixa"
            descricao = "Tendência de leve baixa"
        else:
            tendencia = "estável"
            descricao = "Preços estáveis"
            
        return {
            "tendencia": tendencia,
            "coeficiente": float(coeficiente),
            "descricao": descricao
        }
    except Exception:
        return {"tendencia": None, "descricao": "Erro no cálculo"}


# =====================================================================
# Ciclo do SIN
# =====================================================================
def classify_sin_cycle(
    ear_medio: Optional[float],
    ena_media: Optional[float],
    stress_index: Optional[float],
) -> Dict[str, Any]:

    if ear_medio is None or stress_index is None:
        return {
            "cycle": "indeterminado",
            "description": "Dados insuficientes para classificar o ciclo do SIN.",
        }

    if ear_medio > 75 and stress_index < 0.9:
        cycle = "úmido"
        desc = "Abundância hídrica com folga estrutural de oferta."
    elif ear_medio < 45 and stress_index > 1.1:
        cycle = "crítico"
        desc = "Escassez hídrica com estresse estrutural do sistema."
    elif stress_index > 1.0:
        cycle = "seco"
        desc = "Oferta pressionada, dependência térmica elevada."
    else:
        cycle = "transição"
        desc = "Sistema em equilíbrio instável."

    return {
        "cycle": cycle,
        "description": desc,
    }


# =====================================================================
# Core builder
# =====================================================================

def _core_log(stage: str, message: str, **context: Any) -> None:
    ts = datetime.now().isoformat()
    ctx = " | ".join(f"{k}={v}" for k, v in context.items())
    if ctx:
        print(f"[{ts}] [build_core_analysis] [{stage}] {message} | {ctx}")
    else:
        print(f"[{ts}] [build_core_analysis] [{stage}] {message}")


def build_core_analysis(raw_data: Dict[str, Any], output_dir: str = "data") -> Dict[str, Any]:
    _core_log("START", "Entrou no build_core_analysis", output_dir=output_dir)
    sources = _extract_sources(raw_data)
    ons = sources["ons"]
    ccee = sources["ccee"]

    # ---------------- Hidrologia ----------------
    _core_log("HIDRO", "Iniciando cálculo de hidrologia")
    hydrology = _compute_hydrology_from_csv(ons)
    _core_log("HIDRO", "Hidrologia calculada", ear_medio=hydrology.get("ear_medio"), ena_media=hydrology.get("ena_media"))

    # ---------------- Operação ONS ----------------
    # Energia Agora (intradiário) + Open Data histórico (séries longas)
    _core_log("OPERACAO", "Extraindo operação Energia Agora")
    operacao_agora = _extract_energia_agora(ons)
    _core_log("OPERACAO", "Extraindo operação histórica Open Data")
    operacao_historica = _extract_open_data_historical_operation(ons)
    operacao = _merge_operation_data(operacao_agora, operacao_historica)
    _core_log("OPERACAO", "Operação consolidada")

    # ---------------- Preços (PLD horário CCEE) ----------------
    pld_medio = pld_std = pld_min = pld_max = None
    pld_por_submercado = {}
    pld_serie_7d = {}
    pld_series_full = pd.Series(dtype=float)

    # --------------------------------------------
    # 🔎 Consolidar PLD histórico multi-ano (2021–2026)
    # --------------------------------------------
    pld_records = []

    # Caso venha estrutura nova
    pld_records.extend(ccee.get("data", []))

    # Caso venha estrutura antiga (datasets por ano)
    pld_hist = ccee.get("pld_historical", {})
    datasets = pld_hist.get("datasets", [])

    for ds in datasets:
        records = (
            ds.get("timeseries")
            or ds.get("records")
            or ds.get("data")
            or []
        )
        if isinstance(records, list):
            pld_records.extend(records)

    # --------------------------------------------
    # 📊 Processamento consolidado
    # --------------------------------------------
    df_pld = pd.DataFrame(pld_records)
    _core_log("PLD", "Registros PLD consolidados", total_registros=len(pld_records), dataframe_vazio=df_pld.empty)

    ccee_structured = {"metadata": {}, "data": []}

    if not df_pld.empty:

        # 1️⃣ Normalizar colunas
        df_pld.columns = [c.lower() for c in df_pld.columns]

        if "pld" in df_pld.columns:
            df_pld.rename(columns={"pld": "pld_hora"}, inplace=True)

        # 2️⃣ Criar timestamp
        if "timestamp" not in df_pld.columns:
            if all(col in df_pld.columns for col in ["mes_referencia", "dia", "hora"]):
                df_pld["mes_referencia"] = df_pld["mes_referencia"].astype(str)
                df_pld["timestamp"] = pd.to_datetime(
                    df_pld["mes_referencia"].str[:4] + "-" +
                    df_pld["mes_referencia"].str[4:6] + "-" +
                    df_pld["dia"].astype(str) + " " +
                    df_pld["hora"].astype(str) + ":00",
                    errors="coerce"
                )

        # 3️⃣ Tipos numéricos
        df_pld["pld_hora"] = pd.to_numeric(df_pld["pld_hora"], errors="coerce")

        # 4️⃣ Limpeza
        df_pld = df_pld.dropna(subset=["timestamp", "pld_hora"])

        if not df_pld.empty:

            df_pld["timestamp"] = df_pld["timestamp"].dt.tz_localize(
                "America/Sao_Paulo",
                ambiguous="NaT",
                nonexistent="shift_forward"
            )

            df_pld = df_pld.sort_values("timestamp").reset_index(drop=True)

            # ===============================
            # 📈 Estatísticas (prices)
            # ===============================
            pld_medio = df_pld["pld_hora"].mean()
            pld_std = df_pld["pld_hora"].std()
            pld_min = df_pld["pld_hora"].min()
            pld_max = df_pld["pld_hora"].max()

            pld_series_full = df_pld.set_index("timestamp")["pld_hora"]

            # Submercados
            if "submercado" in df_pld.columns:
                for sub, grp in df_pld.groupby("submercado"):
                    pld_por_submercado[sub] = grp["pld_hora"].mean()

            # Últimos 7 dias
            last_ts = df_pld["timestamp"].max()
            cutoff = last_ts - pd.Timedelta(days=7)

            df_7d = df_pld[df_pld["timestamp"] >= cutoff]

            pld_serie_7d = {}

            if "submercado" in df_7d.columns:

                for sub, grp in df_7d.groupby("submercado"):

                    grp = grp.sort_values("timestamp")

                    pld_serie_7d[sub] = {
                        ts.isoformat(): float(v)
                        for ts, v in zip(grp["timestamp"], grp["pld_hora"])
                    }

            # ===============================
            # 📦 Estrutura CCEE consolidada
            # ===============================
            required_cols = [
                "mes_referencia",
                "submercado",
                "periodo_comercializacao",
                "dia",
                "hora",
                "pld_hora"
            ]

            for col in required_cols:
                if col not in df_pld.columns:
                    df_pld[col] = None

            records_out = df_pld[required_cols].to_dict(orient="records")

            for i, row in enumerate(records_out, start=1):
                row["_id"] = i
                row["_dataset"] = "pld_horario"

            ccee_structured = {
                "metadata": {
                    "source": "CCEE",
                    "dataset": "PLD_HORARIO",
                    "status": "success",
                    "records_processed": len(records_out),
                    "collection_time": datetime.now().isoformat()
                },
                "data": records_out
            }

    # ---------------- Curtailment Renovável ----------------
    _core_log("CURTAILMENT", "Iniciando cálculo de curtailment renovável")
    curtailment = _compute_renewable_curtailment(ons)
    _core_log("CURTAILMENT", "Curtailment calculado", total_mwh=curtailment.get("total_mwh"))

    classificacao_curtailment = _classificar_curtailment(
        curtailment_total=curtailment.get("total_mwh", 0),
        ear_medio=hydrology.get("ear_medio"),
        pld_medio=pld_medio
    )
 
    # ---------------- Séries para MCP econômico ----------------
    pld_series = pd.Series(dtype=float)
    carga_sin_series = pd.Series(dtype=float)
    geracao_hidro_sin_series = pd.Series(dtype=float)

    if pld_records and not df_pld.empty:
        pld_series = (
            df_pld
            .sort_values("timestamp")
            .set_index("timestamp")["pld_hora"]
        )

    oper = operacao.get("generation", {})
    load = operacao.get("load", {})

    # Carga SIN
    if "sin" in load:
        carga_sin_series = pd.Series(
            [x["carga"] for x in load["sin"]["serie"]],
            index=[x["instante"] for x in load["sin"]["serie"]],
        )

    # Geração hidráulica SIN
    if "sin_hidraulica" in oper:
        geracao_hidro_sin_series = pd.Series(
            [x["geracao"] for x in oper["sin_hidraulica"]["serie"]],
            index=[x["instante"] for x in oper["sin_hidraulica"]["serie"]],
        )

    # ---------------- Despacho térmico ----------------
    cvu_medio = _compute_cvu_from_csv(ons)
    
    # Calcular indicadores térmicos REVISADOS (v5)
    _core_log("TERMICA", "Calculando indicadores térmicos revisados")
    indicadores_termicos = calcular_indicadores_termicos_revisados(
        pld_medio=pld_medio,
        cvu_medio=cvu_medio,
        ear_medio=hydrology.get("ear_medio")
    )

    # ---------------- MCP Econômico ----------------
    _core_log("MCP", "Calculando MCP econômico")
    mcp_economico = compute_mcp_economico(
        pld_series=pld_series,
        carga_series=carga_sin_series,
        geracao_hidraulica=geracao_hidro_sin_series,
        cvu_medio=cvu_medio,
    )
    
    # ---------------- Ciclo do SIN ----------------
    _core_log("SIN_CYCLE", "Classificando ciclo do SIN")
    sin_cycle = classify_sin_cycle(
        ear_medio=hydrology.get("ear_medio"),
        ena_media=hydrology.get("ena_media"),
        stress_index=mcp_economico.get("stress_index"),
    )

    # ---------------- Análises de PLD (NOVAS) ----------------
    # Calcular volatilidade normalizada
    volatilidade_norm = _calcular_volatilidade_normalizada(pld_series_full)
    classificacao_vol = _classificar_volatilidade_pld(volatilidade_norm)
    
    # Calcular posição relativa
    posicao_relativa = _calcular_posicao_relativa_pld(pld_medio)
    classificacao_nivel = _classificar_nivel_pld(pld_medio)
    
    # Análise de tendência
    tendencia_pld = _analisar_tendencia_pld(pld_series_full)

    # ---------------- Métricas avançadas solicitadas ----------------
    _core_log("ADVANCED", "Calculando métricas avançadas")
    try:
        metricas_avancadas = _compute_advanced_cross_metrics(
            ons=ons,
            operacao=operacao,
            pld_series=pld_series_full,
            ear_medio=hydrology.get("ear_medio"),
            ena_media=hydrology.get("ena_media"),
            pld_medio=pld_medio,
            curtailment=curtailment,
        )
    except Exception as e:
        _core_log("ADVANCED", "Erro ao calcular métricas avançadas", erro=str(e))
        metricas_avancadas = {
            "status": "erro",
            "erro": str(e),
            "correlacoes": {},
            "classificacoes": {},
        }
    
    # ---------------- Alerts (ATUALIZADOS com nova lógica) ----------------
    alerts: List[str] = []

    # Alertas hídricos
    if hydrology["classificacao"]["classe"] in {"crítico", "alerta"}:
        alerts.append("Estresse hídrico relevante.")

    # Alertas de PLD
    if pld_medio and posicao_relativa and posicao_relativa > 66:
        alerts.append(f"PLD médio elevado ({pld_medio:.2f} R$/MWh, {posicao_relativa:.0f}% da banda).")

    # Alertas térmicos REVISADOS (usando nova lógica)
    analise_sistema = indicadores_termicos.get("analise_sistema", {})
    classificacao_sistema = analise_sistema.get("classificacao")
    risco_sistêmico = analise_sistema.get("risco_sistêmico")
    
    if risco_sistêmico == "alto":
        percentual_cvu_pld = indicadores_termicos.get("indicadores_quantitativos", {}).get("percentual_cvu_pld")
        if percentual_cvu_pld:
            alerts.append(f"Risco térmico alto: CVU em {percentual_cvu_pld:.0f}% do PLD (despacho com prejuízo possível).")
    
    # Alertas de margem vs teto
    margem_vs_teto = indicadores_termicos.get("indicadores_quantitativos", {}).get("margem_vs_teto")
    if margem_vs_teto is not None:
        if margem_vs_teto < 1:
            alerts.append(f"Margem vs teto crítica ({margem_vs_teto:.1f}%). CVU próximo do teto estrutural.")
        elif margem_vs_teto < 5:
            alerts.append(f"Margem vs teto reduzida ({margem_vs_teto:.1f}%).")
    
    # Alertas de volatilidade extrema
    if classificacao_vol == "extrema":
        alerts.append(f"Volatilidade extrema do PLD ({volatilidade_norm:.0f}% da banda).")

    # ---------------- Construir estrutura CORE ----------------
    core = {
        "timestamp": datetime.now().isoformat(),
        "hydrology": hydrology,
        "mcp_economico": mcp_economico,
        "sin_cycle": sin_cycle,
        "renewables": {
            "curtailment": curtailment,
            "classificacao": classificacao_curtailment,
        },
        "ccee": ccee_structured,
        "prices": {
            "pld_medio": pld_medio,
            "pld_min": pld_min,
            "pld_max": pld_max,
            "pld_std": pld_std,
            "pld_volatilidade_norm": volatilidade_norm,
            "pld_posicao_relativa": posicao_relativa,
            "pld_classificacao_vol": classificacao_vol,
            "pld_classificacao_nivel": classificacao_nivel,
            "pld_tendencia": tendencia_pld,
            "limites_regulatorios": {
                "piso": PLD_PISO,
                "teto_estrutural": PLD_TETO_ESTRUTURAL,
                "teto_horario": PLD_TETO_HORARIO
            },
            "por_submercado": pld_por_submercado,
            "pld_horario_7d": pld_serie_7d,
        },
        # ESTRUTURA REVISADA: Análise térmica com dupla perspectiva
        "thermal_analysis": indicadores_termicos,
        "advanced_metrics": metricas_avancadas,
        "operacao": operacao,
        "alerts": alerts,
        "metadata": {
            "analysis_version": "core-6.0",  # Atualizada para v6 com correção conceitual
            "sources": ["ONS (CSV + Energia Agora)", "CCEE"],
            "limites_aneel_2025": True,
            "analise_termica_versao": "v5_dupla_perspectiva",
            "correcao_conceitual": True,  # Sinaliza que CVU alto vs PLD baixo = FOLGA
            "perspectivas_incluidas": ["sistema_modicidade", "gerador_viabilidade"],
            "generated_at": datetime.now().isoformat(),
        },
    }

    # ---------------- Persist ----------------
    _core_log("PERSIST", "Iniciando persistência do core")

    os.makedirs(output_dir, exist_ok=True)

    removidos = []
    # REMOVER versões antigas primeiro
    for filename in os.listdir(output_dir):
        if filename.startswith("core_analysis_") and filename.endswith(".json"):
            target = os.path.join(output_dir, filename)
            os.remove(target)
            removidos.append(filename)

    _core_log("PERSIST", "Arquivos anteriores removidos", removidos=len(removidos))

    # Salvar apenas o arquivo mais recente
    path = os.path.join(output_dir, "core_analysis_latest.json")

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(core, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        _core_log("PERSIST", "Falha ao salvar core_analysis_latest.json", path=path, erro=str(e))
        raise

    _core_log("PERSIST", "core_analysis_latest.json salvo com sucesso", path=path, tamanho_bytes=os.path.getsize(path))
    return core
