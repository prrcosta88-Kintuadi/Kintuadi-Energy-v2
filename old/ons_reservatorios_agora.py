# ons_reservatorios_agora_fixed.py
import requests
import pandas as pd
import json
import numpy as np
from datetime import datetime, date
import os

class ONSReservatoriosAgoraFixed:
    """Coleta dados em tempo real dos reservatórios do ONS - VERSÃO CORRIGIDA"""
    
    def __init__(self, authenticator=None):
        self.authenticator = authenticator
        self.base_url = "https://integra.ons.org.br/api"
        
    def get_situacao_reservatorios(self):
        """Obtém situação atual dos reservatórios (sem autenticação)"""
        endpoint = f"{self.base_url}/energiaagora/Get/SituacaoDosReservatorios"
        
        print(f"🔍 Coletando situação dos reservatórios...")
        
        try:
            headers = {
                "accept": "application/json"
            }
            
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
            print(f"❌ Erro ao coletar dados: {str(e)}")
            return []
    
    def process_reservatorios_data(self, data):
        """Processa e analisa os dados dos reservatórios"""
        if not data:
            return pd.DataFrame(), {}
        
        df = pd.DataFrame(data)
        
        print(f"\n📊 ESTRUTURA DOS DADOS:")
        print(f"   • Total de reservatórios: {len(df)}")
        print(f"   • Colunas disponíveis: {', '.join(df.columns)}")
        print(f"\n📋 AMOSTRA DOS DADOS:")
        print(df.head(3).to_string())
        
        # Converte datas para datetime
        if 'Data' in df.columns:
            df['Data'] = pd.to_datetime(df['Data'])
            latest_date = df['Data'].max()
            print(f"\n   • Data mais recente: {latest_date.strftime('%d/%m/%Y')}")
        
        # Análise por subsistema
        summary = self._analyze_by_subsistema(df)
        
        # Calcula situação do SIN
        sin_summary = self._calculate_sin_status(df)
        summary['SIN'] = sin_summary
        
        return df, summary
    
    def _analyze_by_subsistema(self, df):
        """Analisa dados por subsistema"""
        summary = {}
        
        if 'Subsistema' in df.columns:
            subsistemas = df['Subsistema'].unique()
            print(f"\n📈 SUBMERCADOS ENCONTRADOS: {', '.join(subsistemas)}")
            
            for subsis in subsistemas:
                subset = df[df['Subsistema'] == subsis]
                
                if not subset.empty:
                    first = subset.iloc[0]
                    
                    stats = {
                        'quantidade_reservatorios': len(subset),
                        'data_referencia': self._convert_to_serializable(first.get('Data')),
                        'volume_util_medio': float(subset['ReservatorioPorcentagem'].mean()) if 'ReservatorioPorcentagem' in subset.columns else 0.0,
                        'volume_util_min': float(subset['ReservatorioPorcentagem'].min()) if 'ReservatorioPorcentagem' in subset.columns else 0.0,
                        'volume_util_max': float(subset['ReservatorioPorcentagem'].max()) if 'ReservatorioPorcentagem' in subset.columns else 0.0,
                        'energia_armazenada_mw': float(first.get('SubsistemaEARVerificadaMWMes', 0)),
                        'energia_armazenada_percentual': float(first.get('SubsistemaValorUtil', 0)),
                        'capacidade_maxima_mw': float(first.get('SubsistemaMax', 0))
                    }
                    
                    summary[subsis] = stats
                    print(f"   • {subsis}: {stats['quantidade_reservatorios']} reservatórios, Volume médio: {stats['volume_util_medio']:.1f}%")
        
        return summary
    
    def _calculate_sin_status(self, df):
        """Calcula situação do SIN"""
        sin_summary = {
            'data_coleta': datetime.now().isoformat(),
            'status': 'NORMAL'
        }
        
        if not df.empty:
            first = df.iloc[0]
            
            # Converte todos os valores para tipos serializáveis
            sin_summary.update({
                'energia_armazenada_mw': float(first.get('SINEARVerificadaMWMes', 0)),
                'energia_armazenada_percentual': float(first.get('SINEARPorcentagem', 0)),
                'capacidade_maxima_mw': float(first.get('SINMax', 0)),
                'total_reservatorios': int(len(df))
            })
            
            # Calcula volume útil médio do SIN
            if 'ReservatorioPorcentagem' in df.columns:
                volume_medio = float(df['ReservatorioPorcentagem'].mean())
                sin_summary['volume_util_medio'] = volume_medio
                
                # Define status baseado no volume
                if volume_medio < 40:
                    sin_summary['status'] = 'CRÍTICO'
                elif volume_medio < 60:
                    sin_summary['status'] = 'ALERTA'
                elif volume_medio < 80:
                    sin_summary['status'] = 'ATENÇÃO'
        
        return sin_summary
    
    def _convert_to_serializable(self, obj):
        """Converte objetos para tipos serializáveis em JSON"""
        if pd.isna(obj):
            return None
        elif isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj
    
    def save_reservatorios_data(self, df, summary, filename_prefix=None):
        """Salva dados dos reservatórios"""
        if df.empty:
            print("⚠️ Nenhum dado para salvar")
            return
        
        os.makedirs("data", exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        
        if filename_prefix is None:
            filename_prefix = "reservatorios_agora"
        
        # Salva dados completos em CSV
        csv_filename = f"data/{filename_prefix}_{timestamp}.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        
        # Converte summary para serializável
        summary_serializable = self._make_serializable(summary)
        
        # Salva resumo detalhado
        json_filename = f"data/{filename_prefix}_summary_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(summary_serializable, f, ensure_ascii=False, indent=2)
        
        # Salva resumo simplificado para dashboard
        simple_summary = {
            'timestamp': timestamp,
            'sin_status': summary_serializable.get('SIN', {}),
            'subsistemas': {k: {
                'volume_util_medio': v.get('volume_util_medio', 0),
                'status': self._get_volume_status(v.get('volume_util_medio', 0)),
                'reservatorios': v.get('quantidade_reservatorios', 0)
            } for k, v in summary_serializable.items() if k != 'SIN'}
        }
        
        simple_json = f"data/{filename_prefix}_simple_{timestamp}.json"
        with open(simple_json, 'w', encoding='utf-8') as f:
            json.dump(simple_summary, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Dados salvos:")
        print(f"   📄 CSV completo: {csv_filename}")
        print(f"   📊 JSON resumo: {json_filename}")
        print(f"   📈 JSON simplificado: {simple_json}")
        
        return csv_filename
    
    def _make_serializable(self, obj):
        """Converte recursivamente objetos para serializáveis"""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(v) for v in obj]
        elif isinstance(obj, tuple):
            return tuple(self._make_serializable(v) for v in obj)
        else:
            return self._convert_to_serializable(obj)
    
    def _get_volume_status(self, volume):
        """Retorna status baseado no volume"""
        if volume < 40:
            return 'CRÍTICO'
        elif volume < 60:
            return 'ALERTA'
        elif volume < 80:
            return 'ATENÇÃO'
        else:
            return 'NORMAL'
    
    def generate_report(self, df, summary):
        """Gera relatório textual"""
        report = []
        report.append("=" * 60)
        report.append("📊 RELATÓRIO DE RESERVATÓRIOS - ONS")
        report.append("=" * 60)
        report.append(f"Data da coleta: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        report.append(f"Total de reservatórios: {len(df)}")
        
        if 'SIN' in summary:
            sin = summary['SIN']
            report.append(f"\n⚡ SITUAÇÃO DO SIN:")
            report.append(f"   • Energia armazenada: {sin.get('energia_armazenada_mw', 0):,.0f} MW")
            report.append(f"   • Volume útil médio: {sin.get('volume_util_medio', 0):.1f}%")
            report.append(f"   • Status: {sin.get('status', 'N/A')}")
        
        report.append(f"\n📈 POR SUBMERCADO:")
        for subsis, stats in summary.items():
            if subsis != 'SIN':
                report.append(f"\n   {subsis}:")
                report.append(f"     • Reservatórios: {stats.get('quantidade_reservatorios', 0)}")
                report.append(f"     • Volume útil médio: {stats.get('volume_util_medio', 0):.1f}%")
                report.append(f"     • Energia armazenada: {stats.get('energia_armazenada_mw', 0):,.0f} MW")
                report.append(f"     • Status: {self._get_volume_status(stats.get('volume_util_medio', 0))}")
        
        # Top 5 reservatórios mais críticos
        if 'ReservatorioPorcentagem' in df.columns and 'Reservatorio' in df.columns:
            critical = df.nsmallest(5, 'ReservatorioPorcentagem')
            report.append(f"\n⚠️ RESERVATÓRIOS MAIS CRÍTICOS:")
            for _, row in critical.iterrows():
                report.append(f"   • {row['Reservatorio']}: {row['ReservatorioPorcentagem']:.1f}% ({row['Subsistema']})")
        
        # Top 5 reservatórios mais cheios
        if 'ReservatorioPorcentagem' in df.columns and 'Reservatorio' in df.columns:
            full = df.nlargest(5, 'ReservatorioPorcentagem')
            report.append(f"\n💧 RESERVATÓRIOS MAIS CHEIOS:")
            for _, row in full.iterrows():
                report.append(f"   • {row['Reservatorio']}: {row['ReservatorioPorcentagem']:.1f}% ({row['Subsistema']})")
        
        report.append(f"\n" + "=" * 60)
        
        return '\n'.join(report)


def test_reservatorios_agora():
    """Testa a API de reservatórios agora - VERSÃO CORRIGIDA"""
    print("🧪 TESTE API RESERVATÓRIOS AGORA - CORRIGIDO")
    print("=" * 50)
    
    collector = ONSReservatoriosAgoraFixed()
    
    # Coleta dados
    print("\n1. Coletando dados...")
    data = collector.get_situacao_reservatorios()
    
    if data:
        print("\n2. Processando dados...")
        df, summary = collector.process_reservatorios_data(data)
        
        print("\n3. Gerando relatório...")
        report = collector.generate_report(df, summary)
        print(report)
        
        print("\n4. Salvando dados...")
        collector.save_reservatorios_data(df, summary)
        
        return True
    else:
        print("❌ Nenhum dado coletado")
        return False


if __name__ == "__main__":
    test_reservatorios_agora()