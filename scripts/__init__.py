# scripts/__init__.py - VERSÃO CORRIGIDA
"""
Kintuadi Energy - Pacote de scripts para coleta de dados energéticos
"""

__version__ = "1.1.0"
__author__ = "Kintuadi Energy Team"

# Importações principais
try:
    from .ccee_collector import CCEECollector
    from .ons_reservatorios import ONSReservatoriosCollector
    from .ons_auth import ONSAuthenticator
    from .ons_volume_util import ONSVolumeUtilCollector
    from .integrated_collector import KintuadiIntegratedCollector
    from .energy_analyzer import EnergyAnalyzer
    
    # CORREÇÃO: Remover JSONEncoder se não existe em utils.py
    try:
        from .utils import make_serializable, save_json, load_json
        UTILS_AVAILABLE = True
    except ImportError:
        # Cria funções fallback se utils não estiver disponível
        UTILS_AVAILABLE = False
        print("⚠️ Utils não disponível, usando fallback")
        
        def make_serializable(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_serializable(v) for v in obj]
            else:
                return obj
        
        def save_json(data, filename):
            import json
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(make_serializable(data), f, ensure_ascii=False, indent=2)
        
        def load_json(filename):
            import json
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    __all__ = [
        'CCEECollector',
        'ONSReservatoriosCollector',
        'ONSAuthenticator',
        'ONSVolumeUtilCollector',
        'KintuadiIntegratedCollector',
        'EnergyAnalyzer',
        'make_serializable',
        'save_json',
        'load_json'
    ]
    
    MODULES_LOADED = True
    
except ImportError as e:
    print(f"⚠️ Aviso: Erro ao importar módulos: {e}")
    __all__ = []
    MODULES_LOADED = False

def get_version():
    return __version__

def get_available_modules():
    return __all__

def print_package_info():
    info = f"""
╔{'═'*50}╗
║{'KINTUADI ENERGY v1.1':^50}║
╠{'═'*50}╣
║ {'Versão:':<15} {__version__:<34} ║
║ {'Autor:':<15} {__author__:<34} ║
║ {'Status:':<15} {'✅ OPERACIONAL':<34} ║
╚{'═'*50}╝
    """
    print(info)
    
    if MODULES_LOADED and __all__:
        print("📦 Módulos carregados:")
        for i, module in enumerate(__all__, 1):
            print(f"  {i}. {module}")