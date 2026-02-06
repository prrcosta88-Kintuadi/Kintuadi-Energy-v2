# test_credentials.py
import os
import sys

# Adiciona o diretório atual ao path
sys.path.append('.')

def test_credentials():
    """Testa as credenciais configuradas"""
    
    print("🔐 TESTE DE CREDENCIAIS KINTUADI")
    print("="*50)
    
    # Verifica se .env existe
    if not os.path.exists('.env'):
        print("❌ Arquivo .env não encontrado")
        print("💡 Execute: python setup_env.py")
        return
    
    # Carrega variáveis do .env manualmente
    env_vars = {}
    with open('.env', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    print("📋 VARIÁVEIS CARREGADAS:")
    for key in ['ONS_USERNAME', 'ONS_PASSWORD', 'ONS_PUBLIC_API_URL', 'CCEE_API_URL']:
        value = env_vars.get(key, 'NÃO CONFIGURADO')
        masked = value if key != 'ONS_PASSWORD' else '*****' if value else 'NÃO CONFIGURADO'
        print(f"  {key}: {masked}")
    
    # Testa se credenciais ONS estão configuradas
    username = env_vars.get('ONS_USERNAME', '')
    password = env_vars.get('ONS_PASSWORD', '')
    
    if not username or username == 'SEU_EMAIL_AQUI':
        print("\n⚠️  Credencial ONS_USERNAME não configurada corretamente")
        print("   Edite o arquivo .env com seu email do ONS")
    
    if not password or password == 'SUA_SENHA_AQUI':
        print("⚠️  Credencial ONS_PASSWORD não configurada corretamente")
        print("   Edite o arquivo .env com sua senha do ONS")
    
    if username and username != 'SEU_EMAIL_AQUI' and password and password != 'SUA_SENHA_AQUI':
        print("\n✅ Credenciais ONS configuradas")
        print("🎯 Execute: python test_ons_volume_api.py")
    else:
        print("\n❌ Credenciais ONS não configuradas corretamente")
        print("💡 Edite o arquivo .env com suas credenciais reais")
    
    # Testa APIs públicas
    print("\n🌐 TESTANDO APIS PÚBLICAS...")
    
    try:
        import requests
        
        # Testa API pública do ONS
        print("\n1. Testando API pública ONS...")
        ons_url = env_vars.get('ONS_PUBLIC_API_URL', '') + "/energiaagora/Get/SituacaoDosReservatorios"
        
        if ons_url:
            try:
                response = requests.get(ons_url, headers={"accept": "application/json"}, timeout=10)
                if response.status_code == 200:
                    print(f"   ✅ ONS Pública: OK (Status: {response.status_code})")
                else:
                    print(f"   ⚠️  ONS Pública: HTTP {response.status_code}")
            except Exception as e:
                print(f"   ❌ ONS Pública: Erro - {e}")
        
        # Testa API pública da CCEE
        print("\n2. Testando API pública CCEE...")
        ccee_url = env_vars.get('CCEE_API_URL', '') + "/datastore_search"
        ccee_params = {
            "resource_id": "3f279d6b-1069-42f7-9b0a-217b084729c4",
            "limit": 1
        }
        
        if ccee_url:
            try:
                response = requests.get(ccee_url, params=ccee_params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        print(f"   ✅ CCEE Pública: OK (Success: True)")
                    else:
                        print(f"   ⚠️  CCEE Pública: Success=False")
                else:
                    print(f"   ⚠️  CCEE Pública: HTTP {response.status_code}")
            except Exception as e:
                print(f"   ❌ CCEE Pública: Erro - {e}")
    
    except ImportError:
        print("   ⚠️  Biblioteca 'requests' não instalada")
        print("   💡 Execute: pip install requests")
    
    print("\n" + "="*50)
    print("🎯 RESUMO:")
    print("1. Edite .env com credenciais reais se necessário")
    print("2. Teste: python test_ons_volume_api.py")
    print("3. Execute: python run_collector.py")

if __name__ == "__main__":
    test_credentials()