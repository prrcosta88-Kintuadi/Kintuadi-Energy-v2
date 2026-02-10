# scripts/integrated_collector_v2.py
import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class KintuadiIntegratedCollectorV2:
    """
    Integrador central de dados – Kintuadi Energy v2

    Responsabilidades:
    - Orquestrar coleta ONS + CCEE
    - Normalizar estrutura de saída
    - Persistir dados para consumo do dashboard
    - NÃO realizar análise de mercado
    """

    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("logs/kintuadi.log"),
            ],
        )

        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)

        try:
            from .ons_collector_v2 import ONSCollectorV2
            from .ccee_collector_v2 import CCEEPLDCollector

            self.ons_collector = ONSCollectorV2(
                username=os.getenv("ONS_API_USER"),
                password=os.getenv("ONS_API_PASSWORD"),
                enable_audit=True,
            )

            self.ccee_collector = CCEEPLDCollector(
                cache_ttl_minutes=60, enable_audit=True
            )

            self.modules_loaded = True
        except Exception as e:
            logger.error(f"Erro ao carregar coletores: {e}")
            self.modules_loaded = False

    # ------------------------------------------------------------------
    # Core orchestration
    # ------------------------------------------------------------------
    def collect_all(self) -> Optional[Dict[str, Any]]:
        if not self.modules_loaded:
            logger.error("Coletores não carregados.")
            return None
        if not self.ons_collector or not self.ccee_collector or not self.analyzer:
            logger.error("Coletores não inicializados. Verifique erros de importação.")
            return None
        
        logger.info("=" * 70)
        logger.info("⚡ KINTUADI ENERGY – DATA COLLECTION v2.0")
        logger.info("=" * 70)

        start_time = datetime.now()

        try:
            results = {
                "metadata": {
                    "collection_start": start_time.isoformat(),
                    "version": "2.0",
                    "project": "Kintuadi Energy Intelligence",
                },
                "sources": {},
            }

            # ---------------- ONS ----------------
            logger.info("[1/2] Coletando dados do ONS...")
            ons_data = self.ons_collector.collect_open_data()
            results["sources"]["ons"] = self._normalize_source(ons_data)

            # ---------------- CCEE ----------------
            logger.info("[2/2] Coletando dados da CCEE...")
            open_data = self.ccee_collector.collect_open_data_csv(limit=100000)    
            ccee_data = self.ccee_collector.collect_pld_data()
            ccee_data["open_data_csv"] = open_data.get("datasets", {})
            ccee_data["open_data_metadata"] = open_data.get("metadata", {})
            #ccee_data["open_data_csv"] = self.ccee_collector.collect_open_data_csv(limit=100000)
            results["sources"]["ccee"] = self._normalize_source(ccee_data)

            # ---------------- Finalização ----------------
            end_time = datetime.now()
            results["metadata"]["collection_end"] = end_time.isoformat()
            results["metadata"]["collection_duration"] = (
                end_time - start_time
            ).total_seconds()

            results["metadata"]["overall_status"] = self._compute_overall_status(
                results["sources"]
            )

            self._persist(results)
            self._log_summary(results)

            logger.info("✅ Coleta concluída com sucesso.")
            return results

        except Exception as e:
            logger.error(f"Erro crítico na coleta: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _normalize_source(self, source_data: Dict) -> Dict:
        """
        Garante que cada fonte tenha estrutura previsível:
        - data
        - statistics
        - timeseries
        - open_data_csv
        - metadata (dict)
        """
        normalized = dict(source_data)

        metadata = normalized.get("metadata", {})
        if hasattr(metadata, "to_dict"):
            metadata = metadata.to_dict()

        normalized["metadata"] = metadata
        return normalized

    def _compute_overall_status(self, sources: Dict[str, Dict]) -> str:
        success = 0
        for src in sources.values():
            meta = src.get("metadata", {})
            if meta.get("status") == "success":
                success += 1

        if success == len(sources):
            return "success"
        if success > 0:
            return "partial"
        return "error"

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _persist(self, data: Dict):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        complete_file = f"data/kintuadi_raw_{timestamp}.json"
        latest_file = "data/kintuadi_latest.json"

        with open(complete_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"📁 Dados salvos:")
        logger.info(f"  • {complete_file}")
        logger.info(f"  • {latest_file}")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _log_summary(self, data: Dict):
        try:
            ons_meta = (
                data.get("sources", {})
                .get("ons", {})
                .get("metadata", {})
            )
            ccee_stats = (
                data.get("sources", {})
                .get("ccee", {})
                .get("statistics", {})
                .get("geral", {})
            )

            logger.info(
                f"ONS | Datasets coletados: {ons_meta.get('datasets_collected', 'N/A')} | "
                f"Status: {ons_meta.get('status', 'N/A')}"
            )

            logger.info(
                f"CCEE | PLD médio: {ccee_stats.get('pld_medio', 'N/A')} | "
                f"Volatilidade: {ccee_stats.get('pld_std', 'N/A')}"
            )

        except Exception as e:
            logger.warning(f"Erro ao gerar resumo: {e}")

    # ------------------------------------------------------------------
    # CLI helper
    # ------------------------------------------------------------------
    def quick_collect(self):
        print("🚀 Iniciando coleta Kintuadi Energy v2...")
        results = self.collect_all()

        if not results:
            print("❌ Falha na coleta.")
            return None

        print("✅ Coleta concluída.")
        print("📁 Dados disponíveis em data/kintuadi_latest.json")
        print("🌐 Execute: streamlit run dashboard_integrado.py")
        return results
