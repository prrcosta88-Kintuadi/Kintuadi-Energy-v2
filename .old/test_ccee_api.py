# scripts/test_ccee_apis.py
import requests
import json
import pandas as pd
from datetime import datetime
import logging
import traceback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CCEEApiTester:
    """Testador específico para as APIs da CCEE que estão falhando"""
    
    def __init__(self):
        self.base_url = "https://dadosabertos.ccee.org.br/api/3/action"
        
        # IDs das APIs baseado no seu código
        self.resource_ids = {
            "contabilizacao_montante_perfil_agente": "76d1cf4c-da8c-47a5-9f0d-8b50079be960",
            "sumario_balanco_energetico_horario": "9418da65-0f9f-4f66-a43f-6517db9653f3", 
            "sumario_distribuicao_mensal": "9e8e3f5f-58a8-4744-b6da-7309a4513fcb"
        }
    
    def test_all_apis(self):
        """Testa todas as APIs da CCEE"""
        print("🔍 TESTANDO APIS DA CCEE 🔍")
        print("=" * 60)
        
        results = {}
        
        for api_name, resource_id in self.resource_ids.items():
            print(f"\n📡 Testando: {api_name}")
            print(f"   Resource ID: {resource_id}")
            
            # Teste 1: API JSON
            api_result = self.test_api_json(api_name, resource_id)
            results[f"{api_name}_json"] = api_result
            
            # Teste 2: Resource Show (para obter URL CSV)
            show_result = self.test_resource_show(api_name, resource_id)
            results[f"{api_name}_show"] = show_result
            
            # Teste 3: Tentativa CSV (se houver URL)
            if show_result.get("success") and show_result.get("csv_url"):
                csv_result = self.test_csv(api_name, show_result["csv_url"])
                results[f"{api_name}_csv"] = csv_result
            
            print("-" * 40)
        
        # Relatório consolidado
        self.print_summary(results)
        
        return results
    
    def test_api_json(self, api_name: str, resource_id: str):
        """Testa a API JSON padrão"""
        try:
            url = f"{self.base_url}/datastore_search"
            params = {"resource_id": resource_id, "limit": 2}
            
            print(f"   📊 JSON API: {url}")
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("success", False):
                print(f"   ❌ Sucesso=False na resposta")
                return {"success": False, "error": "API retornou success=False", "data": data}
            
            result = data.get("result", {})
            records = result.get("records", [])
            
            print(f"   ✅ Status: {response.status_code}")
            print(f"   📋 Total: {result.get('total', 'N/A')} registros")
            print(f"   📄 Amostra: {len(records)} registros retornados")
            
            if records:
                print(f"   📅 Primeiro registro - MES_REFERENCIA: {records[0].get('MES_REFERENCIA', 'N/A')}")
            
            return {
                "success": True,
                "status_code": response.status_code,
                "total": result.get("total"),
                "sample_count": len(records),
                "first_record": records[0] if records else None
            }
            
        except requests.exceptions.Timeout:
            print(f"   ⏰ TIMEOUT: A API demorou muito para responder")
            return {"success": False, "error": "Timeout"}
        except requests.exceptions.ConnectionError:
            print(f"   🔌 CONNECTION ERROR: Não foi possível conectar")
            return {"success": False, "error": "Connection Error"}
        except requests.exceptions.HTTPError as e:
            print(f"   🌐 HTTP ERROR: {e}")
            return {"success": False, "error": f"HTTP Error: {e}", "status_code": e.response.status_code if hasattr(e, 'response') else None}
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
            return {"success": False, "error": str(e)}
    
    def test_resource_show(self, api_name: str, resource_id: str):
        """Testa resource_show para obter metadados e URL CSV"""
        try:
            url = f"{self.base_url}/resource_show"
            params = {"id": resource_id}
            
            print(f"   🔍 Resource Show: {url}")
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("success", False):
                print(f"   ❌ Resource show retornou success=False")
                return {"success": False, "error": "Resource show failed"}
            
            resource = data.get("result", {})
            
            # Extrai informações importantes
            csv_url = resource.get("url", "")
            name = resource.get("name", "")
            format_type = resource.get("format", "").upper()
            
            print(f"   ✅ Resource encontrado: {name[:50]}..." if len(name) > 50 else name)
            print(f"   📄 Formato: {format_type}")
            
            if csv_url:
                print(f"   🔗 URL: {csv_url[:80]}..." if len(csv_url) > 80 else csv_url)
            else:
                print(f"   ⚠️  URL não encontrada nos metadados")
            
            # Verifica formatos disponíveis
            resource_formats = []
            if "url" in resource and resource["url"]:
                resource_formats.append("CSV")
            
            # Verifica se tem datastore
            if "datastore_active" in resource and resource["datastore_active"]:
                resource_formats.append("API/JSON")
            
            print(f"   📊 Formatos disponíveis: {', '.join(resource_formats) if resource_formats else 'Nenhum'}")
            
            return {
                "success": True,
                "name": name,
                "format": format_type,
                "csv_url": csv_url,
                "formats_available": resource_formats,
                "datastore_active": resource.get("datastore_active", False),
                "full_resource": resource  # Para debug
            }
            
        except Exception as e:
            print(f"   ❌ ERRO Resource Show: {e}")
            return {"success": False, "error": str(e)}
    
    def test_csv(self, api_name: str, csv_url: str):
        """Testa o download do CSV"""
        try:
            print(f"   📥 Testando CSV: {csv_url[:80]}..." if len(csv_url) > 80 else csv_url)
            
            # Tenta ler apenas os primeiros bytes para verificar
            head_response = requests.head(csv_url, timeout=10, allow_redirects=True)
            
            print(f"   📏 Tamanho: {head_response.headers.get('Content-Length', 'Desconhecido')} bytes")
            print(f"   📋 Tipo: {head_response.headers.get('Content-Type', 'Desconhecido')}")
            
            # Se for CSV, tenta ler algumas linhas
            if 'csv' in head_response.headers.get('Content-Type', '').lower():
                print(f"   🧪 Tentando ler CSV com pandas...")
                
                # Tenta com diferentes encodings
                encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']
                df = None
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(csv_url, nrows=5, encoding=encoding, on_bad_lines='skip')
                        print(f"   ✅ CSV lido com encoding: {encoding}")
                        print(f"   📊 Colunas: {list(df.columns)}")
                        print(f"   📈 Linhas lidas: {len(df)}")
                        
                        return {
                            "success": True,
                            "encoding": encoding,
                            "columns": list(df.columns),
                            "sample_rows": len(df),
                            "sample_data": df.head(2).to_dict('records')
                        }
                        
                    except Exception as e:
                        print(f"   ⚠️  Encoding {encoding} falhou: {e}")
                        continue
                
                if df is None:
                    print(f"   ❌ Todos os encodings falharam")
                    return {"success": False, "error": "Não foi possível ler CSV com nenhum encoding"}
                    
            else:
                print(f"   ⚠️  URL não parece ser CSV: {head_response.headers.get('Content-Type')}")
                
                # Tenta fazer download parcial para ver o conteúdo
                response = requests.get(csv_url, timeout=15, stream=True)
                first_bytes = response.raw.read(200)
                
                print(f"   🔍 Primeiros bytes: {first_bytes[:100]}...")
                
                return {
                    "success": False,
                    "error": f"Content-Type não é CSV: {head_response.headers.get('Content-Type')}",
                    "content_type": head_response.headers.get('Content-Type'),
                    "first_bytes": str(first_bytes[:100])
                }
                
        except Exception as e:
            print(f"   ❌ ERRO CSV: {e}")
            return {"success": False, "error": str(e)}
    
    def print_summary(self, results):
        """Imprime resumo dos testes"""
        print("\n" + "=" * 60)
        print("📋 RESUMO DOS TESTES")
        print("=" * 60)
        
        json_success = 0
        csv_success = 0
        total_apis = len(self.resource_ids)
        
        for api_name in self.resource_ids.keys():
            json_key = f"{api_name}_json"
            csv_key = f"{api_name}_csv"
            
            json_result = results.get(json_key, {})
            csv_result = results.get(csv_key, {})
            
            if json_result.get("success"):
                json_success += 1
            
            if csv_result.get("success"):
                csv_success += 1
        
        print(f"\n📊 ESTATÍSTICAS:")
        print(f"   • APIs testadas: {total_apis}")
        print(f"   • APIs JSON funcionando: {json_success}/{total_apis}")
        print(f"   • CSVs funcionando: {csv_success}/{total_apis}")
        
        print(f"\n🔧 RECOMENDAÇÕES:")
        if csv_success < total_apis:
            print(f"   ⚠️  Algumas APIs podem não ter CSV disponível")
            print(f"   💡 Sugestão: Use apenas a API JSON no código principal")
        
        print("\n📁 Para usar apenas JSON, modifique o código:")
        print("""
No método `collect_open_data_csv`, substitua a chamada para `_fetch_dataset_csv`
por `_fetch_dataset` para usar apenas JSON:

# Em ccee_collector_v2.py, modifique:
def collect_open_data_csv(self, limit: int = 500) -> Dict[str, Dict[str, Any]]:
    \"\"\"Coleta datasets adicionais via API JSON (sem CSV)\"\"\"
    datasets = {}
    for name, resource_id in self._additional_datasets.items():
        # Use JSON em vez de tentar CSV
        datasets[name] = self._fetch_dataset(resource_id, limit=limit)
    return datasets
        """)
    
    def generate_workaround_code(self):
        """Gera código para contornar o problema do CSV"""
        print("\n" + "=" * 60)
        print("💻 CÓDIGO DE CONTORNO")
        print("=" * 60)
        
        code = '''
# Adicione este método à classe CCEEPLDCollector:

def collect_open_data_json_only(self, limit: int = 500) -> Dict[str, Dict[str, Any]]:
    """Coleta datasets adicionais via API JSON (alternativa ao CSV)"""
    datasets = {}
    
    for name, resource_id in self._additional_datasets.items():
        try:
            print(f"Coletando {name} via API JSON...")
            
            # Usa a API JSON diretamente
            result = self._fetch_dataset(resource_id, limit=limit)
            
            # Adiciona metadados
            datasets[name] = {
                "source": "CCEE_API_JSON",
                "resource_id": resource_id,
                "success": result.get("success", False),
                "records": result.get("records", []),
                "total": result.get("total"),
                "sample_size": len(result.get("records", [])),
                "collection_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erro ao coletar {name}: {e}")
            datasets[name] = {
                "source": "CCEE_API_JSON",
                "resource_id": resource_id,
                "success": False,
                "error": str(e),
                "records": []
            }
    
    return datasets

# No coletor integrado, substitua:
# ons_results["open_data_csv"] = self.ons_collector.collect_open_data_csv(limit=500)
# ccee_results["open_data_csv"] = self.ccee_collector.collect_open_data_csv(limit=500)

# Por:
ons_results["open_data_json"] = self.ons_collector.collect_open_data_json_only(limit=500)
ccee_results["open_data_json"] = self.ccee_collector.collect_open_data_json_only(limit=500)
        '''
        
        print(code)

def main():
    """Função principal"""
    print("🚀 Iniciando testes das APIs da CCEE")
    print("ℹ️  Verificando APIs que estão falhando no coletor principal")
    
    tester = CCEEApiTester()
    
    try:
        results = tester.test_all_apis()
        
        # Salva resultados para análise
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f"ccee_api_test_{timestamp}.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n💾 Resultados salvos em: ccee_api_test_{timestamp}.json")
        
        # Gera sugestão de código
        tester.generate_workaround_code()
        
        print("\n✅ Testes concluídos!")
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Teste interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro durante os testes: {e}")
        print(traceback.format_exc())

if __name__ == "__main__":
    main()