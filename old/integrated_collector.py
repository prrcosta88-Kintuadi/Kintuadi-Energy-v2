# scripts/integrated_collector.py - CORREÇÃO DO SALVAMENTO
import json
import pandas as pd
from datetime import datetime
import os

class KintuadiIntegratedCollector:
    """Coletor integrado Kintuadi Energy - VERSÃO SIMPLIFICADA"""
    
    def __init__(self, ons_username=None, ons_password=None):
        from .ccee_collector import CCEECollector
        from .ons_reservatorios import ONSReservatoriosCollector
        from .energy_analyzer import EnergyAnalyzer
        
        # Inicializa coletores básicos
        self.ccee = CCEECollector()
        self.ons_reservatorios = ONSReservatoriosCollector()
        self.energy_analyzer = EnergyAnalyzer()
        
        # Cria diretório de dados
        os.makedirs("data", exist_ok=True)
    
    def collect_all(self):
        """Coleta todos os dados disponíveis - VERSÃO SIMPLIFICADA"""
        print("=" * 60)
        print("🌞 KINTUADI ENERGY - COLETOR INTEGRADO")
        print("=" * 60)
        print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        
        try:
            # 1. Coleta ONS
            print("\n1️⃣ COLETANDO DADOS DO ONS...")
            ons_data = self.collect_ons_simple()
            
            # 2. Coleta CCEE
            print("\n2️⃣ COLETANDO DADOS DA CCEE...")
            ccee_data = self.collect_ccee_simple()
            
            # 3. Análise integrada
            print("\n3️⃣ ANALISANDO DADOS INTEGRADOS...")
            analysis = self.energy_analyzer.analyze_integrated_data(ons_data, ccee_data)
            
            # 4. Prepara dados para salvar
            all_data = {
                'metadata': {
                    'coleta_inicio': datetime.now().isoformat(),
                    'projeto': 'Kintuadi Energy',
                    'versao': '1.1'
                },
                'ons': ons_data,
                'ccee': ccee_data,
                'analysis': analysis
            }
            
            # 5. Salva dados
            print("\n4️⃣ SALVANDO DADOS...")
            self.save_data_simple(all_data)
            
            # 6. Gera relatório
            print("\n5️⃣ GERANDO RELATÓRIO...")
            self.generate_report_simple(all_data)
            
            return all_data
            
        except Exception as e:
            print(f"❌ Erro durante a coleta: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def collect_ons_simple(self):
        """Coleta dados do ONS de forma simples"""
        raw_data = self.ons_reservatorios.get_situacao_reservatorios()
        
        if not raw_data:
            return {'status': 'erro', 'mensagem': 'Nenhum dado coletado'}
        
        # Processa dados
        df, summary = self.ons_reservatorios.process_reservatorios_data(raw_data)
        
        # Salva CSV
        csv_filename = f"data/reservatorios_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        
        # Retorna dados simplificados
        return {
            'status': 'sucesso',
            'total_reservatorios': len(raw_data),
            'summary': summary,
            'arquivo': csv_filename
        }
    
    def collect_ccee_simple(self):
        """Coleta dados da CCEE de forma simples"""
        raw_data = self.ccee.get_recent_pld(limit=200)
        
        if not raw_data:
            return {'status': 'erro', 'mensagem': 'Nenhum dado coletado'}
        
        # Processa dados
        df = self.ccee.create_dataframe(raw_data)
        stats = self.ccee.calculate_statistics(df)
        
        # Salva CSV
        csv_filename = f"data/pld_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        
        # Retorna dados simplificados
        return {
            'status': 'sucesso',
            'total_registros': len(raw_data),
            'statistics': stats,
            'arquivo': csv_filename
        }
    
    def save_data_simple(self, data):
        """Salva dados de forma simples e segura"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. Salva dados completos (com tratamento de tipos)
        complete_filename = f"data/kintuadi_complete_{timestamp}.json"
        
        # Converte manualmente para evitar problemas de serialização
        data_to_save = {
            'metadata': data['metadata'],
            'ons': {
                'status': data['ons']['status'],
                'total_reservatorios': data['ons']['total_reservatorios'],
                'summary': self._convert_summary(data['ons']['summary'])
            },
            'ccee': {
                'status': data['ccee']['status'],
                'total_registros': data['ccee']['total_registros'],
                'statistics': data['ccee']['statistics']
            },
            'analysis': data['analysis']
        }
        
        with open(complete_filename, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        
        # 2. Salva dados para dashboard
        dashboard_data = {
            'timestamp': timestamp,
            'ons_summary': data['ons']['summary'].get('geral', {}),
            'ccee_stats': data['ccee'].get('statistics', {}),
            'analysis': data['analysis']
        }
        
        # Remove objetos complexos
        dashboard_simple = self._simplify_for_dashboard(dashboard_data)
        
        dashboard_filename = f"data/kintuadi_dashboard_{timestamp}.json"
        with open(dashboard_filename, 'w', encoding='utf-8') as f:
            json.dump(dashboard_simple, f, ensure_ascii=False, indent=2)
        
        # 3. Atualiza latest
        latest_filename = "data/kintuadi_latest.json"
        with open(latest_filename, 'w', encoding='utf-8') as f:
            json.dump(dashboard_simple, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Dados salvos:")
        print(f"   📄 Completo: {complete_filename}")
        print(f"   📊 Dashboard: {dashboard_filename}")
        print(f"   🔄 Latest: {latest_filename}")
    
    def _convert_summary(self, summary):
        """Converte summary para formato serializável"""
        result = {}
        
        for key, value in summary.items():
            if key == 'geral':
                result[key] = {
                    k: (float(v) if isinstance(v, (int, float)) else v)
                    for k, v in value.items()
                }
            elif key == 'subsistemas':
                result[key] = {
                    k: {
                        sub_k: (float(sub_v) if isinstance(sub_v, (int, float)) else sub_v)
                        for sub_k, sub_v in v.items()
                    }
                    for k, v in value.items()
                }
            else:
                result[key] = value
        
        return result
    
    def _simplify_for_dashboard(self, data):
        """Simplifica dados para o dashboard"""
        simplified = {
            'timestamp': data.get('timestamp', ''),
            'ons': {
                'total_reservatorios': data.get('ons_summary', {}).get('total_reservatorios', 0),
                'volume_medio': data.get('ons_summary', {}).get('volume_medio_geral', 0),
                'status': data.get('ons_summary', {}).get('status', 'N/A')
            },
            'ccee': {
                'pld_medio': data.get('ccee_stats', {}).get('geral', {}).get('pld_medio', 0),
                'registros': data.get('ccee_stats', {}).get('geral', {}).get('registros', 0)
            },
            'analysis': {
                'tendencia': data.get('analysis', {}).get('tendencia_mercado', 'N/A'),
                'alerta': data.get('analysis', {}).get('alerta', False)
            }
        }
        
        # Converte todos os números para float
        for section in simplified.values():
            if isinstance(section, dict):
                for key, value in section.items():
                    if isinstance(value, (int, float)):
                        section[key] = float(value)
        
        return simplified
    
    def generate_report_simple(self, data):
        """Gera relatório simplificado"""
        try:
            report = []
            report.append("=" * 60)
            report.append("📊 RELATÓRIO KINTUADI ENERGY")
            report.append("=" * 60)
            report.append(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            
            # Dados ONS
            ons = data['ons']
            if ons['status'] == 'sucesso':
                summary = ons['summary']
                geral = summary.get('geral', {})
                
                report.append(f"\n💧 RESERVATÓRIOS DO ONS:")
                report.append(f"   • Total: {ons['total_reservatorios']}")
                report.append(f"   • Status: {geral.get('status', 'N/A')}")
                report.append(f"   • Volume médio: {geral.get('volume_medio_geral', 0):.1f}%")
                
                if 'subsistemas' in summary:
                    report.append(f"   • Por subsistema:")
                    for subsis, subdata in summary['subsistemas'].items():
                        report.append(f"     - {subsis}: {subdata.get('volume_medio', 0):.1f}%")
            
            # Dados CCEE
            ccee = data['ccee']
            if ccee['status'] == 'sucesso':
                stats = ccee['statistics']
                
                report.append(f"\n💰 MERCADO DE ENERGIA (CCEE):")
                report.append(f"   • PLD médio: R$ {stats.get('geral', {}).get('pld_medio', 0):.2f}/MWh")
                report.append(f"   • Variação: R$ {stats.get('geral', {}).get('pld_desvio', 0):.2f}/MWh")
                report.append(f"   • Registros: {stats.get('geral', {}).get('registros', 0)}")
            
            # Análise
            analysis = data.get('analysis', {})
            if analysis:
                report.append(f"\n📈 ANÁLISE INTEGRADA:")
                report.append(f"   • Tendência: {analysis.get('tendencia_mercado', 'N/A')}")
                
                if analysis.get('alerta', False):
                    report.append(f"   ⚠️ SISTEMA EM ALERTA")
            
            report.append(f"\n" + "=" * 60)
            report.append("📁 Dados disponíveis na pasta 'data/'")
            
            print('\n'.join(report))
            
        except Exception as e:
            print(f"⚠️ Erro ao gerar relatório: {str(e)}")