#!/usr/bin/env python3
"""
Kintuadi Energy - Runner Principal
Coleta de dados + execução do dashboard Streamlit
"""

from __future__ import annotations

import os
import sys
import subprocess
import logging
from datetime import datetime
import glob
import json
from typing import Optional, Tuple

# Logging básico
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("kintuadi")


# =========================
# CONFIGURAÇÃO INICIAL
# =========================
def check_and_create_env() -> bool:
    """Verifica se .env existe, senão cria com credenciais do usuário."""
    
    env_path = ".env"
    env_example_path = ".env.example"
    
    # Se .env já existe, tudo ok
    if os.path.exists(env_path):
        print("✅ Arquivo .env encontrado.")
        return True
    
    print("\n" + "="*64)
    print("⚙️  CONFIGURAÇÃO INICIAL DO KINTUADI ENERGY")
    print("="*64)
    print("\nPara acessar dados do ONS, é necessário configurar suas credenciais.")
    print("\n📝 Você pode:")
    print("1. Criar arquivo .env manualmente (copie .env.example)")
    print("2. Configurar agora via terminal")
    
    choice = input("\nEscolha (1/2/3): ").strip()
    
    if choice == "1":
        # Copia .env.example para .env
        if os.path.exists(env_example_path):
            import shutil
            shutil.copy2(env_example_path, env_path)
            print(f"\n✅ Arquivo .env criado a partir de .env.example")
            print("📝 Edite o arquivo .env com suas credenciais ONS.")
            print("▶️  Execute o programa novamente.")
            return False
        else:
            print("❌ Arquivo .env.example não encontrado!")
            return create_env_via_terminal()
    
    elif choice == "2":
        return create_env_via_terminal()
    
    else:
        print("❌ Opção inválida.")
        return False


def create_env_via_terminal() -> bool:
    """Cria arquivo .env coletando credenciais via terminal."""
    
    print("\n" + "="*64)
    print("🔐 CONFIGURAÇÃO DE CREDENCIAIS ONS")
    print("="*64)
    print("\nPara acessar dados históricos do ONS, você precisa de:")
    print("1. Acesso ao SINTEGRE (https://sintegre.ons.org.br)")
    print("2. Credenciais de usuário cadastrado")
    
    print("\n⚠️  Suas credenciais serão salvas LOCALMENTE no arquivo .env")
    print("   Elas NUNCA serão enviadas para a internet.")
    
    email = input("\n📧 Email do ONS/SINTEGRE: ").strip()
    password = input("🔑 Senha: ").strip()
    
    if not email or not password:
        print("❌ Email e senha são obrigatórios!")
        return False
    
    # Lê template do .env.example se existir
    env_content = ""
    if os.path.exists(".env.example"):
        with open(".env.example", "r", encoding="utf-8") as f:
            env_content = f.read()
    else:
        # Template básico
        env_content = """# 🔐 CREDENCIAIS ONS
ONS_USERNAME={email}
ONS_PASSWORD={password}

# 🌐 URLs DAS APIS
ONS_PUBLIC_API_URL=https://integra.ons.org.br/api
CCEE_API_URL=https://dadosabertos.ccee.org.br/api/3/action

# 📁 DIRETÓRIOS
DATA_DIR=data
LOG_DIR=logs

# ⏱️ CACHE
CACHE_TTL_ONS=30
CACHE_TTL_CCEE=60

# 📊 LIMITES
MAX_RESERVATORIOS=100
MAX_PLD_RECORDS=500

# 📝 LOGGING
LOG_LEVEL=INFO
"""
    
    # Substitui credenciais
    env_content = env_content.replace("{email}", email)
    env_content = env_content.replace("{password}", password)
    
    # Salva .env
    with open(".env", "w", encoding="utf-8") as f:
        f.write(env_content)
    
    print("\n✅ Arquivo .env criado com sucesso!")
    print("🔒 Credenciais salvas localmente.")
    print("📁 Você pode editar manualmente o arquivo .env a qualquer momento.")
    
    return True


