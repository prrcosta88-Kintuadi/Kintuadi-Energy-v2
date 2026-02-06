# scripts/ons_reservatorios.py
import requests
import pandas as pd
import json
from datetime import datetime
import os

class ONSReservatoriosCollector:
    """Coleta dados de reservatórios do ONS (sem autenticação)"""
    
    def __init__(self):
        self.base_url = "https://integra.ons.org.br/api"
    
    def get_situacao_reservatorios(self):
        """Obtém situação atual dos reservatórios"""
        endpoint = f"{self.base_url}/energiaagora/Get/SituacaoDosReservatorios"
        
        print("🔍 Coletando situação dos reservatórios do ONS...")
        
        try:
            headers = {"accept": "application/json"}
            response = requests.get(endpoint, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if isinstance(data, list):
                print(f"✅ {len(data)} reservatórios coletados")
                return data
            else:
                print(f"⚠️ Resposta inesperada: {type(data)}")
                return []
                
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
            return []
    
    def process_reservatorios_data(self, data):
        """Processa dados dos reservatórios"""
        if not data:
            return pd.DataFrame(), {}
        
        df = pd.DataFrame(data)
        
        # Converte datas
        if 'Data' in df.columns:
            df['Data'] = pd.to_datetime(df['Data'])
        
        # Análise por subsistema
        summary = self._analyze_by_subsistema(df)
        
        # Análise geral
        summary['geral'] = self._analyze_geral(df)
        
        return df, summary
    
    def _analyze_by_subsistema(self, df):
        """Analisa dados por subsistema"""
        summary = {}
        
        if 'Subsistema' in df.columns and 'ReservatorioPorcentagem' in df.columns:
            for subsis in df['Subsistema'].unique():
                subset = df[df['Subsistema'] == subsis]
                volumes = pd.to_numeric(subset['ReservatorioPorcentagem'], errors='coerce').dropna()
                
                if len(volumes) > 0:
                    summary[subsis] = {
                        'quantidade': len(subset),
                        'volume_medio': float(volumes.mean()),
                        'volume_min': float(volumes.min()),
                        'volume_max': float(volumes.max()),
                        'energia_armazenada': float(subset['SubsistemaEARVerificadaMWMes'].iloc[0]) 
                            if 'SubsistemaEARVerificadaMWMes' in subset.columns and len(subset) > 0 else 0
                    }
        
        return summary
    
    def _analyze_geral(self, df):
        """Análise geral do sistema"""
        geral = {
            'data_coleta': datetime.now().isoformat(),
            'total_reservatorios': len(df),
            'status': 'NORMAL'
        }
        
        if 'ReservatorioPorcentagem' in df.columns:
            volumes = pd.to_numeric(df['ReservatorioPorcentagem'], errors='coerce').dropna()
            
            if len(volumes) > 0:
                volume_medio = float(volumes.mean())
                geral['volume_medio_geral'] = volume_medio
                
                # Define status
                if volume_medio < 40:
                    geral['status'] = 'CRÍTICO'
                elif volume_medio < 60:
                    geral['status'] = 'ALERTA'
                elif volume_medio < 80:
                    geral['status'] = 'ATENÇÃO'
        
        if 'SINEARVerificadaMWMes' in df.columns and len(df) > 0:
            geral['energia_sin'] = float(df['SINEARVerificadaMWMes'].iloc[0])
        
        return geral
    
    def save_reservatorios_data(self, df, summary, filename_prefix=None):
        """Salva dados dos reservatórios"""
        if df.empty:
            return None
        
        os.makedirs("data", exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        
        if filename_prefix is None:
            filename_prefix = "reservatorios_ons"
        
        # Salva CSV
        csv_filename = f"data/{filename_prefix}_{timestamp}.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        
        # Salva resumo
        json_filename = f"data/{filename_prefix}_summary_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Dados salvos: {csv_filename}, {json_filename}")
        return csv_filename