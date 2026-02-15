# run_collector.py atualizado
#!/usr/bin/env python3
"""
Kintuadi Energy - Coletor Principal v2.0
"""

import os
import sys
import subprocess
import logging
from datetime import datetime
from dotenv import load_dotenv

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def setup_environment():
    """Configura o ambiente"""
    
    # Cria diretórios necessários
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # Configura Streamlit
    config_dir = os.path.join(os.path.expanduser("~"), ".streamlit")
    config_file = os.path.join(config_dir, "config.toml")
    
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    if not os.path.exists(config_file):
        config_content = """[browser]
gatherUsageStats = false

[server]
address = "localhost"
port = 8501

[theme]
base = "dark"
"""
        with open(config_file, 'w') as f:
            f.write(config_content)
        logger.info("Configuração do Streamlit criada")
    
    # Carrega variáveis de ambiente
    load_dotenv()

def check_dependencies():
    """Verifica dependências"""
    try:
        import streamlit
        import pandas
        import plotly
        import requests
        logger.info("✅ Dependências verificadas")
        return True
    except ImportError as e:
        logger.error(f"❌ Dependência faltando: {e}")
        return False

def print_banner():
    """Exibe banner do sistema"""
    banner = f"""
╔{'═'*60}╗
║{'KINTUADI ENERGY INTELLIGENCE v2.0':^60}║
╠{'═'*60}╣
║{'Plataforma de Análise do Mercado de Energia':^60}║
║{datetime.now().strftime('%d/%m/%Y %H:%M:%S'):^60}║
╚{'═'*60}╝
    """
    print(banner)

def run_collector_v2():
    """Executa o coletor v2.0"""
    try:
        from scripts.integrated_collector_v2 import KintuadiIntegratedCollectorV2
        collector = KintuadiIntegratedCollectorV2()
        return collector.quick_collect()
    except ImportError as e:
        logger.error(f"Erro ao importar coletor v2: {e}")
        return None

def run_dashboard():
    """Executa o dashboard"""
    print("\n🌐 Iniciando Kintuadi Dashboard...")
    print("   Acesse: http://localhost:8501")
    print("   Pressione Ctrl+C para encerrar\n")
    
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "dashboard_integrado.py"],
            check=True
        )
    except KeyboardInterrupt:
        print("\n⏹️ Dashboard encerrado pelo usuário")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar dashboard: {e}")
        print("\n💡 Tente manualmente: python -m streamlit run dashboard_integrado.py")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")

def main():
    """Função principal"""
    
    # Configura ambiente
    setup_environment()
    
    # Verifica dependências
    if not check_dependencies():
        print("\n⚠️ Instale as dependências:")
        print("pip install -r requirements.txt")
        return
    
    # Exibe banner
    print_banner()
    
    # Menu principal
    while True:
        print("\n" + "="*60)
        print("🎯 MENU PRINCIPAL")
        print("="*60)
        print("1. Coleta completa + Dashboard")
        print("2. Apenas coletar dados (v2.0)")
        print("3. Apenas abrir dashboard")
        print("4. Coleta rápida (teste)")
        print("5. Verificar sistema")
        print("6. Sair")
        print("="*60)
        
        choice = input("\nEscolha (1-6): ").strip()
        
        if choice == "1":
            # Coleta completa + Dashboard
            print("\n📊 Executando coleta completa...")
            if run_collector_v2():
                print("\n✅ Coleta concluída! Iniciando dashboard...")
                run_dashboard()
        
        elif choice == "2":
            # Apenas coleta
            print("\n📥 Coletando dados...")
            run_collector_v2()
        
        elif choice == "3":
            # Apenas dashboard
            run_dashboard()
        
        elif choice == "4":
            # Coleta rápida
            print("\n⚡ Coleta rápida...")
            run_collector_v2()
        
        elif choice == "5":
            # Verificar sistema
            check_system()
        
        elif choice == "6":
            print("\n👋 Até logo!")
            break
        
        else:
            print("❌ Opção inválida")

def check_system():
    """Verifica status do sistema"""
    print("\n🔍 VERIFICANDO SISTEMA")
    print("-"*40)
    
    # Verifica diretórios
    dirs = ["data", "logs", "scripts"]
    for d in dirs:
        if os.path.exists(d):
            print(f"✅ {d}/")
        else:
            print(f"❌ {d}/ (não existe)")
    
    # Verifica arquivos principais
    files = ["dashboard_integrado.py", "requirements.txt", "run_collector.py"]
    for f in files:
        if os.path.exists(f):
            print(f"✅ {f}")
        else:
            print(f"❌ {f} (não existe)")
    
    # Verifica dados recentes
    import glob
    recent_files = glob.glob("data/kintuadi_*.json")
    if recent_files:
        latest = max(recent_files, key=os.path.getmtime)
        print(f"✅ Dados mais recentes: {os.path.basename(latest)}")
    else:
        print("❌ Nenhum dado coletado encontrado")
    
    print("-"*40)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ Programa interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()