def create_env_with_gui() -> bool:
    """Cria .env usando interface gráfica (tkinter)."""
    try:
        import tkinter as tk
        from tkinter import messagebox, simpledialog
    except ImportError:
        print("⚠️  tkinter não disponível. Usando configuração via terminal.")
        return create_env_via_terminal()
    
    class CredentialsDialog:
        def __init__(self):
            self.credentials_saved = False
            self.root = tk.Tk()
            self.root.title("Kintuadi Energy - Configuração Inicial")
            self.root.geometry("500x350")
            self.root.configure(bg="#0f172a")
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            self.setup_ui()
            
        def setup_ui(self):
            # Título
            title = tk.Label(
                self.root, 
                text="🔐 Configuração de Credenciais ONS",
                font=("Arial", 14, "bold"),
                fg="#60a5fa",
                bg="#0f172a"
            )
            title.pack(pady=20)
            
            # Frame principal
            frame = tk.Frame(self.root, bg="#1e293b", padx=20, pady=20)
            frame.pack(padx=20, pady=10, fill="both", expand=True)
            
            # Instruções
            instructions = tk.Label(
                frame,
                text="Para acessar dados históricos do ONS, informe suas credenciais do SINTEGRE.\n\nSuas credenciais serão salvas apenas localmente no arquivo .env",
                font=("Arial", 10),
                fg="#cbd5e1",
                bg="#1e293b",
                justify="left"
            )
            instructions.pack(pady=(0, 20))
            
            # Email
            tk.Label(
                frame, 
                text="Email:", 
                font=("Arial", 10, "bold"),
                fg="#94a3b8",
                bg="#1e293b"
            ).pack(anchor="w")
            
            self.email_entry = tk.Entry(frame, font=("Arial", 10), width=40)
            self.email_entry.pack(pady=(0, 15))
            self.email_entry.focus_set()  # Foco no campo email
            
            # Senha
            tk.Label(
                frame, 
                text="Senha:", 
                font=("Arial", 10, "bold"),
                fg="#94a3b8",
                bg="#1e293b"
            ).pack(anchor="w")
            
            self.password_entry = tk.Entry(frame, font=("Arial", 10), width=40, show="*")
            self.password_entry.pack(pady=(0, 25))
            
            # Botão Salvar
            save_button = tk.Button(
                frame,
                text="✅ Salvar Credenciais",
                font=("Arial", 10, "bold"),
                bg="#3b82f6",
                fg="white",
                padx=20,
                pady=10,
                command=self.save_credentials
            )
            save_button.pack()
            
            # Botão Cancelar
            cancel_button = tk.Button(
                frame,
                text="❌ Cancelar",
                font=("Arial", 10),
                bg="#64748b",
                fg="white",
                padx=20,
                pady=5,
                command=self.on_cancel
            )
            cancel_button.pack(pady=10)
            
            # Link para cadastro
            link = tk.Label(
                self.root,
                text="📝 Não tem cadastro? Acesse: https://sintegre.ons.org.br/paginas/acesso.aspx",
                font=("Arial", 8),
                fg="#60a5fa",
                bg="#0f172a",
                cursor="hand2"
            )
            link.pack(pady=10)
            
            def open_link(event):
                import webbrowser
                webbrowser.open("https://sintegre.ons.org.br/paginas/acesso.aspx")
            
            link.bind("<Button-1>", open_link)
            
            # Bind Enter key to save
            self.root.bind('<Return>', lambda event: self.save_credentials())
        
        def save_credentials(self):
            email = self.email_entry.get().strip()
            password = self.password_entry.get().strip()
            
            if not email:
                messagebox.showerror("Erro", "Email é obrigatório!")
                self.email_entry.focus_set()
                return
            
            if not password:
                messagebox.showerror("Erro", "Senha é obrigatória!")
                self.password_entry.focus_set()
                return
            
            # Verifica se é email válido (básico)
            if "@" not in email or "." not in email:
                if not messagebox.askyesno("Confirmar", 
                    f"O email '{email}' parece inválido.\nDeseja continuar mesmo assim?"):
                    return
            
            # Cria .env
            env_content = f"""# 🔐 CREDENCIAIS ONS
ONS_USERNAME={email}
ONS_PASSWORD={password}

# 🌐 URLs DAS APIS
ONS_PUBLIC_API_URL=https://integra.ons.org.br/api
CCEE_API_URL=https://dadosabertos.ccee.org.br/api/3/action

# 📁 DIRETÓRIOS
DATA_DIR=data
LOG_DIR=logs

# ⏱️ CACHE
CACHE_TTL_ONS=30
CACHE_TTL_CCEE=60

# 📊 LIMITES
MAX_RESERVATORIOS=100
MAX_PLD_RECORDS=500

# 📝 LOGGING
LOG_LEVEL=INFO
"""
            
            try:
                with open(".env", "w", encoding="utf-8") as f:
                    f.write(env_content)
                
                messagebox.showinfo("Sucesso", 
                    "✅ Credenciais salvas com sucesso!\n\n"
                    "Elas foram armazenadas no arquivo .env\n"
                    "Você pode editar manualmente a qualquer momento.")
                
                self.credentials_saved = True
                self.root.destroy()  # Use destroy() em vez de quit()
                
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível salvar o arquivo .env:\n{str(e)}")
        
        def on_cancel(self):
            if messagebox.askyesno("Cancelar", "Deseja realmente cancelar a configuração?"):
                self.root.destroy()
        
        def on_closing(self):
            if messagebox.askyesno("Sair", "Deseja sair sem salvar as credenciais?"):
                self.root.destroy()
        
        def run(self):
            self.root.mainloop()
            return self.credentials_saved
    
    # Executa o diálogo
    dialog = CredentialsDialog()
    return dialog.run()

