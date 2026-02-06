# scripts/ccee_collector.py - ATUALIZADO
import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import time

class CCEECollector:
    """Coleta dados do PLD da CCEE - VERSÃO CORRIGIDA"""
    
    def __init__(self):
        self.base_url = "https://dadosabertos.ccee.org.br/api/3/action"
        self.resource_id = "3f279d6b-1069-42f7-9b0a-217b084729c4"
    
    def get_recent_pld(self, days=7, limit=500):
        """
        Coleta dados recentes do PLD - VERSÃO SIMPLIFICADA
        
        Args:
            days: Número de dias para trás
            limit: Máximo de registros por página
        """
        all_records = []
        offset = 0
        max_pages = 2  # Reduz para 2 páginas para teste
        
        print(f"🔍 Coletando PLD recente...")
        
        for page in range(max_pages):
            url = f"{self.base_url}/datastore_search"
            params = {
                "resource_id": self.resource_id,
                "limit": limit,
                "offset": offset,
                "sort": "_id desc"  # Mais recentes primeiro
            }
            
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("success"):
                    records = data["result"]["records"]
                    
                    if not records:
                        break
                    
                    # ADICIONA TODOS OS REGISTROS SEM FILTRAR
                    all_records.extend(records)
                    
                    print(f"   📄 Página {page + 1}: {len(records)} registros")
                    
                    # Se chegou ao fim
                    if len(records) < limit:
                        break
                    
                    offset += limit
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"⚠️ Erro na página {page + 1}: {str(e)}")
                break
        
        print(f"✅ Total coletado: {len(all_records)} registros")
        return all_records
    
    def create_dataframe(self, records):
        """Cria DataFrame dos dados do PLD"""
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        
        # Converte colunas numéricas
        numeric_cols = ['HORA', 'PLD_HORA', 'PERIODO_COMERCIALIZACAO']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def calculate_statistics(self, df):
        """Calcula estatísticas do PLD"""
        if df.empty:
            return {}
        
        stats = {}
        
        # Estatísticas gerais
        if 'PLD_HORA' in df.columns:
            pld_values = pd.to_numeric(df['PLD_HORA'], errors='coerce').dropna()
            
            if len(pld_values) > 0:
                stats['geral'] = {
                    'pld_medio': float(pld_values.mean()),
                    'pld_min': float(pld_values.min()),
                    'pld_max': float(pld_values.max()),
                    'pld_desvio': float(pld_values.std()),
                    'registros': len(pld_values)
                }
        
        # Por submercado
        if 'SUBMERCADO' in df.columns and 'PLD_HORA' in df.columns:
            stats['por_submercado'] = {}
            
            for subm in df['SUBMERCADO'].unique():
                subset = df[df['SUBMERCADO'] == subm]
                pld_subm = pd.to_numeric(subset['PLD_HORA'], errors='coerce').dropna()
                
                if len(pld_subm) > 0:
                    stats['por_submercado'][subm] = {
                        'pld_medio': float(pld_subm.mean()),
                        'registros': len(subset),
                        'variacao': float(pld_subm.std())
                    }
        
        return stats
    
    def save_to_csv(self, df, filename=None):
        """Salva DataFrame em CSV"""
        if df.empty:
            return None
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"pld_{timestamp}.csv"
        
        df.to_csv(f"data/{filename}", index=False, encoding='utf-8-sig')
        return filename