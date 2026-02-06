# test_ons_api.py
import os
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

def test_ons_api_direct():
    """Testa a API do ONS Volume Util diretamente"""
    
    print("🔍 TESTE DIRETO DA API ONS VOLUME UTIL")
    print("="*60)
    
    # Credenciais
    username = os.getenv('ONS_USERNAME')
    password = os.getenv('ONS_PASSWORD')
    
    if not username or not password:
        print("❌ Credenciais ONS não configuradas")
        return
    
    print(f"👤 Usuário: {username}")
    
    # 1. Autenticação
    print("\n1. 🔐 Testando autenticação...")
    
    auth_url = "https://integra.ons.org.br/api/autenticar"
    auth_payload = {
        "usuario": username,
        "senha": password
    }
    
    auth_headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        import requests
        
        auth_response = requests.post(auth_url, json=auth_payload, headers=auth_headers, timeout=30)
        
        if auth_response.status_code == 200:
            auth_data = auth_response.json()
            token = auth_data.get("access_token")
            token_type = auth_data.get("token_type", "bearer")
            
            print(f"✅ Autenticação bem-sucedida!")
            print(f"   Token type: {token_type}")
            print(f"   Expira em: {auth_data.get('expires_in', 'N/A')} segundos")
            print(f"   Token (início): {token[:50]}..." if token else "   Token: N/A")
        else:
            print(f"❌ Falha na autenticação: HTTP {auth_response.status_code}")
            print(f"   Resposta: {auth_response.text[:200]}")
            return
        
    except Exception as e:
        print(f"❌ Erro na autenticação: {e}")
        return
    
    # 2. Listar reservatórios
    print("\n2. 📋 Testando listagem de reservatórios...")
    
    reservatorios_url = "https://integra.ons.org.br/api/hidrologia/reservatorios"
    
    headers = {
        "Authorization": f"{token_type.capitalize()} {token}",
        "accept": "application/json",
        "Content-Type": "application/json",
        "Pagina": "1",
        "Quantidade": "50"  # Limita para teste
    }
    
    try:
        res_response = requests.get(reservatorios_url, headers=headers, timeout=30)
        
        if res_response.status_code == 200:
            res_data = res_response.json()
            
            if isinstance(res_data, list):
                print(f"✅ {len(res_data)} reservatórios encontrados")
                
                # Mostra alguns exemplos
                print("\n   📝 Exemplos:")
                for i, res in enumerate(res_data[:5]):
                    print(f"   {i+1}. ID: {res.get('id', 'N/A')}, Nome: {res.get('nome', 'N/A')}")
                
                # Salva para análise
                with open("test_reservatorios.json", "w", encoding="utf-8") as f:
                    json.dump(res_data[:10], f, indent=2, ensure_ascii=False)
                print(f"   💾 Salvo em: test_reservatorios.json")
                
            elif isinstance(res_data, dict):
                print(f"✅ Resposta em formato dicionário")
                print(f"   Keys: {list(res_data.keys())}")
                
                # Procura por lista de reservatórios
                for key in ['data', 'result', 'reservatorios']:
                    if key in res_data and isinstance(res_data[key], list):
                        print(f"   Reservatórios em '{key}': {len(res_data[key])}")
                        break
            else:
                print(f"⚠️ Formato inesperado: {type(res_data)}")
                
        else:
            print(f"❌ Erro na listagem: HTTP {res_response.status_code}")
            print(f"   Resposta: {res_response.text[:200]}")
    
    except Exception as e:
        print(f"❌ Erro na listagem: {e}")
    
    # 3. Testar volume útil histórico
    print("\n3. 📊 Testando volume útil histórico...")
    
    # Usa o ID do seu exemplo (10)
    reservatorio_id = "10"
    
    # Calcula datas (últimos 3 dias)
    fim = datetime.now()
    inicio = fim - timedelta(days=3)
    
    volume_url = f"https://integra.ons.org.br/api/hidrologia/reservatorios/{reservatorio_id}/volumeUtil"
    
    params = {
        'Inicio': inicio.strftime('%Y-%m-%d %H:%M:%S'),
        'Fim': fim.strftime('%Y-%m-%d %H:%M:%S'),
        'Intervalo': 'DI',  # Diário
        'Origem': 'ATR'
    }
    
    # Adiciona headers de paginação
    volume_headers = headers.copy()
    volume_headers["Pagina"] = "1"
    volume_headers["Quantidade"] = "240"
    
    try:
        vol_response = requests.get(volume_url, headers=volume_headers, params=params, timeout=30)
        
        if vol_response.status_code == 200:
            vol_data = vol_response.json()
            
            print(f"✅ Dados históricos obtidos!")
            print(f"   Tipo de resposta: {type(vol_data)}")
            
            if isinstance(vol_data, list):
                print(f"   Total de registros: {len(vol_data)}")
                
                if vol_data:
                    print(f"\n   📅 Primeiros registros:")
                    for i, registro in enumerate(vol_data[:3]):
                        if isinstance(registro, dict):
                            print(f"   {i+1}. {registro.get('dataHora', 'N/A')}: {registro.get('volumeUtil', 'N/A')}%")
                        else:
                            print(f"   {i+1}. {registro}")
                
                # Salva para análise
                with open("test_volume_data.json", "w", encoding="utf-8") as f:
                    json.dump(vol_data, f, indent=2, ensure_ascii=False, default=str)
                print(f"   💾 Salvo em: test_volume_data.json")
                
            elif isinstance(vol_data, dict):
                print(f"   Formato dicionário - Keys: {list(vol_data.keys())}")
                
                # Tenta encontrar dados
                for key in ['data', 'result', 'volumeUtil']:
                    if key in vol_data:
                        print(f"   Dados em '{key}': {type(vol_data[key])}")
                        if isinstance(vol_data[key], list):
                            print(f"   Itens: {len(vol_data[key])}")
                            if vol_data[key]:
                                print(f"   Exemplo: {vol_data[key][0]}")
            else:
                print(f"   Resposta: {vol_data}")
                
        else:
            print(f"❌ Erro no volume histórico: HTTP {vol_response.status_code}")
            print(f"   Resposta: {vol_response.text[:200]}")
    
    except Exception as e:
        print(f"❌ Erro no volume histórico: {e}")
    
    print("\n" + "="*60)
    print("🎯 PRÓXIMOS PASSOS:")
    print("1. Analise os arquivos gerados:")
    print("   - test_reservatorios.json")
    print("   - test_volume_data.json")
    print("2. Execute: python scripts/ons_volume_util.py")
    print("3. Integre ao coletor principal se funcionar")

if __name__ == "__main__":
    test_ons_api_direct()