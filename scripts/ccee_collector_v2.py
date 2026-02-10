from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
import statistics
import requests

# Import defensivo (execução como pacote OU script)
try:
    from .utils import save_records_to_csv
except ImportError:
    from scripts.utils import save_records_to_csv


logger = logging.getLogger(__name__)


class CCEEPLDCollector:
    """
    Coletor CCEE v2.3

    Responsável EXCLUSIVAMENTE por:
    - Dados econômicos públicos da CCEE
    - PLD horário
    - Open Data CKAN (datasets independentes)

    NÃO interpreta mercado, risco ou operação.
    """

    # =============================
    # CONFIGURAÇÕES CKAN CCEE
    # =============================
    CKAN_BASE_URL = "https://dadosabertos.ccee.org.br/api/3/action/datastore_search"

    # PLD horário
    PLD_RESOURCE_ID = "3f279d6b-1069-42f7-9b0a-217b084729c4"

    # Open Data – APIs distintas
    OPEN_DATASETS = {
        "contabilizacao_montante_perfil_agente": "76d1cf4c-da8c-47a5-9f0d-8b50079be960",
        "sumario_balanco_energetico_horario": "9418da65-0f9f-4f66-a43f-6517db9653f3",
        "sumario_distribuicao_mensal": "9e8e3f5f-58a8-4744-b6da-7309a4513fcb",
    }

    def __init__(self, cache_ttl_minutes: int = 60, enable_audit: bool = True):
        self.cache_ttl_minutes = cache_ttl_minutes
        self.enable_audit = enable_audit

    # =============================
    # API PÚBLICA
    # =============================

    def collect_pld_data(
        self,
        days: Optional[int] = None,
        limit: int = 100000,
    ) -> Dict[str, Any]:
        """
        Coleta PLD horário via CKAN.

        Parâmetro `days` é aceito por compatibilidade com o orquestrador,
        mas o CKAN da CCEE não suporta filtro temporal direto.
        """
        start_time = datetime.now()

        try:
            records = self._fetch_pld(limit=limit)

            csv_path = save_records_to_csv(
                records=records,
                dataset_name="ccee_pld_horario",
            )

            stats = self._calculate_statistics(records)
            timeseries = self._build_timeseries(records)

            return {
                "metadata": {
                    "source": "CCEE",
                    "dataset": "PLD_HORARIO",
                    "status": "success",
                    "records_processed": len(records),
                    "collection_time": start_time.isoformat(),
                    "csv_file": csv_path,
                },
                "data": records,
                "statistics": {"geral": stats},
                "timeseries": timeseries,
            }

        except Exception as e:
            logger.error(f"Erro na coleta PLD CCEE: {e}", exc_info=True)
            return {
                "metadata": {
                    "source": "CCEE",
                    "dataset": "PLD_HORARIO",
                    "status": "error",
                    "error_message": str(e),
                    "collection_time": start_time.isoformat(),
                },
                "data": [],
                "statistics": {},
                "timeseries": [],
            }

    def collect_open_data_csv(self, limit: int = 100000) -> Dict[str, Any]:
        """
        Coleta Open Data da CCEE via CKAN.

        Cada API (resource_id) gera:
        - 1 CSV independente
        - 1 bloco de metadata próprio
        """
        start_time = datetime.now()
        datasets: Dict[str, Any] = {}

        try:
            for dataset_name, resource_id in self.OPEN_DATASETS.items():
                records = self._fetch_open_dataset(
                    dataset_name=dataset_name,
                    resource_id=resource_id,
                    limit=limit,
                )

                csv_path = save_records_to_csv(
                    records=records,
                    dataset_name=f"ccee_{dataset_name}",
                )

                datasets[dataset_name] = {
                    "records": records,             #lista de registros
                    "csv_file": csv_path,
                    "resource_id": resource_id,
                    "record_count": len(records),   #opcional, útil
                }

            return {
                "metadata": {
                    "source": "CCEE",
                    "dataset": "OPEN_DATA",
                    "status": "success",
                    "datasets_collected": len(datasets),
                    "collection_time": start_time.isoformat(),
                },
                "datasets": datasets,
            }

        except Exception as e:
            logger.error(f"Erro na coleta Open Data CCEE: {e}", exc_info=True)
            return {
                "metadata": {
                    "source": "CCEE",
                    "dataset": "OPEN_DATA",
                    "status": "error",
                    "error_message": str(e),
                    "collection_time": start_time.isoformat(),
                },
                "datasets": {},
            }

    # =============================
    # MÉTODOS INTERNOS
    # =============================

    def _fetch_pld(self, limit: int = 5000) -> List[Dict[str, Any]]:
        all_records: List[Dict[str, Any]] = []
        offset = 0

        while True:
            params = {
                "resource_id": self.PLD_RESOURCE_ID,
                "limit": limit,
                "offset": offset,
            }

            response = requests.get(self.CKAN_BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            payload = response.json()
            if not payload.get("success"):
                raise RuntimeError("API PLD CCEE retornou success=False")

            records = payload.get("result", {}).get("records", [])

            if not records:
                break

            for r in records:
                r["_dataset"] = "pld_horario"
                r["_resource_id"] = self.PLD_RESOURCE_ID

            all_records.extend(records)

            logger.info(
                f"CCEE | PLD horário | +{len(records)} registros "
                f"(total: {len(all_records)})"
            )

            if len(records) < limit:
                break

            offset += limit

        return all_records

    def _fetch_open_dataset(
        self,
        dataset_name: str,
        resource_id: str,
        limit: int = 5000,
    ) -> List[Dict[str, Any]]:
        
        """
        Coleta dataset CKAN com paginação completa.
        """
        all_records: List[Dict[str, Any]] = []
        offset = 0

        while True:
            params = {
                "resource_id": resource_id,
                "limit": limit,
                "offset": offset,
            }

            response = requests.get(self.CKAN_BASE_URL, params=params, timeout=30)
            response.raise_for_status()

            payload = response.json()
            if not payload.get("success"):
                raise RuntimeError(
                    f"Dataset {dataset_name} retornou success=False"
                )

            result = payload.get("result", {})
            records = result.get("records", [])

            if not records:
                break

            for r in records:
                r["_dataset"] = dataset_name
                r["_resource_id"] = resource_id

            all_records.extend(records)

            logger.info(
                f"CCEE | {dataset_name} | +{len(records)} registros "
                f"(total: {len(all_records)})"
            )

            if len(records) < limit:
                break

            offset += limit

        return all_records

    def _calculate_statistics(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        plds = [
            r.get("PLD_HORA")
            for r in records
            if isinstance(r.get("PLD_HORA"), (int, float))
        ]

        return {
            "quantidade": len(plds),
            "pld_medio": statistics.mean(plds) if plds else None,
            "pld_std": statistics.stdev(plds) if len(plds) > 1 else None,
            "pld_min": min(plds) if plds else None,
            "pld_max": max(plds) if plds else None,
        }

    def _build_timeseries(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        timeseries = []

        for r in records:
            try:
                timeseries.append(
                    {
                        "mes_referencia": r.get("MES_REFERENCIA"),
                        "dia": int(r.get("DIA")) if r.get("DIA") is not None else None,
                        "hora": int(r.get("HORA")) if r.get("HORA") is not None else None,
                        "submercado": r.get("SUBMERCADO"),
                        "pld": r.get("PLD_HORA"),
                    }
                )
            except Exception:
                continue

        return sorted(
            timeseries,
            key=lambda x: (
                x.get("mes_referencia"),
                x.get("dia"),
                x.get("hora"),
                x.get("submercado"),
            ),
        )