# =========================
# SETUP
# =========================
def setup_environment() -> None:
    """Configura diretórios e ambiente."""
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # Verifica e cria .env se necessário
    if not os.path.exists(".env"):
        print("\n🔍 Verificando configuração...")
        # Tenta GUI primeiro, depois terminal
        try:
            if not create_env_with_gui():
                check_and_create_env()
        except Exception as e:
            print(f"⚠️  Erro na interface gráfica: {e}")
            check_and_create_env()

    # Configuração mínima do Streamlit
    config_dir = os.path.join(os.path.expanduser("~"), ".streamlit")
    os.makedirs(config_dir, exist_ok=True)

    config_file = os.path.join(config_dir, "config.toml")
    if not os.path.exists(config_file):
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(
                """[browser]
gatherUsageStats = false

[server]
headless = true

[theme]
base = "dark"
"""
            )


def check_dependencies() -> bool:
    """Verifica dependências essenciais."""
    try:
        import streamlit  # noqa
        import pandas  # noqa
        import plotly  # noqa
        import requests  # noqa
        return True
    except ImportError as e:
        logger.error(f"Dependência ausente: {e}")
        return False


def print_banner() -> None:
    banner = f"""
╔{'═' * 64}╗
║{'KINTUADI ENERGY INTELLIGENCE':^64}║
╠{'═' * 64}╣
║{'Plataforma de Inteligência do Mercado de Energia':^64}║
║{datetime.now().strftime('%d/%m/%Y %H:%M:%S'):^64}║
╚{'═' * 64}╝
"""
    print(banner)


# =========================
# VERIFICAÇÃO DE CREDENCIAIS
# =========================
def check_ons_credentials() -> Tuple[bool, str]:
    """Verifica se as credenciais ONS estão configuradas."""
    from dotenv import load_dotenv
    load_dotenv()
    
    username = os.getenv("ONS_USERNAME")
    password = os.getenv("ONS_PASSWORD")
    
    if not username or not password:
        return False, "Credenciais ONS não configuradas no arquivo .env"
    
    # Verifica se são credenciais de exemplo
    if "seu_email@dominio.com" in username or "sua_senha" in password:
        return False, "Credenciais ONS não foram configuradas. Edite o arquivo .env"
    
    return True, "Credenciais ONS configuradas"


