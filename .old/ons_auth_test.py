# test_ons_simplificado.py
import requests
import json
from datetime import datetime
import os

def test_api_reservatorios_simples():
    """Teste simples e direto da API de reservatórios"""
    
    print("🧪 TESTE SIMPLIFICADO - API ONS RESERVATÓRIOS")
    print("=" * 60)
    
    # URL da API
    url = "https://integra.ons.org.br/api/energiaagora/Get/SituacaoDosReservatorios"
    
    print(f"URL: {url}")
    
    try:
        # Faz a requisição
        response = requests.get(url, timeout=30)
        
        print(f"Status: {response.status_code}")
        print(f"Tempo de resposta: {response.elapsed.total_seconds():.2f}s")
        
        if response.status_code == 200:
            # Tenta parsear como JSON
            data = response.json()
            
            if isinstance(data, list):
                print(f"✅ Sucesso! {len(data)} reservatórios encontrados")
                
                # Analisa estrutura
                if len(data) > 0:
                    primeiro = data[0]
                    print(f"\n📋 ESTRUTURA DO PRIMEIRO REGISTRO:")
                    print(f"   • Data: {primeiro.get('Data', 'N/A')}")
                    print(f"   • Subsistema: {primeiro.get('Subsistema', 'N/A')}")
                    print(f"   • Reservatório: {primeiro.get('Reservatorio', 'N/A')}")
                    print(f"   • Volume útil: {primeiro.get('ReservatorioPorcentagem', 'N/A')}%")
                    print(f"   • Energia armazenada: {primeiro.get('ReservatorioEARVerificadaMWMes', 'N/A')} MW")
                
                # Analisa por subsistema
                subsistemas = {}
                for item in data:
                    subsis = item.get('Subsistema', 'Desconhecido')
                    if subsis not in subsistemas:
                        subsistemas[subsis] = []
                    subsistemas[subsis].append(item)
                
                print(f"\n📊 DISTRIBUIÇÃO POR SUBMERCADO:")
                for subsis, items in subsistemas.items():
                    print(f"   • {subsis}: {len(items)} reservatórios")
                
                # Salva dados
                salvar_dados(data, "reservatorios_ons")
                
                # Calcula estatísticas
                calcular_estatisticas(data)
                
                return True
            else:
                print(f"⚠️ Resposta não é uma lista: {type(data)}")
                print(f"Conteúdo: {json.dumps(data, indent=2)[:500]}...")
                return False
                
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            print(f"Mensagem: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na requisição: {str(e)}")
        return False

def salvar_dados(data, nome_base):
    """Salva dados em arquivos"""
    os.makedirs("data", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Salva JSON completo
    json_filename = f"data/{nome_base}_{timestamp}.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 JSON salvo: {json_filename}")
    
    # Cria resumo
    criar_resumo(data, nome_base, timestamp)

def criar_resumo(data, nome_base, timestamp):
    """Cria um resumo dos dados"""
    if not data:
        return
    
    resumo = {
        "data_coleta": datetime.now().isoformat(),
        "total_reservatorios": len(data),
        "subsistemas": {},
        "estatisticas": {}
    }
    
    # Agrupa por subsistema
    subsistemas = {}
    volumes = []
    
    for item in data:
        subsis = item.get('Subsistema', 'Desconhecido')
        volume = item.get('ReservatorioPorcentagem', 0)
        
        if subsis not in subsistemas:
            subsistemas[subsis] = {
                "count": 0,
                "volumes": []
            }
        
        subsistemas[subsis]["count"] += 1
        subsistemas[subsis]["volumes"].append(volume)
        volumes.append(volume)
    
    # Calcula estatísticas por subsistema
    for subsis, info in subsistemas.items():
        if info["volumes"]:
            resumo["subsistemas"][subsis] = {
                "quantidade": info["count"],
                "volume_medio": sum(info["volumes"]) / len(info["volumes"]),
                "volume_min": min(info["volumes"]),
                "volume_max": max(info["volumes"])
            }
    
    # Estatísticas gerais
    if volumes:
        resumo["estatisticas"] = {
            "volume_medio_geral": sum(volumes) / len(volumes),
            "volume_min_geral": min(volumes),
            "volume_max_geral": max(volumes),
            "status_sistema": "NORMAL"
        }
        
        # Define status baseado no volume médio
        volume_medio = resumo["estatisticas"]["volume_medio_geral"]
        if volume_medio < 40:
            resumo["estatisticas"]["status_sistema"] = "CRÍTICO"
        elif volume_medio < 60:
            resumo["estatisticas"]["status_sistema"] = "ALERTA"
        elif volume_medio < 80:
            resumo["estatisticas"]["status_sistema"] = "ATENÇÃO"
    
    # Salva resumo
    resumo_filename = f"data/{nome_base}_resumo_{timestamp}.json"
    with open(resumo_filename, 'w', encoding='utf-8') as f:
        json.dump(resumo, f, ensure_ascii=False, indent=2)
    
    print(f"📊 Resumo salvo: {resumo_filename}")
    
    # Imprime resumo
    print(f"\n📈 RESUMO DA COLETA:")
    print(f"   • Total reservatórios: {resumo['total_reservatorios']}")
    print(f"   • Volume médio geral: {resumo['estatisticas'].get('volume_medio_geral', 0):.1f}%")
    print(f"   • Status do sistema: {resumo['estatisticas'].get('status_sistema', 'N/A')}")
    
    print(f"\n📊 POR SUBMERCADO:")
    for subsis, info in resumo["subsistemas"].items():
        print(f"   • {subsis}: {info['quantidade']} reservatórios, Volume médio: {info['volume_medio']:.1f}%")

def calcular_estatisticas(data):
    """Calcula estatísticas detalhadas"""
    if not data:
        return
    
    print(f"\n📊 ESTATÍSTICAS DETALHADAS:")
    
    # Top 10 reservatórios mais críticos
    reservatorios_ordenados = sorted(data, key=lambda x: x.get('ReservatorioPorcentagem', 100))
    
    print(f"\n⚠️ TOP 10 RESERVATÓRIOS MAIS CRÍTICOS:")
    for i, res in enumerate(reservatorios_ordenados[:10], 1):
        print(f"   {i:2d}. {res.get('Reservatorio', 'N/A')[:30]:30} - {res.get('ReservatorioPorcentagem', 0):6.1f}% ({res.get('Subsistema', 'N/A')})")
    
    # Top 10 reservatórios mais cheios
    reservatorios_ordenados_rev = sorted(data, key=lambda x: x.get('ReservatorioPorcentagem', 0), reverse=True)
    
    print(f"\n💧 TOP 10 RESERVATÓRIOS MAIS CHEIOS:")
    for i, res in enumerate(reservatorios_ordenados_rev[:10], 1):
        print(f"   {i:2d}. {res.get('Reservatorio', 'N/A')[:30]:30} - {res.get('ReservatorioPorcentagem', 0):6.1f}% ({res.get('Subsistema', 'N/A')})")

def main():
    """Função principal"""
    print("🚀 KINTUADI ENERGY - TESTE SIMPLIFICADO ONS")
    print("=" * 60)
    
    # Testa a API
    sucesso = test_api_reservatorios_simples()
    
    if sucesso:
        print("\n" + "=" * 60)
        print("✅ TESTE CONCLUÍDO COM SUCESSO!")
        print("=" * 60)
        print("\n📁 Dados salvos na pasta 'data/'")
        print("💡 Use estes dados para construir seu dashboard")
    else:
        print("\n" + "=" * 60)
        print("❌ TESTE FALHOU")
        print("=" * 60)

if __name__ == "__main__":
    main()