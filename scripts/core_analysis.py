"""
Core analysis utilities for Kintuadi Energy.

CORE = visão sistêmica do SIN
- ONS (CSV) como fonte física primária
- CCEE como fonte econômica

VERSÃO REVISADA: Análise térmica com dupla perspectiva (sistema vs gerador)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import json
import os
import re

import pandas as pd
import numpy as np

try:
    import duckdb
except Exception:
    duckdb = None

# =====================================================================
# CONSTANTES REGULATÓRIAS - ANEEL/CCEE 2025
# =====================================================================
PLD_PISO = 57.31  # R$/MWh
PLD_TETO_ESTRUTURAL = 785.27  # R$/MWh (média semanal)
PLD_TETO_HORARIO = 1611.04  # R$/MWh (máximo horário)

# =====================================================================
# Utilities
# =====================================================================



_DUCKDB_PATH = os.path.join("data", "kintuadi.duckdb")

def _duckdb_connect() -> Optional[Any]:
    if duckdb is None:
        return None
    if not os.path.exists(_DUCKDB_PATH):
        return None
    try:
        return duckdb.connect(_DUCKDB_PATH, read_only=True)
    except Exception:
        return None

def _duckdb_table_exists(con: Any, table_name: str) -> bool:
    try:
        q = "SELECT 1 FROM information_schema.tables WHERE lower(table_name)=lower(?) LIMIT 1"
        return con.execute(q, [table_name]).fetchone() is not None
    except Exception:
        return False

def _duckdb_num_expr(col: str) -> str:
    return f"TRY_CAST(REPLACE(REPLACE(TRIM(CAST({col} AS VARCHAR)), '.', ''), ',', '.') AS DOUBLE)"

def _duckdb_date_expr(col: str) -> str:
    return (
        f"COALESCE("
        f"TRY_CAST({col} AS TIMESTAMP), "
        f"TRY_STRPTIME(CAST({col} AS VARCHAR), '%d/%m/%Y %H:%M:%S'), "
        f"TRY_STRPTIME(CAST({col} AS VARCHAR), '%d/%m/%Y %H:%M'), "
        f"TRY_STRPTIME(CAST({col} AS VARCHAR), '%d/%m/%Y')"
        f")"
    )




def _duckdb_fetchdf(sql: str, params: Optional[List[Any]] = None) -> pd.DataFrame:
    con = _duckdb_connect()
    if con is None:
        return pd.DataFrame()
    try:
        return con.execute(sql, params or []).fetchdf()
    except Exception:
        return pd.DataFrame()
    finally:
        con.close()


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
    """Modo DuckDB-only: leitura direta de CSV desabilitada no core_analysis."""
    return None


def _find_ons_csv_all(ons: Dict[str, Any], dataset_prefix: str) -> List[str]:
    """Modo DuckDB-only: leitura direta de CSV desabilitada no core_analysis."""
    return []

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
    """Hidrologia em modo DuckDB-only."""
    ear_medio = ena_media = tendencia = None
    try:
        ear_by_sub, ena_by_sub = _load_ear_ena_monthly_by_submercado(ons)
        if ear_by_sub:
            df_ear = pd.concat(ear_by_sub, axis=1)
            ear_mensal = df_ear.mean(axis=1, skipna=True).dropna().sort_index()
            if not ear_mensal.empty:
                ear_medio = float(ear_mensal.mean())
                recent = float(ear_mensal.tail(3).mean())
                past = float(ear_mensal.tail(12).mean())
                tendencia = float(recent - past) if past else None
        if ena_by_sub:
            df_ena = pd.concat(ena_by_sub, axis=1)
            ena_mensal = df_ena.mean(axis=1, skipna=True).dropna().sort_index()
            if not ena_mensal.empty:
                ena_media = float(ena_mensal.mean())
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
    """Processa geração e carga horária direto do DuckDB (sem leitura CSV em memória)."""
    geracao: Dict[str, Any] = {}
    carga: Dict[str, Any] = {}

    con = _duckdb_connect()
    if con is None:
        return {"generation": geracao, "load": carga, "status": "indisponível"}

    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]

        for t in tables:
            tl = str(t).lower()
            info = con.execute(f"PRAGMA table_info('{t}')").fetchall()
            cols = {c[1].lower(): c[1] for c in info}

            if tl.startswith("geracao_") and "instante" in cols and "geracao" in cols:
                df = con.execute(
                    f"SELECT TRY_CAST({cols['instante']} AS TIMESTAMP) AS instante, "
                    f"TRY_CAST({cols['geracao']} AS DOUBLE) AS geracao FROM {t}"
                ).fetchdf()
                df = df.dropna(subset=["instante", "geracao"]).sort_values("instante")
                if df.empty:
                    continue
                fonte = tl.replace("geracao_", "")
                v = df["geracao"]
                geracao[fonte] = {
                    "media": float(v.mean()),
                    "max": float(v.max()),
                    "min": float(v.min()),
                    "rampa_max": float(v.diff().abs().max()),
                    "serie": df[["instante", "geracao"]].to_dict("records"),
                }

            if tl.startswith("carga_") and "instante" in cols and "carga" in cols:
                df = con.execute(
                    f"SELECT TRY_CAST({cols['instante']} AS TIMESTAMP) AS instante, "
                    f"TRY_CAST({cols['carga']} AS DOUBLE) AS carga FROM {t}"
                ).fetchdf()
                df = df.dropna(subset=["instante", "carga"]).sort_values("instante")
                if df.empty:
                    continue
                area = tl.replace("carga_", "")
                v = df["carga"]
                carga[area] = {
                    "media": float(v.mean()),
                    "max": float(v.max()),
                    "min": float(v.min()),
                    "rampa_max": float(v.diff().abs().max()),
                    "serie": df[["instante", "carga"]].to_dict("records"),
                }
    except Exception:
        pass
    finally:
        con.close()

    status = "disponível" if geracao or carga else "indisponível"
    return {"generation": geracao, "load": carga, "status": status}


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
    """Consolida operação histórica via DuckDB (geracao_usina_horaria + curva_carga)."""
    generation: Dict[str, Dict[str, Any]] = {}
    load: Dict[str, Dict[str, Any]] = {}

    con = _duckdb_connect()
    if con is None:
        return {"generation": generation, "load": load, "status": "indisponível"}

    try:
        if _duckdb_table_exists(con, "geracao_usina_horaria"):
            q = f"""
                SELECT
                    {_duckdb_date_expr('din_instante')} AS din_instante,
                    UPPER(TRIM(CAST(nom_tipousina AS VARCHAR))) AS fonte,
                    {_duckdb_num_expr('val_geracao')} AS val_geracao
                FROM geracao_usina_horaria
                WHERE din_instante IS NOT NULL
            """
            g = con.execute(q).fetchdf()
            if not g.empty:
                g = g.dropna(subset=["din_instante", "fonte", "val_geracao"])
                g["val_geracao"] = _normalize_power_to_mw(pd.to_numeric(g["val_geracao"], errors="coerce"))
                g = g.dropna(subset=["val_geracao"])
                for fonte, grp in g.groupby("fonte"):
                    s = grp.groupby("din_instante")["val_geracao"].sum().sort_index()
                    generation[fonte.lower()] = {
                        "media": float(s.mean()),
                        "max": float(s.max()),
                        "min": float(s.min()),
                        "rampa_max": float(s.diff().abs().max()) if len(s) > 1 else 0.0,
                        "serie": [{"instante": i.strftime('%Y-%m-%d %H:%M:%S'), "geracao": float(v)} for i, v in s.items()],
                    }

        if _duckdb_table_exists(con, "curva_carga"):
            q = f"""
                SELECT
                    {_duckdb_date_expr('din_instante')} AS din_instante,
                    TRIM(CAST(id_subsistema AS VARCHAR)) AS id_subsistema,
                    {_duckdb_num_expr('val_cargaenergiahomwmed')} AS carga
                FROM curva_carga
                WHERE din_instante IS NOT NULL
            """
            c = con.execute(q).fetchdf()
            if not c.empty:
                c = c.dropna(subset=["din_instante", "id_subsistema", "carga"])
                c["submercado"] = c["id_subsistema"].map(_normalize_submercado_name)
                c = c.dropna(subset=["submercado"])
                for sm, grp in c.groupby("submercado"):
                    s = grp.groupby("din_instante")["carga"].sum().sort_index()
                    load[sm.lower()] = {
                        "media": float(s.mean()),
                        "max": float(s.max()),
                        "min": float(s.min()),
                        "rampa_max": float(s.diff().abs().max()) if len(s) > 1 else 0.0,
                        "serie": [{"instante": i.strftime('%Y-%m-%d %H:%M:%S'), "carga": float(v)} for i, v in s.items()],
                    }
                s_sin = c.groupby("din_instante")["carga"].sum().sort_index()
                load["sin"] = {
                    "media": float(s_sin.mean()),
                    "max": float(s_sin.max()),
                    "min": float(s_sin.min()),
                    "rampa_max": float(s_sin.diff().abs().max()) if len(s_sin) > 1 else 0.0,
                    "serie": [{"instante": i.strftime('%Y-%m-%d %H:%M:%S'), "carga": float(v)} for i, v in s_sin.items()],
                }
    except Exception:
        pass
    finally:
        con.close()

    return {"generation": generation, "load": load, "status": "disponível" if (generation or load) else "indisponível"}


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
    table_name = re.sub(r"[^a-z0-9_]", "", dataset_name.lower())

    # Prioridade: DuckDB
    con = _duckdb_connect()
    if con is not None and _duckdb_table_exists(con, table_name):
        try:
            flag_filter = ""
            if col_flag_invalido:
                flag_filter = f" AND COALESCE(TRY_CAST({col_flag_invalido} AS BOOLEAN), FALSE) = FALSE"

            q = f"""
                SELECT
                    {_duckdb_date_expr('din_instante')} AS din_instante,
                    {_duckdb_num_expr(col_estimada)} AS estimada,
                    {_duckdb_num_expr(col_verificada)} AS verificada
                FROM {table_name}
                WHERE {_duckdb_date_expr('din_instante')} IS NOT NULL
                {flag_filter}
            """
            df = con.execute(q).fetchdf()
            if df.empty:
                return {"status": "indisponível"}

            df = df.dropna(subset=["din_instante", "estimada", "verificada"])
            df = df[(df["estimada"] > 0)]
            if df.empty:
                return {"status": "indisponível"}

            df["curtailment_abs"] = (df["estimada"] - df["verificada"]).clip(lower=0)
            serie = df.groupby("din_instante")["curtailment_abs"].sum().sort_index()
            return {
                "status": "disponível",
                "curtailment_total_mwh": float(df["curtailment_abs"].sum()),
                "geracao_disponivel_total_mwh": float(df["estimada"].sum()),
                "geracao_realizada_total_mwh": float(df["verificada"].sum()),
                "curtailment_pct_total": float(df["curtailment_abs"].sum() / df["estimada"].sum()) if float(df["estimada"].sum()) > 0 else None,
                "curtailment_medio_hora": float(serie.mean()) if not serie.empty else 0,
                "curtailment_max_hora": float(serie.max()) if not serie.empty else 0,
                "serie": serie.reset_index().rename(columns={"din_instante": "instante", "curtailment_abs": "valor"}).to_dict("records"),
            }
        except Exception:
            pass
        finally:
            con.close()

    # Fallback CSV apenas se necessário
    file = _find_ons_csv(ons, dataset_name)
    if not file or not os.path.exists(file):
        return {"status": "indisponível"}

    try:
        df = pd.read_csv(file, sep=None, engine="python")
        if "din_instante" not in df.columns:
            return {"status": "indisponível"}

        df["din_instante"] = _parse_date_series(df["din_instante"])
        df = df.dropna(subset=["din_instante"])

        if col_flag_invalido and col_flag_invalido in df.columns:
            df = df[df[col_flag_invalido] == False]

        df[col_estimada] = _normalize_br_numeric_series(df[col_estimada])
        df[col_verificada] = _normalize_br_numeric_series(df[col_verificada])
        df = df[(df[col_estimada] > 0) & df[col_estimada].notna() & df[col_verificada].notna()]
        if df.empty:
            return {"status": "indisponível"}

        df["curtailment_abs"] = (df[col_estimada] - df[col_verificada]).clip(lower=0)
        serie = df.groupby("din_instante")["curtailment_abs"].sum().sort_index()

        return {
            "status": "disponível",
            "curtailment_total_mwh": float(df["curtailment_abs"].sum()),
            "geracao_disponivel_total_mwh": float(df[col_estimada].sum()),
            "geracao_realizada_total_mwh": float(df[col_verificada].sum()),
            "curtailment_pct_total": float(df["curtailment_abs"].sum() / df[col_estimada].sum()) if float(df[col_estimada].sum()) > 0 else None,
            "curtailment_medio_hora": float(serie.mean()) if not serie.empty else 0,
            "curtailment_max_hora": float(serie.max()) if not serie.empty else 0,
            "serie": serie.reset_index().rename(columns={"din_instante": "instante", "curtailment_abs": "valor"}).to_dict("records"),
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

    # Notação científica (ex.: 0E-8) já é interpretada por to_numeric e vira 0.0
    parsed = parsed.str.replace(" ", "", regex=False)

    return pd.to_numeric(parsed, errors="coerce")




def _parse_date_series(series: pd.Series) -> pd.Series:
    """Parse robusto para datas priorizando padrão brasileiro (dd/mm/aaaa)."""
    if series is None or series.empty:
        return pd.Series(dtype="datetime64[ns]")

    raw = series.astype(str).str.strip()
    out = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")

    # ISO/ano-primeiro: mantém parsing padrão para evitar inversões.
    mask_iso = raw.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")
    if mask_iso.any():
        out.loc[mask_iso] = pd.to_datetime(raw.loc[mask_iso], errors="coerce")

    # Fontes ONS/CCEE com dia primeiro (dd/mm/aaaa [HH:MM[:SS]]).
    mask_br = ~mask_iso
    if mask_br.any():
        out.loc[mask_br] = pd.to_datetime(raw.loc[mask_br], errors="coerce", dayfirst=True)

    # Fallback final para casos residuais.
    rem = out.isna()
    if rem.any():
        out.loc[rem] = pd.to_datetime(raw.loc[rem], errors="coerce")

    return out

def _to_series(records: List[Dict[str, Any]], value_key: str) -> pd.Series:
    if not records:
        return pd.Series(dtype=float)

    try:
        df = pd.DataFrame(records)
        if "instante" not in df.columns or value_key not in df.columns:
            return pd.Series(dtype=float)

        df["instante"] = _parse_date_series(df["instante"])
        df[value_key] = _normalize_br_numeric_series(df[value_key])
        df = df.dropna(subset=["instante", value_key]).sort_values("instante")
        if df.empty:
            return pd.Series(dtype=float)
        return _ensure_tz_naive_index(df.set_index("instante")[value_key])
    except Exception:
        return pd.Series(dtype=float)


def _safe_corr(a: pd.Series, b: pd.Series, min_points: int = 24) -> Optional[float]:
    try:
        a = _ensure_tz_naive_index(a)
        b = _ensure_tz_naive_index(b)
        if a.empty or b.empty:
            return None
        df = pd.DataFrame({"a": a, "b": b}).dropna()
        if len(df) < min_points:
            return None
        corr = df["a"].corr(df["b"])
        if pd.isna(corr):
            return None
        return float(corr)
    except Exception:
        return None


def _ensure_tz_naive_index(series: pd.Series) -> pd.Series:
    """Padroniza índice temporal para datetime naive e sem duplicatas."""
    s = series.copy()

    try:
        # Força índice temporal consistente mesmo com mistura tz-aware/tz-naive
        idx = pd.to_datetime(s.index, errors="coerce", utc=True)
        s = s[~idx.isna()]
        idx = idx[~idx.isna()].tz_localize(None)
        s.index = idx
    except Exception:
        try:
            if isinstance(s.index, pd.DatetimeIndex) and s.index.tz is not None:
                s.index = s.index.tz_localize(None)
        except Exception:
            pass

    try:
        if isinstance(s.index, pd.DatetimeIndex) and s.index.has_duplicates:
            if pd.api.types.is_numeric_dtype(s):
                s = s.groupby(level=0).mean().sort_index()
            else:
                s = s[~s.index.duplicated(keep="last")].sort_index()
        elif isinstance(s.index, pd.DatetimeIndex):
            s = s.sort_index()
    except Exception:
        pass

    return s


def _dataset_file(ds: Dict[str, Any]) -> Optional[str]:
    file = ds.get("file")
    if isinstance(file, str):
        file = file.replace("\\", os.sep)
    return file


def _normalize_submercado_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip().upper()
    v = v.replace("/", "").replace("-", "").replace(" ", "")

    mapping = {
        "1": "SUDESTE",
        "2": "SUL",
        "3": "NORDESTE",
        "4": "NORTE",
        "N": "NORTE",
        "NE": "NORDESTE",
        "SE": "SUDESTE",
        "SECO": "SUDESTE",
        "SUDESTECENTROOESTE": "SUDESTE",
        "SUDESTECENTRO-OESTE": "SUDESTE",
        "S": "SUL",
        "NORTE": "NORTE",
        "NORDESTE": "NORDESTE",
        "SUDESTE": "SUDESTE",
        "SUL": "SUL",
    }
    return mapping.get(v)


def _load_gfom_hourly(ons: Dict[str, Any]) -> pd.DataFrame:
    if duckdb is None:
        return pd.DataFrame(columns=["ger", "gfom"])
    con = _duckdb_connect()
    if con is None or not _duckdb_table_exists(con, "despacho_gfom"):
        if con is not None:
            con.close()
        return pd.DataFrame(columns=["ger", "gfom"])
    try:
        q = f"""
            SELECT
                {_duckdb_date_expr('din_instante')} AS din_instante,
                SUM({_duckdb_num_expr('val_verifgeracao')}) AS ger,
                SUM({_duckdb_num_expr('val_verifgfom')}) AS gfom
            FROM despacho_gfom
            GROUP BY 1
            HAVING din_instante IS NOT NULL
            ORDER BY 1
        """
        df = con.execute(q).fetchdf()
        if df.empty:
            return pd.DataFrame(columns=["ger", "gfom"])
        return df.set_index("din_instante")[["ger", "gfom"]]
    except Exception:
        return pd.DataFrame(columns=["ger", "gfom"])
    finally:
        con.close()


def _load_gfom_hourly_by_submarket(ons: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    if duckdb is None:
        return {}
    con = _duckdb_connect()
    if con is None or not _duckdb_table_exists(con, "despacho_gfom"):
        if con is not None:
            con.close()
        return {}
    try:
        q = f"""
            SELECT
                {_duckdb_date_expr('din_instante')} AS din_instante,
                UPPER(TRIM(CAST(COALESCE(nom_subsistema, id_subsistema) AS VARCHAR))) AS submercado_raw,
                SUM({_duckdb_num_expr('val_verifgeracao')}) AS ger,
                SUM({_duckdb_num_expr('val_verifgfom')}) AS gfom
            FROM despacho_gfom
            GROUP BY 1,2
            HAVING din_instante IS NOT NULL
        """
        df = con.execute(q).fetchdf()
        if df.empty:
            return {}
        df["submercado"] = df["submercado_raw"].map(_normalize_submercado_name)
        df = df.dropna(subset=["submercado"])
        out: Dict[str, pd.DataFrame] = {}
        for sm, grp in df.groupby("submercado"):
            out[str(sm)] = grp.groupby("din_instante")[["ger", "gfom"]].sum().sort_index()
        return out
    except Exception:
        return {}
    finally:
        con.close()


def _load_disponibilidade_horaria(ons: Dict[str, Any]) -> pd.Series:
    if duckdb is None:
        return pd.Series(dtype=float)
    con = _duckdb_connect()
    if con is None or not _duckdb_table_exists(con, "disponibilidade_usina"):
        if con is not None:
            con.close()
        return pd.Series(dtype=float)
    try:
        q = f"""
            SELECT
                {_duckdb_date_expr('din_instante')} AS din_instante,
                SUM(COALESCE({_duckdb_num_expr('val_dispoperacional')}, {_duckdb_num_expr('val_dispsincronizada')}, {_duckdb_num_expr('val_potenciainstalada')})) AS disp
            FROM disponibilidade_usina
            GROUP BY 1
            HAVING din_instante IS NOT NULL
            ORDER BY 1
        """
        df = con.execute(q).fetchdf()
        if df.empty:
            return pd.Series(dtype=float)
        s = pd.Series(df['disp'].values, index=pd.to_datetime(df['din_instante']))
        return _normalize_power_to_mw(s).sort_index()
    except Exception:
        return pd.Series(dtype=float)
    finally:
        con.close()


def _load_ear_ena_monthly_by_submercado(ons: Dict[str, Any]) -> Tuple[Dict[str, pd.Series], Dict[str, pd.Series]]:
    """Consolida EAR e ENA mensais por submercado apenas via DuckDB."""
    ear_by_sub: Dict[str, pd.Series] = {}
    ena_by_sub: Dict[str, pd.Series] = {}

    con = _duckdb_connect()
    if con is None:
        return ear_by_sub, ena_by_sub

    try:
        if _duckdb_table_exists(con, "ear_diario_subsistema"):
            q_ear = f"""
                SELECT
                    DATE_TRUNC('month', {_duckdb_date_expr('ear_data')}) AS mes,
                    UPPER(TRIM(CAST(COALESCE(nom_subsistema, id_subsistema) AS VARCHAR))) AS submercado_raw,
                    AVG({_duckdb_num_expr('ear_verif_subsistema_percentual')}) AS valor
                FROM ear_diario_subsistema
                GROUP BY 1,2
                HAVING mes IS NOT NULL AND valor IS NOT NULL
            """
            dfe = con.execute(q_ear).fetchdf()
            if not dfe.empty:
                dfe['submercado'] = dfe['submercado_raw'].map(_normalize_submercado_name)
                dfe = dfe.dropna(subset=['submercado'])
                for sm, grp in dfe.groupby('submercado'):
                    idx = pd.to_datetime(grp['mes']) + pd.offsets.MonthEnd(0)
                    ear_by_sub[str(sm)] = pd.Series(grp['valor'].values, index=idx).sort_index()

        if _duckdb_table_exists(con, "ena_diario_subsistema"):
            q_ena = f"""
                SELECT
                    DATE_TRUNC('month', {_duckdb_date_expr('ena_data')}) AS mes,
                    UPPER(TRIM(CAST(COALESCE(nom_subsistema, id_subsistema) AS VARCHAR))) AS submercado_raw,
                    AVG(COALESCE({_duckdb_num_expr('ena_armazenavel_regiao_mwmed')}, {_duckdb_num_expr('ena_bruta_regiao_mwmed')})) AS valor
                FROM ena_diario_subsistema
                GROUP BY 1,2
                HAVING mes IS NOT NULL AND valor IS NOT NULL
            """
            dfn = con.execute(q_ena).fetchdf()
            if not dfn.empty:
                dfn['submercado'] = dfn['submercado_raw'].map(_normalize_submercado_name)
                dfn = dfn.dropna(subset=['submercado'])
                for sm, grp in dfn.groupby('submercado'):
                    idx = pd.to_datetime(grp['mes']) + pd.offsets.MonthEnd(0)
                    ena_by_sub[str(sm)] = pd.Series(grp['valor'].values, index=idx).sort_index()
    except Exception:
        pass
    finally:
        con.close()

    return ear_by_sub, ena_by_sub


def _compute_effective_availability_margin(
    ons: Dict[str, Any],
    carga_sin_series: pd.Series
) -> Dict[str, Any]:
    if carga_sin_series.empty or carga_sin_series.mean() <= 0:
        return {"status": "indisponível"}

    disponibilidade_h = _load_disponibilidade_horaria(ons)
    if disponibilidade_h.empty:
        return {"status": "indisponível"}

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
        "coluna_origem": "duckdb:disponibilidade_usina",
    }


def _compute_termica_share_from_gfom(ons: Dict[str, Any]) -> Optional[float]:
    """Dependência térmica efetiva via DuckDB (soma de val_verifgeracao no despacho GFOM)."""
    gf = _load_gfom_hourly(ons)
    if gf.empty or "ger" not in gf.columns:
        return None
    try:
        return float(pd.to_numeric(gf["ger"], errors="coerce").dropna().sum())
    except Exception:
        return None


def _compute_advanced_cross_metrics(
    ons: Dict[str, Any],
    operacao: Dict[str, Any],
    pld_series: pd.Series,
    pld_series_by_submercado: Optional[Dict[str, pd.Series]],
    ear_medio: Optional[float],
    ena_media: Optional[float],
    pld_medio: Optional[float],
    curtailment: Dict[str, Any],
) -> Dict[str, Any]:
    pld_series = _ensure_tz_naive_index(pld_series)
    pld_series_by_submercado = {
        _normalize_submercado_name(k) or str(k): _ensure_tz_naive_index(v)
        for k, v in (pld_series_by_submercado or {}).items()
        if isinstance(v, pd.Series)
    }

    generation = operacao.get("generation", {})
    load = operacao.get("load", {})
    step_errors: Dict[str, str] = {}

    carga_sin = _ensure_tz_naive_index(_to_series(load.get("sin", {}).get("serie", []), "carga"))

    solar_key = next((k for k in generation.keys() if "solar" in k.lower()), None)
    eolica_key = next((k for k in generation.keys() if "eolica" in k.lower()), None)
    termica_key = next((k for k in generation.keys() if "termica" in k.lower()), None)

    solar = _ensure_tz_naive_index(_to_series(generation.get(solar_key, {}).get("serie", []), "geracao")) if solar_key else pd.Series(dtype=float)
    eolica = _ensure_tz_naive_index(_to_series(generation.get(eolica_key, {}).get("serie", []), "geracao")) if eolica_key else pd.Series(dtype=float)
    termica = _ensure_tz_naive_index(_to_series(generation.get(termica_key, {}).get("serie", []), "geracao")) if termica_key else pd.Series(dtype=float)

    total_key = "sin" if "sin" in generation else None
    geracao_total = _ensure_tz_naive_index(_to_series(generation.get(total_key, {}).get("serie", []), "geracao")) if total_key else pd.Series(dtype=float)

    if geracao_total.empty:
        sin_parts = [
            _to_series(v.get("serie", []), "geracao")
            for k, v in generation.items()
            if k.startswith("sin_")
        ]
        if sin_parts:
            df_sum = pd.concat(sin_parts, axis=1).fillna(0)
            geracao_total = _ensure_tz_naive_index(df_sum.sum(axis=1))

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

    corr_pld_carga_liquida = None
    rolling_corr_90d = None
    try:
        pld_series = _ensure_tz_naive_index(pld_series)
        carga_liquida = _ensure_tz_naive_index(carga_liquida)
        corr_pld_carga_liquida = _safe_corr(pld_series, carga_liquida, min_points=24)
        if not pld_series.empty and not carga_liquida.empty:
            df_rl = pd.DataFrame({"pld": pld_series, "carga_liquida": carga_liquida}).dropna().sort_index()
            if len(df_rl) >= 24:
                rolling = df_rl["pld"].rolling(window=90 * 24, min_periods=24).corr(df_rl["carga_liquida"])
                if not rolling.dropna().empty:
                    rolling_corr_90d = float(rolling.dropna().iloc[-1])
    except Exception as e:
        step_errors["pld_vs_carga_liquida"] = str(e)

    corr_pld_ear_mensal = None
    pld_vs_ear_mensal_por_submercado: Dict[str, Optional[float]] = {}
    pld_vs_ena_mensal_por_submercado: Dict[str, Optional[float]] = {}

    ear_media_mensal = None
    ena_media_mensal = None
    ear_media_diaria = None
    ena_media_diaria = None
    matriz_cenario_mensal: List[Dict[str, Any]] = []
    matriz_cenario_diaria: List[Dict[str, Any]] = []
    try:
        ear_by_sub, ena_by_sub = _load_ear_ena_monthly_by_submercado(ons)
        for sm, pld_sm in pld_series_by_submercado.items():
            pld_m_sm = _ensure_tz_naive_index(pld_sm).resample("ME").mean()
            ear_sm = ear_by_sub.get(sm)
            ena_sm = ena_by_sub.get(sm)
            pld_vs_ear_mensal_por_submercado[sm] = _safe_corr(pld_m_sm, ear_sm, min_points=3)
            pld_vs_ena_mensal_por_submercado[sm] = _safe_corr(pld_m_sm, ena_sm, min_points=3)

        if ear_by_sub:
            ear_media_mensal = {
                i.strftime("%Y-%m"): float(v)
                for i, v in pd.concat(ear_by_sub, axis=1).mean(axis=1, skipna=True).dropna().sort_index().items()
            }
        if ena_by_sub:
            ena_media_mensal = {
                i.strftime("%Y-%m"): float(v)
                for i, v in pd.concat(ena_by_sub, axis=1).mean(axis=1, skipna=True).dropna().sort_index().items()
            }

        if ear_media_mensal and not pld_series.empty:
            pld_m = _ensure_tz_naive_index(pld_series).resample("ME").mean()
            ear_m = pd.Series({pd.to_datetime(k) + pd.offsets.MonthEnd(0): v for k, v in ear_media_mensal.items()})
            corr_pld_ear_mensal = _safe_corr(pld_m, ear_m, min_points=3)

        # Séries diárias (prioridade DuckDB; fallback CSV somente se necessário)
        con = _duckdb_connect()
        if con is not None:
            try:
                if _duckdb_table_exists(con, "ear_diario_subsistema"):
                    q_ear_d = f"""
                        SELECT DATE_TRUNC('day', {_duckdb_date_expr('ear_data')}) AS dia,
                               AVG({_duckdb_num_expr('ear_verif_subsistema_percentual')}) AS ear_val
                        FROM ear_diario_subsistema
                        GROUP BY 1
                        HAVING dia IS NOT NULL AND ear_val IS NOT NULL
                        ORDER BY 1
                    """
                    dfe = con.execute(q_ear_d).fetchdf()
                    if not dfe.empty:
                        ear_media_diaria = {
                            pd.Timestamp(i).strftime("%Y-%m-%d"): float(v)
                            for i, v in zip(dfe["dia"], dfe["ear_val"])
                        }

                if _duckdb_table_exists(con, "ena_diario_subsistema"):
                    q_ena_d = f"""
                        SELECT DATE_TRUNC('day', {_duckdb_date_expr('ena_data')}) AS dia,
                               AVG(COALESCE({_duckdb_num_expr('ena_armazenavel_regiao_mwmed')}, {_duckdb_num_expr('ena_bruta_regiao_mwmed')})) AS ena_val
                        FROM ena_diario_subsistema
                        GROUP BY 1
                        HAVING dia IS NOT NULL AND ena_val IS NOT NULL
                        ORDER BY 1
                    """
                    dfn = con.execute(q_ena_d).fetchdf()
                    if not dfn.empty:
                        ena_media_diaria = {
                            pd.Timestamp(i).strftime("%Y-%m-%d"): float(v)
                            for i, v in zip(dfn["dia"], dfn["ena_val"])
                        }
            except Exception:
                pass
            finally:
                con.close()

        pld_m_global = _ensure_tz_naive_index(pld_series).resample("ME").mean()
        carga_liquida_m = _ensure_tz_naive_index(carga_liquida).resample("ME").mean() if not carga_liquida.empty else pd.Series(dtype=float)
        termica_pct_m = (pd.DataFrame({"termica": termica, "total": geracao_total}).dropna().query("total > 0").eval("(termica/total)*100").resample("ME").mean() if (not termica.empty and not geracao_total.empty) else pd.Series(dtype=float))

        idx = pld_m_global.index
        for extra in [
            (pd.to_datetime(list((ear_media_mensal or {}).keys()), format="%Y-%m", errors="coerce") + pd.offsets.MonthEnd(0)) if ear_media_mensal else pd.DatetimeIndex([]),
            (pd.to_datetime(list((ena_media_mensal or {}).keys()), format="%Y-%m", errors="coerce") + pd.offsets.MonthEnd(0)) if ena_media_mensal else pd.DatetimeIndex([]),
            carga_liquida_m.index if not carga_liquida_m.empty else pd.DatetimeIndex([]),
            termica_pct_m.index if not termica_pct_m.empty else pd.DatetimeIndex([]),
        ]:
            idx = idx.union(extra)

        seen_months = set()
        for month in sorted([i for i in idx if not pd.isna(i)]):
            month_label = month.strftime("%Y-%m")
            if month_label in seen_months:
                continue
            seen_months.add(month_label)
            pld_v = float(pld_m_global.get(month)) if month in pld_m_global.index and pd.notna(pld_m_global.get(month)) else None
            ear_v = ear_media_mensal.get(month.strftime("%Y-%m")) if ear_media_mensal else None
            ena_v = ena_media_mensal.get(month.strftime("%Y-%m")) if ena_media_mensal else None
            carga_v = float(carga_liquida_m.get(month)) if month in carga_liquida_m.index and pd.notna(carga_liquida_m.get(month)) else None
            term_v = float(termica_pct_m.get(month)) if month in termica_pct_m.index and pd.notna(termica_pct_m.get(month)) else None

            if pld_v is None or ear_v is None:
                cenario = "dados_insuficientes"
            elif pld_v >= PLD_TETO_ESTRUTURAL * 0.8 and ear_v < 50:
                cenario = "estresse_hidrico"
            elif pld_v <= PLD_PISO * 1.2 and ear_v > 65:
                cenario = "abundancia_hidrica"
            elif term_v is not None and term_v > 25 and pld_medio is not None and pld_v > pld_medio:
                cenario = "pressao_termica"
            else:
                cenario = "equilibrio_operacional"

            matriz_cenario_mensal.append({
                "mes": month_label,
                "pld_medio": pld_v,
                "ear_medio": ear_v,
                "ena_media": ena_v,
                "carga_liquida_media": carga_v,
                "percentual_termica_medio": term_v,
                "cenario": cenario,
            })
    except Exception as e:
        step_errors["ear_ena_vs_pld_por_submercado"] = str(e)

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

        con = _duckdb_connect()
        if con is not None:
            try:
                tables = [r[0] for r in con.execute("SHOW TABLES").fetchall() if "intercambio" in str(r[0]).lower()]
                for t in tables:
                    info = con.execute(f"PRAGMA table_info('{t}')").fetchall()
                    cols = {c[1].lower(): c[1] for c in info}
                    ts_col = cols.get("instante") or cols.get("din_instante")
                    interc_col = cols.get("intercambio")
                    lim_col = cols.get("limite")
                    if not ts_col or (not interc_col and not lim_col):
                        continue
                    if interc_col:
                        qi = f"SELECT {_duckdb_date_expr(ts_col)} AS ts, {_duckdb_num_expr(interc_col)} AS v FROM {t}"
                        dfi = con.execute(qi).fetchdf().dropna(subset=["ts", "v"])
                        if not dfi.empty:
                            s_i = dfi.groupby("ts")["v"].sum().sort_index()
                            intercambio_series = s_i if intercambio_series.empty else intercambio_series.add(s_i, fill_value=0)
                    if lim_col:
                        ql = f"SELECT {_duckdb_date_expr(ts_col)} AS ts, {_duckdb_num_expr(lim_col)} AS v FROM {t}"
                        dfl = con.execute(ql).fetchdf().dropna(subset=["ts", "v"])
                        if not dfl.empty:
                            s_l = dfl.groupby("ts")["v"].sum().sort_index()
                            limite_series = s_l if limite_series.empty else limite_series.add(s_l, fill_value=0)
            except Exception:
                pass
            finally:
                con.close()

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
        try:
            gfom_h = gfom_h.copy()
            gfom_h.index = pd.to_datetime(gfom_h.index, errors="coerce", utc=True).tz_localize(None)
            gfom_h = gfom_h[~gfom_h.index.isna()]
            gfom_h = gfom_h.groupby(level=0).sum().sort_index()

            total_ger = float(gfom_h["ger"].sum()) if "ger" in gfom_h else 0
            total_gfom = float(gfom_h["gfom"].sum()) if "gfom" in gfom_h else 0
            if total_ger > 0:
                gfom_pct = float((total_gfom / total_ger) * 100)

            if not pld_series.empty:
                gfom_pct_h = (gfom_h["gfom"] / gfom_h["ger"].replace(0, np.nan)) * 100
                gfom_pct_h = _ensure_tz_naive_index(gfom_pct_h.replace([np.inf, -np.inf], np.nan))
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
        except Exception as e:
            step_errors["gfom_vs_pld"] = str(e)

    # GFOM x PLD por submercado (PLD horário pode diferir por submercado)
    gfom_vs_pld_por_submercado: Dict[str, Any] = {}
    gfom_sub = _load_gfom_hourly_by_submarket(ons)
    sm_suffix = {
        "NORTE": "n",
        "NORDESTE": "ne",
        "SUL": "s",
        "SUDESTE": "se",
    }
    for sm, gfdf in gfom_sub.items():
        try:
            pld_sm = pld_series_by_submercado.get(sm)
            if pld_sm is None or pld_sm.empty:
                continue
            gfdf = gfdf.copy()
            gfdf.index = pd.to_datetime(gfdf.index, errors="coerce", utc=True).tz_localize(None)
            gfdf = gfdf[~gfdf.index.isna()].groupby(level=0).sum().sort_index()
            gfom_pct_sm = (gfdf["gfom"] / gfdf["ger"].replace(0, np.nan) * 100).replace([np.inf, -np.inf], np.nan)
            gfom_pct_sm = _ensure_tz_naive_index(gfom_pct_sm)
            key_pct = f"gfom_{sm_suffix.get(sm, sm.lower())}_pct"
            gfom_vs_pld_por_submercado[sm] = {
                key_pct: float((gfdf["gfom"].sum() / gfdf["ger"].sum()) * 100) if gfdf["ger"].sum() > 0 else None,
                "corr": _safe_corr(pld_sm, gfom_pct_sm, min_points=24),
            }
        except Exception as e:
            gfom_vs_pld_por_submercado[sm] = {"erro": str(e)}

    # Curtailement estrutural vs elétrico (nova abordagem)
    curtailment_class_nova = "indisponível"
    if curtailment.get("total_mwh", 0) > 0:
        if intercambio_saturado:
            curtailment_class_nova = "eletrico"
        elif ipr_medio is not None and ipr_medio > 1 and ear_medio is not None and ear_medio > 60 and pld_medio is not None and pld_medio <= PLD_PISO * 1.1:
            curtailment_class_nova = "estrutural"
        else:
            curtailment_class_nova = "operacional"

    # Matriz diária para uso no dashboard (cards c1..c7 por período)
    try:
        pld_h = _ensure_tz_naive_index(pld_series)
        pld_d = pld_h.groupby(pld_h.index.floor("D")).mean() if not pld_h.empty else pd.Series(dtype=float)

        gfom_pct_d = pd.Series(dtype=float)
        if not gfom_h.empty:
            gtmp = gfom_h.copy()
            gtmp.index = pd.to_datetime(gtmp.index, errors="coerce", utc=True).tz_localize(None)
            gtmp = gtmp[~gtmp.index.isna()].groupby(level=0).sum().sort_index()
            if not gtmp.empty:
                gtmp_d = gtmp.groupby(gtmp.index.floor("D")).sum()
                gfom_pct_d = (gtmp_d["gfom"] / gtmp_d["ger"].replace(0, np.nan) * 100).replace([np.inf, -np.inf], np.nan)

        gfom_corr_d = pd.Series(dtype=float)
        if not pld_h.empty and not gfom_h.empty:
            gtmp = gfom_h.copy()
            gtmp.index = pd.to_datetime(gtmp.index, errors="coerce", utc=True).tz_localize(None)
            gtmp = gtmp[~gtmp.index.isna()].groupby(level=0).sum().sort_index()
            gfom_pct_h_local = (gtmp["gfom"] / gtmp["ger"].replace(0, np.nan) * 100).replace([np.inf, -np.inf], np.nan)
            df_gp_h = pd.DataFrame({"pld": pld_h, "gfom_pct": gfom_pct_h_local}).dropna()
            if not df_gp_h.empty:
                vals = {}
                for d, grp in df_gp_h.groupby(df_gp_h.index.floor("D")):
                    vals[d] = _safe_corr(grp["pld"], grp["gfom_pct"], min_points=12)
                gfom_corr_d = pd.Series(vals)

        stress_d = pd.Series(dtype=float)
        if not capacidade_disp_h.empty and not carga_sin.empty:
            df_capd = pd.DataFrame({"cap": capacidade_disp_h, "carga": carga_sin}).dropna()
            df_capd = df_capd[df_capd["cap"] > 0]
            if not df_capd.empty:
                stress_d = (df_capd["carga"] / df_capd["cap"]).groupby(df_capd.index.floor("D")).mean()

        ipr_d = pd.Series(dtype=float)
        if not carga_sin.empty:
            renov_dfr = pd.DataFrame({"renov": solar.add(eolica, fill_value=0), "carga": carga_sin}).dropna()
            renov_dfr = renov_dfr[renov_dfr["carga"] > 0]
            if not renov_dfr.empty:
                ipr_d = (renov_dfr["renov"] / renov_dfr["carga"]).groupby(renov_dfr.index.floor("D")).mean()

        isr_d = pd.Series(dtype=float)
        if not carga_liquida.empty:
            df_isrd = pd.DataFrame({"renov": solar.add(eolica, fill_value=0), "carga_liquida": carga_liquida}).dropna()
            df_isrd = df_isrd[df_isrd["carga_liquida"] > 0]
            if not df_isrd.empty:
                isr_d = (df_isrd["renov"] / df_isrd["carga_liquida"]).groupby(df_isrd.index.floor("D")).mean()

        term_dep_d = pd.Series(dtype=float)
        if not termica.empty and not geracao_total.empty:
            dft = pd.DataFrame({"term": termica, "tot": geracao_total}).dropna()
            dft = dft[dft["tot"] > 0]
            if not dft.empty:
                term_dep_d = ((dft["term"] / dft["tot"]) * 100).groupby(dft.index.floor("D")).mean()

        curtailment_d = pd.Series(dtype=float)
        try:
            sol_rec = ((curtailment.get("solar") or {}).get("serie") or [])
            eol_rec = ((curtailment.get("eolica") or {}).get("serie") or [])
            s_sol = _to_series(sol_rec, "valor") if sol_rec else pd.Series(dtype=float)
            s_eol = _to_series(eol_rec, "valor") if eol_rec else pd.Series(dtype=float)
            if not s_sol.empty or not s_eol.empty:
                curtailment_d = s_sol.add(s_eol, fill_value=0).groupby(lambda x: pd.Timestamp(x).floor("D")).sum()
        except Exception:
            curtailment_d = pd.Series(dtype=float)

        ear_daily = pd.Series({pd.to_datetime(k): v for k, v in (ear_media_diaria or {}).items()}) if ear_media_diaria else pd.Series(dtype=float)

        idx_days = pd.DatetimeIndex([])
        for ser in [pld_d, gfom_pct_d, gfom_corr_d, stress_d, ipr_d, isr_d, term_dep_d, curtailment_d, ear_daily]:
            if not ser.empty:
                idx_days = idx_days.union(pd.DatetimeIndex(ser.index))

        for d in sorted(idx_days):
            pldv = pld_d.get(d)
            gpv = gfom_pct_d.get(d)
            gcv = gfom_corr_d.get(d)
            stv = stress_d.get(d)
            ipv = ipr_d.get(d)
            isv = isr_d.get(d)
            tdv = term_dep_d.get(d)
            ctv = curtailment_d.get(d)
            earv = ear_daily.get(d)

            if ctv is None or pd.isna(ctv) or ctv <= 0:
                curt_state = "inexistente"
            elif intercambio_saturado:
                curt_state = "eletrico"
            elif (ipv is not None and not pd.isna(ipv) and ipv > 1) and (earv is not None and not pd.isna(earv) and earv > 60) and (pldv is not None and not pd.isna(pldv) and pldv <= PLD_PISO * 1.1):
                curt_state = "estrutural"
            else:
                curt_state = "operacional"

            abund = None
            if tdv is not None and not pd.isna(tdv) and earv is not None and not pd.isna(earv) and pldv is not None and not pd.isna(pldv):
                abund = bool(tdv < 15 and earv > 70 and pldv <= PLD_PISO * 1.15)

            matriz_cenario_diaria.append({
                "dia": pd.Timestamp(d).strftime("%Y-%m-%d"),
                "gfom_pct": None if pd.isna(gpv) else float(gpv),
                "gfom_vs_pld_corr": None if pd.isna(gcv) else float(gcv),
                "curtailment_estado": curt_state,
                "stress_operacional_medio": None if pd.isna(stv) else float(stv),
                "ipr_medio": None if pd.isna(ipv) else float(ipv),
                "isr_medio": None if pd.isna(isv) else float(isv),
                "regime_abundancia": abund,
                "pld_medio_dia": None if pd.isna(pldv) else float(pldv),
                "ear_medio_dia": None if pd.isna(earv) else float(earv),
            })
    except Exception as e:
        step_errors["matriz_cenario_diaria"] = str(e)

    # Mudança de regime histórica (trimestral)
    mudanca_regime_trimestral = {}
    try:
        capacidade_disp_h = _ensure_tz_naive_index(capacidade_disp_h)
        carga_sin = _ensure_tz_naive_index(carga_sin)
        if not pld_series.empty and not capacidade_disp_h.empty and not carga_sin.empty:
            df_reg = pd.DataFrame({"pld": pld_series, "cap": capacidade_disp_h, "carga": carga_sin}).dropna()
            if not df_reg.empty:
                df_reg["stress"] = df_reg["carga"] / df_reg["cap"].replace(0, np.nan)
                g = df_reg.groupby(df_reg.index.to_period("Q")).agg({"pld": "mean", "stress": "mean"}).dropna()
                for q, row in g.iterrows():
                    if row["stress"] < 0.8 and row["pld"] > pld_series.quantile(0.7):
                        reg = "desalinhamento_estrutural"
                    elif row["stress"] > 1:
                        reg = "estresse_operacional"
                    else:
                        reg = "equilibrio"
                    mudanca_regime_trimestral[str(q)] = reg
    except Exception as e:
        step_errors["mudanca_regime_historica_trimestral"] = str(e)

    return {
        "status": "parcial" if step_errors else "disponível",
        "diagnostico_etapas": step_errors,
        "margem_estrutural_oferta": margem_oferta,
        "dependencia_termica_efetiva_pct": dependencia_termica_pct,
        "regime_abundancia": regime_abundancia,
        "ena_media": ena_media,
        "ear_media_mensal": ear_media_mensal,
        "ena_media_mensal": ena_media_mensal,
        "ear_media_diaria": ear_media_diaria,
        "ena_media_diaria": ena_media_diaria,
        "matriz_cenario_mensal": matriz_cenario_mensal,
        "matriz_cenario_diaria": matriz_cenario_diaria,
        "horas_renovavel_gt_carga_liquida": horas_renovavel_gt_carga_liquida,
        "curtailment_percentual_total": curtailment.get("curtailment_pct_total"),
        "correlacoes": {
            "curtailment_vs_ear": corr_curtail_ear,
            "pld_vs_carga_liquida": corr_pld_carga_liquida,
            "pld_vs_carga_liquida_rolling_90d": rolling_corr_90d,
            "pld_vs_ear_mensal": corr_pld_ear_mensal,
            "pld_vs_percentual_termica": corr_pld_pct_termica,
            "pld_vs_ear_mensal_por_submercado": pld_vs_ear_mensal_por_submercado,
            "pld_vs_ena_mensal_por_submercado": pld_vs_ena_mensal_por_submercado,
        },
        "classificacoes": {
            "curtailment_x_ear": classificacao_curtail_ear,
            "curtailment_x_intercambio": intercambio_classificacao,
            "curtailment_estrutural_vs_eletrico": curtailment_class_nova,
        },
        "metodologia": {
            "gfom_vs_pld": "GFOM% horário = (val_verifgfom / val_verifgeracao)*100; correlação de Pearson com PLD horário após alinhamento temporal.",
            "margem_operativa_real": "margem = (capacidade_disponivel_real - carga)/carga; margem média mensal = média da margem horária no mês; margem p5 = percentil 5% da margem horária no mês.",
            "curtailment": "elétrico quando intercâmbio saturado (>=95% do limite) com curtailment>0; estrutural quando IPR>1, EAR>60 e PLD baixo; caso contrário operacional.",
            "ipr_isr": "IPR = média((solar+eólica)/carga); ISR = média((solar+eólica)/carga_liquida).",
            "regime_abundancia": "True quando dependência térmica <15%, EAR>70 e PLD <= 1.15*piso regulatório.",
            "mudanca_regime_trimestral": "desalinhamento_estrutural: stress<0.8 e PLD no quantil alto; estresse_operacional: stress>1; senão equilíbrio.",
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
            "pld_vs_ear_mensal_por_submercado": pld_vs_ear_mensal_por_submercado,
            "pld_vs_ena_mensal_por_submercado": pld_vs_ena_mensal_por_submercado,
            "gfom_pct": gfom_pct,
            "gfom_vs_pld_corr": gfom_pld_corr,
            "gfom_vs_pld_cenario": gfom_pld_cenario,
            "horas_cenario_A": gfom_alto_pld_baixo,
            "horas_cenario_B": gfom_alto_pld_alto,
            "gfom_vs_pld_por_submercado": gfom_vs_pld_por_submercado,
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
        "mudanca_regime_historica_trimestral": mudanca_regime_trimestral,
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

    pld_series = _ensure_tz_naive_index(pld_series)
    carga_series = _ensure_tz_naive_index(carga_series)
    geracao_hidraulica = _ensure_tz_naive_index(geracao_hidraulica)

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


def _load_cvu_weekly_series(ons: Dict[str, Any]) -> pd.Series:
    """Retorna série semanal média de CVU por dat_fimsemana (consolidando múltiplos arquivos)."""
    con = _duckdb_connect()
    if con is not None:
        try:
            if _duckdb_table_exists(con, "cvu_usina_termica"):
                q = f"""
                    SELECT
                        {_duckdb_date_expr('dat_fimsemana')} AS dat_fimsemana,
                        AVG({_duckdb_num_expr('val_cvu')}) AS val_cvu
                    FROM cvu_usina_termica
                    GROUP BY 1
                    HAVING dat_fimsemana IS NOT NULL AND val_cvu > 0
                    ORDER BY 1
                """
                df = con.execute(q).fetchdf()
                if not df.empty:
                    s = pd.Series(df['val_cvu'].values, index=pd.to_datetime(df['dat_fimsemana']))
                    return s.sort_index().astype(float)
        except Exception:
            pass
        finally:
            con.close()

    files = _find_ons_csv_all(ons, "CVU_Usina_Termica")
    if not files:
        return pd.Series(dtype=float)

    frames: List[pd.DataFrame] = []
    for cvu_file in files:
        try:
            df = pd.read_csv(cvu_file, sep=None, engine="python")
            needed = {"dat_iniciosemana", "dat_fimsemana", "val_cvu"}
            if not needed.issubset(df.columns):
                continue
            df = df[["dat_iniciosemana", "dat_fimsemana", "val_cvu"]].copy()
            df["dat_iniciosemana"] = _parse_date_series(df["dat_iniciosemana"])
            df["dat_fimsemana"] = _parse_date_series(df["dat_fimsemana"])
            df["val_cvu"] = _normalize_br_numeric_series(df["val_cvu"])
            df = df.dropna(subset=["dat_iniciosemana", "dat_fimsemana", "val_cvu"])
            df = df[df["val_cvu"] > 0]
            if not df.empty:
                frames.append(df)
        except Exception:
            continue

    if not frames:
        return pd.Series(dtype=float)

    all_df = pd.concat(frames, ignore_index=True)
    weekly = (
        all_df.groupby(["dat_iniciosemana", "dat_fimsemana"], as_index=False)["val_cvu"]
        .mean()
        .sort_values("dat_fimsemana")
    )
    if weekly.empty:
        return pd.Series(dtype=float)
    return weekly.set_index("dat_fimsemana")["val_cvu"].astype(float)


def _expand_cvu_weekly_to_daily(ons: Dict[str, Any]) -> pd.Series:
    """Expande CVU semanal para valor diário no intervalo dat_iniciosemana..dat_fimsemana."""
    con = _duckdb_connect()
    if con is not None:
        try:
            if _duckdb_table_exists(con, "cvu_usina_termica"):
                q = f"""
                    SELECT
                        {_duckdb_date_expr('dat_iniciosemana')} AS dat_iniciosemana,
                        {_duckdb_date_expr('dat_fimsemana')} AS dat_fimsemana,
                        AVG({_duckdb_num_expr('val_cvu')}) AS val_cvu
                    FROM cvu_usina_termica
                    GROUP BY 1,2
                    HAVING dat_iniciosemana IS NOT NULL AND dat_fimsemana IS NOT NULL AND val_cvu > 0
                """
                wk = con.execute(q).fetchdf()
                if not wk.empty:
                    daily_vals: Dict[pd.Timestamp, float] = {}
                    for _, r in wk.iterrows():
                        start = pd.Timestamp(r["dat_iniciosemana"]).floor("D")
                        end = pd.Timestamp(r["dat_fimsemana"]).floor("D")
                        if end < start:
                            start, end = end, start
                        for d in pd.date_range(start, end, freq="D"):
                            daily_vals[d] = float(r["val_cvu"])
                    if daily_vals:
                        return pd.Series(daily_vals).sort_index()
        except Exception:
            pass
        finally:
            con.close()

    files = _find_ons_csv_all(ons, "CVU_Usina_Termica")
    if not files:
        return pd.Series(dtype=float)

    frames: List[pd.DataFrame] = []
    for cvu_file in files:
        try:
            df = pd.read_csv(cvu_file, sep=None, engine="python")
            needed = {"dat_iniciosemana", "dat_fimsemana", "val_cvu"}
            if not needed.issubset(df.columns):
                continue
            df = df[["dat_iniciosemana", "dat_fimsemana", "val_cvu"]].copy()
            df["dat_iniciosemana"] = _parse_date_series(df["dat_iniciosemana"])
            df["dat_fimsemana"] = _parse_date_series(df["dat_fimsemana"])
            df["val_cvu"] = _normalize_br_numeric_series(df["val_cvu"])
            df = df.dropna(subset=["dat_iniciosemana", "dat_fimsemana", "val_cvu"])
            df = df[df["val_cvu"] > 0]
            if not df.empty:
                frames.append(df)
        except Exception:
            continue

    if not frames:
        return pd.Series(dtype=float)

    wk = (
        pd.concat(frames, ignore_index=True)
        .groupby(["dat_iniciosemana", "dat_fimsemana"], as_index=False)["val_cvu"]
        .mean()
    )
    daily_vals: Dict[pd.Timestamp, float] = {}
    for _, r in wk.iterrows():
        start = pd.Timestamp(r["dat_iniciosemana"]).floor("D")
        end = pd.Timestamp(r["dat_fimsemana"]).floor("D")
        if end < start:
            start, end = end, start
        for d in pd.date_range(start, end, freq="D"):
            daily_vals[d] = float(r["val_cvu"])

    if not daily_vals:
        return pd.Series(dtype=float)
    return pd.Series(daily_vals).sort_index()


def _compute_cvu_from_csv(ons: Dict[str, Any]) -> Optional[float]:
    s = _load_cvu_weekly_series(ons)
    if s.empty:
        return None
    try:
        return float(s.iloc[-1])
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
    line = f"[{ts}] [build_core_analysis] [{stage}] {message}"
    if ctx:
        line = f"{line} | {ctx}"

    # stdout imediato (útil no terminal/powershell)
    print(line, flush=True)

    # persistência em arquivo para diagnóstico quando stdout não aparece
    try:
        log_path = os.environ.get("KINTUADI_CORE_LOG_PATH", os.path.join("data", "core_analysis_debug.log"))
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(line + "\n")
    except Exception:
        # logging não pode quebrar o pipeline principal
        pass


def _try_load_fresh_core_cache(output_dir: str = "data") -> Optional[Dict[str, Any]]:
    """Retorna core já persistido quando está sincronizado com o DuckDB (atalho de performance)."""
    try:
        final_path = os.path.join(output_dir, "core_analysis_latest.json")
        if not os.path.exists(final_path) or not os.path.exists(_DUCKDB_PATH):
            return None

        with open(final_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        if not isinstance(cached, dict):
            return None

        core_mtime = os.path.getmtime(final_path)
        db_mtime = os.path.getmtime(_DUCKDB_PATH)

        # Se o DB não mudou desde a geração do core, reaproveita.
        if core_mtime >= db_mtime:
            return cached
    except Exception:
        return None
    return None


def build_core_analysis(raw_data: Dict[str, Any], output_dir: str = "data", force_rebuild: bool = False) -> Dict[str, Any]:
    _core_log("START", "Entrou no build_core_analysis", output_dir=output_dir)
    if duckdb is None or not os.path.exists(_DUCKDB_PATH):
        raise RuntimeError("DuckDB obrigatório para build_core_analysis no modo atual.")

    if not force_rebuild:
        cached = _try_load_fresh_core_cache(output_dir=output_dir)
        if isinstance(cached, dict):
            _core_log("CACHE", "core_analysis_latest.json reaproveitado (DB inalterado)")
            return cached

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
    pld_series_by_submercado: Dict[str, pd.Series] = {}

    # --------------------------------------------
    # 🔎 Consolidar PLD histórico via DuckDB
    # --------------------------------------------
    df_pld = _duckdb_fetchdf("""
        SELECT
            data AS timestamp,
            submercado,
            pld AS pld_hora,
            ano,
            mes,
            hora
        FROM pld_historical
        WHERE data IS NOT NULL AND pld IS NOT NULL
        ORDER BY data
    """)
    _core_log("PLD", "Registros PLD consolidados (duckdb)", total_registros=len(df_pld), dataframe_vazio=df_pld.empty)

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

            pld_series_full = _ensure_tz_naive_index(df_pld.set_index("timestamp")["pld_hora"])

            # Submercados
            if "submercado" in df_pld.columns:
                for sub, grp in df_pld.groupby("submercado"):
                    pld_por_submercado[sub] = grp["pld_hora"].mean()
                    sm = _normalize_submercado_name(sub) or str(sub)
                    pld_series_by_submercado[sm] = _ensure_tz_naive_index(
                        grp.sort_values("timestamp").set_index("timestamp")["pld_hora"]
                    )

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

    if not df_pld.empty:
        pld_series = _ensure_tz_naive_index(
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
    cvu_semanal = _load_cvu_weekly_series(ons)
    cvu_diario = _expand_cvu_weekly_to_daily(ons)
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
            pld_series_by_submercado=pld_series_by_submercado,
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
        "thermal_analysis": {**indicadores_termicos, "cvu_semanal": {d.strftime("%Y-%m-%d"): float(v) for d, v in cvu_semanal.items()} if not cvu_semanal.empty else {}, "cvu_diario": {d.strftime("%Y-%m-%d"): float(v) for d, v in cvu_diario.items()} if not cvu_diario.empty else {}},
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
            "duckdb_path": _DUCKDB_PATH,
            "duckdb_mtime": datetime.fromtimestamp(os.path.getmtime(_DUCKDB_PATH)).isoformat() if os.path.exists(_DUCKDB_PATH) else None,
        },
    }

    # ---------------- Persist ----------------
    _core_log("PERSIST", "Iniciando persistência do core")

    # 1) Garantir diretório
    os.makedirs(output_dir, exist_ok=True)

    # 2) Salvar em arquivo temporário primeiro
    temp_path = os.path.join(output_dir, "core_analysis_temp.json")
    final_path = os.path.join(output_dir, "core_analysis_latest.json")

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(core, f, indent=2, ensure_ascii=False, default=str)

        _core_log("PERSIST", "Arquivo temporário salvo com sucesso", temp_path=temp_path)

        # 3) Limpar versões antigas (exceto temp recém-gerado)
        removidos = []
        for filename in os.listdir(output_dir):
            if (
                filename.startswith("core_analysis_")
                and filename.endswith(".json")
                and filename != "core_analysis_temp.json"
            ):
                target = os.path.join(output_dir, filename)
                os.remove(target)
                removidos.append(filename)

        _core_log("PERSIST", "Arquivos anteriores removidos", removidos=len(removidos))

        # 4) Promover temp para definitivo de forma atômica quando possível
        os.replace(temp_path, final_path)

    except Exception as e:
        _core_log("PERSIST", "Falha ao salvar core_analysis_latest.json", final_path=final_path, erro=str(e))
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        raise

    _core_log(
        "PERSIST",
        "core_analysis_latest.json salvo com sucesso",
        path=final_path,
        tamanho_bytes=os.path.getsize(final_path),
    )
    return core