# =========================
# COLETA
# =========================
def run_collector_v2() -> bool:
    """Executa o coletor integrado v2."""
    try:
        # Verifica credenciais antes
        creds_ok, message = check_ons_credentials()
        if not creds_ok:
            print(f"\n⚠️  {message}")
            print("📊 Coletando apenas dados públicos da CCEE...")
        
        from scripts.integrated_collector_v2 import KintuadiIntegratedCollectorV2

        collector = KintuadiIntegratedCollectorV2()
        collector.quick_collect()
        return True

    except Exception as e:
        logger.error(f"Erro na coleta v2: {e}")
        return False


# =========================
# DASHBOARD
# =========================
def run_dashboard() -> None:
    """Inicia o dashboard Streamlit."""
    print("\n🌐 Dashboard disponível em: http://localhost:8501\n")

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "dashboard_integrado.py",
                "--server.headless=true",
            ],
            check=True,
        )
    except KeyboardInterrupt:
        print("\n⏹️ Dashboard encerrado")
    except Exception as e:
        print(f"\n❌ Erro ao iniciar dashboard: {e}")


# =========================
# CHECK SYSTEM
# =========================
def check_system() -> None:
    print("\n🔍 VERIFICAÇÃO DO SISTEMA")
    print("-" * 48)

    for d in ["data", "logs", "scripts"]:
        print(f"{'✅' if os.path.exists(d) else '❌'} {d}/")

    for f in ["dashboard_integrado.py", "run_collector.py", ".env"]:
        print(f"{'✅' if os.path.exists(f) else '❌'} {f}")
    
    # Verifica credenciais ONS
    creds_ok, message = check_ons_credentials()
    print(f"{'✅' if creds_ok else '⚠️ '} {message}")

    files = glob.glob("data/kintuadi_*.json")
    if files:
        latest = max(files, key=os.path.getmtime)
        print(f"📊 Último dado coletado: {os.path.basename(latest)}")
    else:
        print("⚠️ Nenhum dado coletado encontrado")

    print("-" * 48)


# =========================
# MAIN
# =========================
def main() -> None:
    setup_environment()

    if not check_dependencies():
        print("\nInstale as dependências com:")
        print("pip install -r requirements.txt")
        return

    print_banner()
    
    # Mostra status das credenciais
    creds_ok, message = check_ons_credentials()
    if not creds_ok:
        print(f"\n⚠️  {message}")
        print("💡 Use a opção 5 para verificar configuração.")

    while True:
        print("\n" + "=" * 64)
        print("MENU PRINCIPAL")
        print("=" * 64)
        print("1. Coletar dados + Dashboard")
        print("2. Apenas coletar dados")
        print("3. Apenas abrir dashboard")
        print("4. Coleta rápida (teste)")
        print("5. Verificar sistema")
        print("6. Configurar credenciais ONS")
        print("7. Sair")

        choice = input("\nEscolha (1-7): ").strip()

        if choice == "1":
            if run_collector_v2():
                run_dashboard()

        elif choice == "2":
            run_collector_v2()

        elif choice == "3":
            run_dashboard()

        elif choice == "4":
            run_collector_v2()

        elif choice == "5":
            check_system()

        elif choice == "6":
            print("\n⚙️  Configuração de Credenciais ONS")
            print("=" * 48)
            print("1. Configurar via interface gráfica")
            print("2. Configurar via terminal")
            print("3. Voltar")
            
            config_choice = input("\nEscolha (1/2/3): ").strip()
            
            if config_choice == "1":
                create_env_with_gui()
            elif config_choice == "2":
                create_env_via_terminal()
            elif config_choice == "3":
                continue
            else:
                print("❌ Opção inválida.")

        elif choice == "7":
            print("\n👋 Encerrando.")
            break

        else:
            print("❌ Opção inválida.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ Execução interrompida pelo usuário")