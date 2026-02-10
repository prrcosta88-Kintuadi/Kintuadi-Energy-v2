"""
Kintuadi Energy
Pacote de scripts para coleta, análise e integração de dados
do mercado de energia elétrica brasileiro (ONS + CCEE).

Este pacote prioriza módulos v2 e mantém compatibilidade
controlada com módulos legados quando disponíveis.
"""

from __future__ import annotations

__version__ = "2.0.0"
__author__ = "Kintuadi Energy"


# Flags internas
MODULES_LOADED = False
UTILS_AVAILABLE = False


# =========================
# IMPORTAÇÕES PRINCIPAIS (V2)
# =========================
try:
    from .ccee_collector_v2 import CCEEPLDCollector
    from .ons_collector_v2 import ONSCollectorV2
    from .integrated_collector_v2 import KintuadiIntegratedCollectorV2
    from .core_analysis import build_core_analysis

    MODULES_LOADED = True

except ImportError as e:
    # Não imprime erro aqui para não poluir imports
    MODULES_LOADED = False
    _IMPORT_ERROR_V2 = e


# =========================
# UTILITÁRIOS
# =========================
try:
    from .utils import (
        make_serializable,
        save_json,
        load_json,
        save_records_to_csv,
        save_raw_csv_file,
    )
    UTILS_AVAILABLE = True

except ImportError:
    # Fallback mínimo e seguro
    UTILS_AVAILABLE = False

    def make_serializable(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [make_serializable(v) for v in obj]
        return obj

    def save_json(data, filename):
        import json
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(make_serializable(data), f, ensure_ascii=False, indent=2)

    def load_json(filename):
        import json
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)


# =========================
# EXPORTS PÚBLICOS
# =========================
__all__ = []

if MODULES_LOADED:
    __all__.extend([
        "CCEEPLDCollector",
        "ONSCollectorV2",
        "KintuadiIntegratedCollectorV2",
        "build_core_analysis",
    ])

__all__.extend([
    "make_serializable",
    "save_json",
    "load_json",
    "save_records_to_csv",
    "save_raw_csv_file",
    "get_version",
    "get_available_modules",
    "print_package_info",
])


# =========================
# FUNÇÕES DE APOIO
# =========================
def get_version() -> str:
    """Retorna a versão do pacote."""
    return __version__


def get_available_modules() -> list[str]:
    """Lista os módulos públicos disponíveis no pacote."""
    return __all__


def print_package_info() -> None:
    """Exibe informações resumidas do pacote no terminal."""
    status = "✅ OPERACIONAL" if MODULES_LOADED else "⚠️ PARCIAL"

    info = f"""
╔{'═' * 56}╗
║{'KINTUADI ENERGY':^56}║
╠{'═' * 56}╣
║ {'Versão:':<18} {__version__:<36} ║
║ {'Autor:':<18} {__author__:<36} ║
║ {'Status:':<18} {status:<36} ║
╚{'═' * 56}╝
"""
    print(info)

    if __all__:
        print("📦 Módulos exportados:")
        for i, module in enumerate(__all__, 1):
            print(f"  {i}. {module}")
