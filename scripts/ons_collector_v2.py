from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
import logging
import csv
import io
import os
import tempfile
import requests

# Import defensivo
try:
    from .utils import save_records_to_csv, save_raw_csv_file
except ImportError:
    from scripts.utils import save_records_to_csv, save_raw_csv_file


logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
OPEN_DATA_TIMEOUT = 60

ENERGIA_AGORA_BASE_URL = "https://integra.ons.org.br/api/energiaagora/Get"
EXPECTED_API_DISABLE_MESSAGE = "API desabilitada"


# ======================================================================
# API Energia Agora – configuração
# ======================================================================

ENERGIA_AGORA_ENDPOINTS = [
    # SIN
    "Geracao_SIN_Eolica_json",
    "Geracao_SIN_Hidraulica_json",
    "Geracao_SIN_Nuclear_json",
    "Geracao_SIN_Solar_json",
    "Geracao_SIN_Termica_json",
    # Submercados
    "Geracao_Norte_Eolica_json",
    "Geracao_Norte_Hidraulica_json",
    "Geracao_Norte_Nuclear_json",
    "Geracao_Norte_Solar_json",
    "Geracao_Norte_Termica_json",
    "Geracao_Nordeste_Eolica_json",
    "Geracao_Nordeste_Hidraulica_json",
    "Geracao_Nordeste_Nuclear_json",
    "Geracao_Nordeste_Solar_json",
    "Geracao_Nordeste_Termica_json",
    "Geracao_Sudeste_Eolica_json",
    "Geracao_Sudeste_Hidraulica_json",
    "Geracao_Sudeste_Nuclear_json",
    "Geracao_Sudeste_Solar_json",
    "Geracao_Sudeste_Termica_json",
    "Geracao_Sul_Eolica_json",
    "Geracao_Sul_Hidraulica_json",
    "Geracao_Sul_Nuclear_json",
    "Geracao_Sul_Solar_json",
    "Geracao_Sul_Termica_json",
    "Geracao_SudesteECentroOeste_Eolica_json",
    "Geracao_SudesteECentroOeste_Hidraulica_json",
    "Geracao_SudesteECentroOeste_Nuclear_json",
    "Geracao_SudesteECentroOeste_Solar_json",
    "Geracao_SudesteECentroOeste_Termica_json",
]

CARGA_AGORA_ENDPOINTS = [
    "Carga_SIN_json",
    "Carga_Norte_json",
    "Carga_Nordeste_json",
    "Carga_SudesteECentroOeste_json",
    "Carga_Sul_json",
]


# ======================================================================
# Collector
# ======================================================================

