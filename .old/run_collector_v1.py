# run_collector.py - VERSÃO OTIMIZADA
#!/usr/bin/env python3
"""
Script principal para execução do Kintuadi Energy Collector
"""

import os
import sys
import subprocess
from datetime import datetime
from dotenv import load_dotenv

def setup_streamlit_config():
    """Configura o Streamlit para não pedir email"""
    config_dir = os.path.join(os.path.expanduser("~"), ".streamlit")
    config_file = os.path.join(config_dir, "config.toml")
    
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    if not os.path.exists(config_file):
        config_content = """[browser]
gatherUsageStats = false

[server]
address = "localhost"

[theme]
base = "light"
"""
        with open(config_file, 'w') as f:
            f.write(config_content)
        print("⚙️ Configuração do Streamlit criada")

def main():
    # Configura Streamlit
    setup_streamlit_config()
    
    print("=" * 60)
    print("🚀 KINTUADI ENERGY - PLATAFORMA DE ANÁLISE")
    print("=" * 60)
    print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    # Verifica se temos todos os módulos
    try:
        from scripts import print_package_info
        print_package_info()
    except Exception as e:
        print(f"⚠️ {e}")
    
    print("\n🎯 O que você quer fazer?")
    print("1. Executar coleta completa + dashboard")
    print("2. Apenas coletar dados")
    print("3. Apenas abrir dashboard (se já tiver dados)")
    print("4. Sair")
    
    choice = input("\nEscolha (1-4): ").strip()
    
    if choice == "1":
        # Coleta + dashboard
        run_collector_and_dashboard()
    elif choice == "2":
        # Apenas coleta
        run_collector_only()
    elif choice == "3":
        # Apenas dashboard
        run_dashboard_only()
    elif choice == "4":
        print("👋 Até logo!")
        return
    else:
        print("❌ Opção inválida")
        return

def run_collector_and_dashboard():
    """Executa coletor e depois dashboard"""
    print("\n📊 Executando coleta completa...")
    
    try:
        from scripts.integrated_collector import KintuadiIntegratedCollector
        collector = KintuadiIntegratedCollector()
        data = collector.collect_all()
        
        if data:
            print("\n✅ Coleta concluída! Iniciando dashboard...")
            run_streamlit()
        else:
            print("❌ Falha na coleta")
            
    except Exception as e:
        print(f"❌ Erro: {e}")

def run_collector_only():
    """Apenas coleta dados"""
    print("\n📥 Coletando dados...")
    
    try:
        from scripts.integrated_collector import KintuadiIntegratedCollector
        collector = KintuadiIntegratedCollector()
        data = collector.collect_all()
        
        if data:
            print("\n✅ Dados coletados e salvos em 'data/'")
            print("💡 Para visualizar: python -m streamlit run dashboard_integrado.py")
        else:
            print("❌ Falha na coleta")
            
    except Exception as e:
        print(f"❌ Erro: {e}")

def run_dashboard_only():
    """Apenas abre o dashboard"""
    print("\n📈 Abrindo dashboard...")
    run_streamlit()

def run_streamlit():
    """Executa o dashboard Streamlit"""
    print("\n🚀 Iniciando Kintuadi Energy Dashboard...")
    print("   Acesse: http://localhost:8501")
    print("   Pressione Ctrl+C para encerrar\n")
    
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "dashboard_integrado.py"],
            check=True
        )
    except KeyboardInterrupt:
        print("\n⏹️ Dashboard encerrado")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro: {e}")
        print("\n💡 Tente manualmente: python -m streamlit run dashboard_integrado.py")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")

if __name__ == "__main__":
    # Carrega variáveis de ambiente
    from dotenv import load_dotenv
    load_dotenv()
    
    main()