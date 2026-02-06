# test_data_load.py
import json
import os
import glob

print("🔍 TESTANDO CARREGAMENTO DE DADOS")
print("="*50)

# Verifica se existe a pasta data
if not os.path.exists("data"):
    print("❌ Pasta 'data' não existe!")
    exit()

# Lista arquivos JSON
json_files = glob.glob("data/*.json")
print(f"📁 Arquivos JSON encontrados: {len(json_files)}")

if not json_files:
    print("❌ Nenhum arquivo JSON encontrado na pasta 'data/'")
    print("💡 Execute primeiro: python run_collector.py (opção 2)")
    exit()

# Encontra o arquivo mais recente
latest_file = max(json_files, key=os.path.getmtime)
print(f"📊 Arquivo mais recente: {os.path.basename(latest_file)}")

# Tenta carregar
try:
    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("✅ Arquivo carregado com sucesso!")
    
    # Mostra estrutura
    print("\n📋 ESTRUTURA DO ARQUIVO:")
    print(f"  • Keys principais: {list(data.keys())}")
    
    # Verifica dados ONS
    if 'ons' in data:
        ons = data['ons']
        print(f"\n💧 DADOS ONS:")
        print(f"  • Volume médio: {ons.get('statistics', {}).get('geral', {}).get('volume_medio', 'N/A')}%")
        print(f"  • Status: {ons.get('statistics', {}).get('geral', {}).get('status_sistema', 'N/A')}")
    
    # Verifica dados CCEE
    if 'ccee' in data:
        ccee = data['ccee']
        print(f"\n💰 DADOS CCEE:")
        print(f"  • PLD médio: R$ {ccee.get('statistics', {}).get('geral', {}).get('pld_medio', 'N/A')}/MWh")
        print(f"  • Registros: {ccee.get('statistics', {}).get('geral', {}).get('quantidade', 'N/A')}")
    
    # Verifica análise
    if 'analysis' in data:
        analysis = data['analysis']
        print(f"\n📈 ANÁLISE:")
        print(f"  • Tendência: {analysis.get('tendencia_mercado', 'N/A')}")
        print(f"  • Índice segurança: {analysis.get('indice_seguranca', 'N/A')}")
    
except Exception as e:
    print(f"❌ Erro ao carregar arquivo: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*50)
print("🎯 PRÓXIMOS PASSOS:")
print("1. Se os dados aparecerem acima, o problema é no dashboard")
print("2. Se não aparecerem, execute o coletor novamente")