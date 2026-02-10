"""
Utilitários comuns do Kintuadi Energy.

Inclui serialização segura para JSON de objetos pandas, numpy e datetime.
"""

from __future__ import annotations

import json
from datetime import datetime, date
from typing import Any

import numpy as np
import pandas as pd


class JSONEncoder(json.JSONEncoder):
    """Encoder JSON robusto para pandas, numpy e datas."""

    def default(self, obj: Any):
        # None
        if obj is None:
            return None

        # numpy arrays e escalares
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)

        # pandas
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if isinstance(obj, pd.Series):
            return obj.tolist()
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient="records")

        # datas
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()

        # NaN / NA
        try:
            if pd.isna(obj):
                return None
        except Exception:
            pass

        return super().default(obj)


def make_serializable(obj: Any) -> Any:
    """
    Converte recursivamente qualquer objeto em algo serializável em JSON.
    """
    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [make_serializable(v) for v in obj]

    if isinstance(obj, np.ndarray):
        return obj.tolist()

    if isinstance(obj, (np.integer, np.int64)):
        return int(obj)

    if isinstance(obj, (np.floating, np.float64)):
        return float(obj)

    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")

    if isinstance(obj, pd.Series):
        return obj.tolist()

    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass

    # fallback final
    return str(obj)


def save_json(data: Any, filename: str) -> bool:
    """Salva dados em JSON usando encoder customizado."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, cls=JSONEncoder, ensure_ascii=False, indent=2)
        return True
    except Exception:
        try:
            serializable = make_serializable(data)
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False


def load_json(filename: str) -> Any:
    """Carrega dados de um arquivo JSON."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

import os
import csv
from datetime import datetime
from typing import List, Dict, Any


def save_records_to_csv(
    records: List[Dict[str, Any]],
    dataset_name: str,
    base_dir: str = "data",
) -> str:
    """
    Salva registros (lista de dicts) em CSV.
    - Remove arquivos antigos do mesmo dataset
    - Nomeia o arquivo com timestamp de coleta
    - Retorna o caminho do arquivo salvo
    """

    if not records:
        raise ValueError("Nenhum registro fornecido para salvar em CSV.")

    os.makedirs(base_dir, exist_ok=True)

    # Remove arquivos antigos do mesmo dataset
    for filename in os.listdir(base_dir):
        if filename.startswith(dataset_name) and filename.endswith(".csv"):
            os.remove(os.path.join(base_dir, filename))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(
        base_dir, f"{dataset_name}_{timestamp}.csv"
    )

    # Descobre todas as colunas possíveis
    fieldnames = sorted(
        {key for record in records for key in record.keys()}
    )

    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    return filepath
import shutil
import os
from datetime import datetime


def save_raw_csv_file(
    source_path: str,
    dataset_name: str,
    base_dir: str = "data",
) -> str:
    """
    Salva um CSV bruto (download direto), removendo versões anteriores.
    Retorna o caminho do arquivo salvo.
    """

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Arquivo CSV não encontrado: {source_path}")

    os.makedirs(base_dir, exist_ok=True)

    # Remove arquivos antigos
    for filename in os.listdir(base_dir):
        if filename.startswith(dataset_name) and filename.endswith(".csv"):
            os.remove(os.path.join(base_dir, filename))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_path = os.path.join(
        base_dir, f"{dataset_name}_{timestamp}.csv"
    )

    shutil.copy2(source_path, target_path)

    return target_path
