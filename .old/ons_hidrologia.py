# ons_hidrologia.py
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
from typing import List, Dict, Any, Optional
import time

class ONSHidrologiaCollector:
    """Coleta dados hidrológicos do ONS"""
    
    def __init__(self, authenticator):
        self.auth = authenticator
        self.base_url = "https://integra.ons.org.br/api/hidrologia"
        
    def get_reservoirs_list(self) -> List[Dict]:
        """Obtém lista de todos os reservatórios"""
        endpoint = f"{self.base_url}/reservatorios"
        
        try:
            headers = self.auth.get_auth_headers()
            if not headers:
                print("❌ Não foi possível autenticar")
                return []
            
            print("🔍 Obtendo lista de reservatórios...")
            response = requests.get(endpoint, headers=headers, timeout=30)
            response.raise_for_status()
            
            reservoirs = response.json()
            print(f"✅ {len(reservoirs)} reservatórios encontrados")
            
            return reservoirs
            
        except Exception as e:
            print(f"❌ Erro ao obter lista de reservatórios: {str(e)}")
            return []
    
    def get_reservoir_details(self, reservoir_id: str) -> Dict:
        """Obtém detalhes de um reservatório específico"""
        endpoint = f"{self.base_url}/reservatorios/{reservoir_id}"
        
        try:
            headers = self.auth.get_auth_headers()
            response = requests.get(endpoint, headers=headers, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            print(f"❌ Erro ao obter detalhes do reservatório {reservoir_id}: {str(e)}")
            return {}
    
    def get_reservoirs_by_subsystem(self, subsystem: str = None) -> pd.DataFrame:
        """
        Obtém dados de reservatórios, opcionalmente filtrando por subsistema
        
        Args:
            subsystem: 'SE/CO', 'S', 'NE', 'N' ou None para todos
        """
        reservoirs_list = self.get_reservoirs_list()
        
        if not reservoirs_list:
            return pd.DataFrame()
        
        # Converte para DataFrame
        df = pd.DataFrame(reservoirs_list)
        
        # Filtra por subsistema se especificado
        if subsystem and 'subsistema' in df.columns:
            df = df[df['subsistema'] == subsystem]
            print(f"📊 {len(df)} reservatórios no subsistema {subsystem}")
        
        # Adiciona informações básicas
        if not df.empty:
            # Calcula estatísticas
            if 'volumeUtil' in df.columns:
                df['volumeUtil'] = pd.to_numeric(df['volumeUtil'], errors='coerce')
                
                stats = {
                    'total_reservatorios': len(df),
                    'volume_medio': df['volumeUtil'].mean(),
                    'volume_min': df['volumeUtil'].min(),
                    'volume_max': df['volumeUtil'].max(),
                    'volume_total': df['volumeUtil'].sum() if len(df) > 0 else 0
                }
                
                print(f"📈 Estatísticas: Volume médio = {stats['volume_medio']:.1f}%")
            
            # Adiciona timestamp de coleta
            df['coletado_em'] = datetime.now().isoformat()
        
        return df
    
    def get_subsystem_summary(self) -> Dict[str, Any]:
        """Obtém resumo por subsistema"""
        df = self.get_reservoirs_by_subsystem()
        
        if df.empty:
            return {}
        
        summary = {}
        
        if 'subsistema' in df.columns and 'volumeUtil' in df.columns:
            # Agrupa por subsistema
            for subsys in df['subsistema'].unique():
                subset = df[df['subsistema'] == subsys]
                
                # Converte volumeUtil para numérico
                volumes = pd.to_numeric(subset['volumeUtil'], errors='coerce')
                
                summary[subsys] = {
                    'quantidade_reservatorios': len(subset),
                    'volume_medio': volumes.mean(),
                    'volume_min': volumes.min(),
                    'volume_max': volumes.max(),
                    'reservatorios_principais': subset.nlargest(3, 'capacidadeMaxima').to_dict('records') if 'capacidadeMaxima' in subset.columns else []
                }
        
        # Calcula média do SIN
        if 'volumeUtil' in df.columns:
            sin_volume = pd.to_numeric(df['volumeUtil'], errors='coerce').mean()
            summary['SIN'] = {
                'volume_medio': sin_volume,
                'quantidade_reservatorios': len(df),
                'status': 'ALERTA' if sin_volume < 50 else 'ATENÇÃO' if sin_volume < 65 else 'NORMAL'
            }
        
        return summary
    
    def get_historical_data(self, reservoir_id: str, days: int = 30) -> pd.DataFrame:
        """
        Obtém dados históricos de um reservatório
        Nota: Endpoint pode variar - ajuste conforme documentação
        """
        # ENDPOINT HIPOTÉTICO - ajuste conforme API real
        endpoint = f"{self.base_url}/reservatorios/{reservoir_id}/historico"
        
        try:
            headers = self.auth.get_auth_headers()
            
            params = {
                'dias': days,
                'formato': 'json'
            }
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Converte para DataFrame
            df = pd.DataFrame(data.get('dados', []))
            
            if not df.empty:
                # Processa colunas de data se existirem
                if 'data' in df.columns:
                    df['data'] = pd.to_datetime(df['data'])
                
                print(f"📊 {len(df)} registros históricos para reservatório {reservoir_id}")
            
            return df
            
        except Exception as e:
            print(f"⚠️ Erro ao obter dados históricos: {str(e)}")
            return pd.DataFrame()
    
    def save_reservoir_data(self, df: pd.DataFrame, filename: str = None) -> str:
        """Salva dados de reservatórios"""
        if df.empty:
            print("⚠️ Nenhum dado para salvar")
            return ""
        
        os.makedirs("data", exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"reservatorios_ons_{timestamp}"
        
        # Salva em CSV
        csv_path = f"data/{filename}.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        
        # Salva resumo em JSON
        summary = self.get_subsystem_summary()
        json_path = f"data/{filename}_summary.json"
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Dados salvos:")
        print(f"   📄 CSV: {csv_path}")
        print(f"   📊 JSON: {json_path}")
        
        return csv_path