class ONSCollectorV2:
    """
    Coletor ONS v2.6

    Responsável por:
    - Dados físicos e hidrológicos (Open Data CSV)
    - Dados operacionais (Energia Agora API)
    - Persistência bruta (CSV)
    """

    OPEN_DATASETS: List[Tuple[str, str]] = [
        ("Reservatorios", "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/reservatorio/RESERVATORIOS.csv"),
        ("EAR_Diario_Reservatorios", "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_reservatorio_di/EAR_DIARIO_RESERVATORIOS_2026.csv"),
        ("ENA_Diario_Reservatorios", "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_reservatorio_di/ENA_DIARIO_RESERVATORIOS_2026.csv"),
        ("EAR_Diario_Subsistema", "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_subsistema_di/EAR_DIARIO_SUBSISTEMA_2026.csv"),
        ("ENA_Diario_Subsistema", "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_subsistema_di/ENA_DIARIO_SUBSISTEMA_2026.csv"),
        ("Intercambio_Nacional", "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/intercambio_nacional_ho/INTERCAMBIO_NACIONAL_2026.csv"),
        ("Capacidade_Instalada", "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/capacidade-geracao/CAPACIDADE_GERACAO.csv"),
        ("CVU_Usina_Termica", "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/cvu_usitermica_se/CVU_USINA_TERMICA_2026.csv"),
    ]

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        enable_audit: bool = True,
    ):
        self.username = username
        self.password = password
        self.enable_audit = enable_audit
        self.api_headers: Optional[Dict[str, str]] = None

    # ==================================================================
    # API pública
    # ==================================================================

    def collect_open_data(self) -> Dict[str, Any]:
        start_time = datetime.now()
        datasets: List[Dict[str, Any]] = []

        # ---------- OPEN DATA (CSV S3) ----------
        for name, url in self.OPEN_DATASETS:
            try:
                logger.info(f"ONS | OpenData | {name}")
                path, rows = self._fetch_and_save_csv(url, name)
                datasets.append({
                    "dataset": name,
                    "type": "csv",
                    "records": rows,
                    "file": path,
                    "origin": "open_data",
                })
            except Exception as e:
                logger.warning(f"ONS | Falha OpenData {name}: {e}")

        # ---------- API ENERGIA AGORA ----------
        
        datasets.extend(self._collect_api_series())

        return {
            "metadata": {
                "source": "ONS",
                "status": "success",
                "datasets_collected": len(datasets),
                "collection_time": start_time.isoformat(),
            },
            "datasets": datasets,
        }

    # ==================================================================
    # Open Data helpers
    # ==================================================================

    def _fetch_and_save_csv(self, url: str, dataset_name: str) -> Tuple[str, int]:
        response = requests.get(url, timeout=OPEN_DATA_TIMEOUT)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(response.content)
            temp_path = tmp.name

        final_path = save_raw_csv_file(
            source_path=temp_path,
            dataset_name=f"ons_{dataset_name.lower()}",
        )

        rows = self._count_csv_rows(response.content)
        return final_path, rows

    def _count_csv_rows(self, content: bytes) -> int:
        text_stream = io.StringIO(content.decode("utf-8", errors="ignore"))
        reader = csv.reader(text_stream)
        return max(sum(1 for _ in reader) - 1, 0)

    # ==================================================================
    # API Energia Agora helpers
    # ==================================================================

    def _authenticate(self) -> bool:
        if not self.username or not self.password:
            logger.info("ONS | API Energia Agora não configurada (sem credenciais)")
            return False

        try:
            resp = requests.post(
                f"{ENERGIA_AGORA_BASE_URL}/autenticar",
                json={"usuario": self.username, "senha": self.password},
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            token = resp.json().get("access_token")
            token_type = resp.json().get("token_type", "bearer")

            self.api_headers = {
                "Authorization": f"{token_type.capitalize()} {token}",
                "accept": "application/json",
            }
            logger.info("ONS | Autenticação API bem-sucedida")
            return True

        except Exception as e:
            logger.warning(f"ONS | Falha na autenticação API: {e}")
            return False

    def _is_api_disabled(self, resp: requests.Response) -> bool:
        """
        Detecta respostas padrão do ONS quando a API Energia Agora está desabilitada.
        """
        try:
            if resp.status_code in (401, 403, 404):
                return True

            text = resp.text.lower()
            return EXPECTED_API_DISABLE_MESSAGE.lower() in text

        except Exception:
            return False

    def _collect_api_series(self) -> List[Dict[str, Any]]:
        collected = []

        headers = {"accept": "application/json"}

        for endpoint in ENERGIA_AGORA_ENDPOINTS + CARGA_AGORA_ENDPOINTS:
            url = f"{ENERGIA_AGORA_BASE_URL}/{endpoint}"

            try:
                logger.info(f"ONS | Energia Agora | {endpoint}")
                resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)

                if self._is_api_disabled(resp):
                    logger.warning(f"ONS | API Energia Agora desabilitada ({endpoint})")
                    continue

                resp.raise_for_status()
                records = resp.json()

                if not isinstance(records, list) or not records:
                    logger.warning(f"ONS | Energia Agora vazio ({endpoint})")
                    continue

                path = save_records_to_csv(
                    records,
                    dataset_name=f"ons_{endpoint.lower().replace('_json','')}",
                )

                collected.append({
                    "dataset": endpoint.replace("_json", ""),
                    "type": "csv",
                    "records": len(records),
                    "file": path,
                    "origin": "energia_agora",
                })

            except Exception as e:
                logger.warning(f"ONS | Falha Energia Agora {endpoint}: {e}")

        return collected
