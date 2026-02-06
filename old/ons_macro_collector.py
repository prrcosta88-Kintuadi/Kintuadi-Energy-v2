# ons_macro_collector.py
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import time

class ONSMacroCollector:
    """Coleta dados macroeconômicos do ONS"""
    
    def __init__(self, authenticator):
        self.auth = authenticator
        self.base_url = "https://integra.ons.org.br/api"
        
    def get_system_load(self, days_back: int = 30):
        """
        Obtém dados de carga do sistema
        ENDPOINT HIPOTÉTICO - ajuste conforme API real
        """
        endpoint = f"{self.base_url}/carga/historico"
        
        try:
            headers = self.auth.get_auth_headers()
            
            # Calcula datas
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            params = {
                'dataInicial': start_date.strftime('%Y-%m-%d'),
                'dataFinal': end_date.strftime('%Y-%m-%d'),
                'formato': 'json'
            }
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                df = pd.DataFrame(data.get('dados', []))
                
                if not df.empty:
                    # Processa dados
                    if 'data' in df.columns:
                        df['data'] = pd.to_datetime(df['data'])
                    
                    if 'cargaMW' in df.columns:
                        df['cargaMW'] = pd.to_numeric(df['cargaMW'], errors='coerce')
                    
                    print(f"✅ {len(df)} registros de carga coletados")
                
                return df
                
        except Exception as e:
            print(f"⚠️ Erro ao coletar carga: {str(e)}")
        
        return pd.DataFrame()
    
    def get_generation_mix(self):
        """
        Obtém mix de geração atual
        ENDPOINT HIPOTÉTICO
        """
        endpoint = f"{self.base_url}/geracao/mix-atual"
        
        try:
            headers = self.auth.get_auth_headers()
            response = requests.get(endpoint, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extrai mix por fonte
                mix_data = {}
                for fonte in data.get('fontes', []):
                    nome = fonte.get('fonte')
                    percentual = fonte.get('percentual')
                    potencia = fonte.get('potenciaMW')
                    
                    if nome and percentual is not None:
                        mix_data[nome] = {
                            'percentual': percentual,
                            'potenciaMW': potencia,
                            'timestamp': datetime.now().isoformat()
                        }
                
                print(f"✅ Mix de geração: {len(mix_data)} fontes")
                return mix_data
                
        except Exception as e:
            print(f"⚠️ Erro ao coletar mix de geração: {str(e)}")
        
        return {}
    
    def get_interchange_data(self):
        """Obtém dados de intercâmbio entre subsistemas"""
        # ENDPOINT HIPOTÉTICO
        endpoint = f"{self.base_url}/intercambio/atual"
        
        try:
            headers = self.auth.get_auth_headers()
            response = requests.get(endpoint, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data
                
        except Exception as e:
            print(f"⚠️ Erro ao coletar intercâmbio: {str(e)}")
        
        return {}