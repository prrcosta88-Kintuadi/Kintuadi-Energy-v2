import json
import logging
from datetime import datetime
import os
from typing import Dict, Any, Optional
import hashlib


class AuditLogger:
    """Sistema de auditoria (RAW, eventos e rastreabilidade)."""

    def __init__(self, base_dir: str = "audit_logs"):
        self.base_dir = base_dir

        self.paths = {
            "raw": os.path.join(base_dir, "raw"),
            "api": os.path.join(base_dir, "api"),
            "transform": os.path.join(base_dir, "transform"),
            "anomaly": os.path.join(base_dir, "anomaly"),
            "consolidation": os.path.join(base_dir, "consolidation"),
        }

        for path in self.paths.values():
            os.makedirs(path, exist_ok=True)

        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)

        if not self.logger.handlers:
            log_file = os.path.join(
                base_dir, f"audit_{datetime.now().strftime('%Y%m%d')}.log"
            )
            handler = logging.FileHandler(log_file, encoding="utf-8")
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    # ----------------------------
    # PUBLIC METHODS
    # ----------------------------

    def log_api_call(self, source: str, url: str, params: Dict,
                     response_status: int, data_sample: Any):
        entry = self._base_entry(source)
        entry.update({
            "type": "api_call",
            "url": url,
            "params": params,
            "status": response_status,
            "data_sample": self._get_sample(data_sample),
            "hash": self._generate_hash(data_sample),
        })

        self.logger.info(f"API CALL [{source}] status={response_status}")
        self._save_json("api", entry)

    def log_data_transformation(self, source: str, raw_data: Any,
                                processed_data: Any, transformation: str):
        entry = self._base_entry(source)
        entry.update({
            "type": "transformation",
            "transformation": transformation,
            "raw_sample": self._get_sample(raw_data),
            "processed_sample": self._get_sample(processed_data),
            "raw_hash": self._generate_hash(raw_data),
            "processed_hash": self._generate_hash(processed_data),
        })

        self.logger.info(f"TRANSFORM [{source}] {transformation}")
        self._save_json("transform", entry)

    def log_anomaly(self, source: str, data_point: Any,
                    expected: Any, actual: Any, severity: str = "WARNING"):
        entry = self._base_entry(source)
        entry.update({
            "type": "anomaly",
            "severity": severity,
            "data_point": data_point,
            "expected": expected,
            "actual": actual,
            "deviation_pct": self._calculate_deviation(expected, actual),
        })

        self.logger.warning(f"ANOMALY [{source}] {data_point}={actual}")
        self._save_json("anomaly", entry)

    def log_consolidation(self, source_list: list,
                          consolidated_sample: Any, rules_applied: list):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "consolidation",
            "sources": source_list,
            "rules_applied": rules_applied,
            "sample": self._get_sample(consolidated_sample),
            "hash": self._generate_hash(consolidated_sample),
        }

        self.logger.info(f"CONSOLIDATION from {len(source_list)} sources")
        self._save_json("consolidation", entry)

    def save_raw_data(self, source: str, raw_data: Any, metadata: Dict = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "metadata": metadata or {},
            "hash": self._generate_hash(raw_data),
            "data": raw_data,
        }

        filename = f"raw_{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = os.path.join(self.paths["raw"], filename)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False, default=str)

        self.logger.info(f"RAW SAVED [{source}] {filename}")
        return path

    # ----------------------------
    # INTERNAL HELPERS
    # ----------------------------

    def _base_entry(self, source: str) -> Dict[str, Any]:
        return {
            "timestamp": datetime.now().isoformat(),
            "source": source,
        }

    def _save_json(self, category: str, entry: Dict):
        filename = f"{category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = os.path.join(self.paths[category], filename)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False, default=str)

    def _generate_hash(self, data: Any) -> str:
        payload = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def _get_sample(self, data: Any, max_items: int = 3) -> Any:
        if isinstance(data, list):
            return data[:max_items]
        if isinstance(data, dict):
            return dict(list(data.items())[:max_items])
        return data

    def _calculate_deviation(self, expected: Any, actual: Any) -> Optional[float]:
        try:
            if isinstance(expected, (list, tuple)) and len(expected) == 2:
                mid = (expected[0] + expected[1]) / 2
                return abs((actual - mid) / mid * 100)
        except Exception:
            return None
