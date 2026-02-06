# kintuadi_system_v1.py
import requests
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import os
import sys
from typing import Dict, List, Optional, Any
import time

class KintuadiSystem:
    """
    Sistema integrado de coleta de dados energéticos
    Versão 1.0 - Foco em APIs que funcionam
    """
    
    def __init__(self):
        self.data_dir = "data"
        self.reports_dir = "reports"
        self.setup_directories()
        
        # Configurações
        self.config = {
            'ccee': {
                'base_url': 'https://dadosabertos.ccee.org.br/api/3/action',
                'resource_id': '3f279d6b-1069-42f7-9b0a-217b084729c4'
            },
            'ons': {
                'base_url': 'https://integra.ons.org.br/api',
                'reservatorios_endpoint': '/energiaagora/Get/SituacaoDosReservatorios'
            },
            'collection': {
                'max_records': 1000,
                'timeout': 30,
                'retries': 3
            }
        }
        
        # Cache de dados
        self.cache = {}
        
    def setup_directories(self):
        """Cria diretórios necessários"""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "raw"), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "processed"), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "integrated"), exist_ok=True)
        
    # ==================== MÓDULO CCEE ====================
    
    def collect_ccee_pld(self, days_back: int = 7, limit: int = 1000) -> Dict:
        """Coleta dados do PLD da CCEE"""
        print("\n📊 COLETANDO DADOS DA CCEE (PLD)...")
        
        all_records = []
        offset = 0
        
        try:
            # Coleta com paginação
            while len(all_records) < limit:
                url = f"{self.config['ccee']['base_url']}/datastore_search"
                params = {
                    'resource_id': self.config['ccee']['resource_id'],
                    'limit': min(100, limit - len(all_records)),
                    'offset': offset,
                    'sort': '_id desc'
                }
                
                response = requests.get(url, params=params, timeout=self.config['collection']['timeout'])
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('success'):
                        records = data['result']['records']
                        
                        if not records:
                            break
                        
                        all_records.extend(records)
                        offset += len(records)
                        
                        print(f"   ✅ Página {offset//100 + 1}: {len(records)} registros")
                        
                        # Filtra por data se necessário
                        if days_back:
                            filtered = self._filter_pld_by_date(records, days_back)
                            if len(filtered) < len(records):
                                print(f"   📅 Mantendo apenas últimos {days_back} dias")
                        
                        time.sleep(0.1)  # Respeita o servidor
                    else:
                        print(f"   ⚠️ API retornou success=False")
                        break
                else:
                    print(f"   ❌ HTTP {response.status_code}: {response.text[:100]}")
                    break
                    
        except Exception as e:
            print(f"   ❌ Erro na coleta CCEE: {str(e)}")
        
        # Processa os dados coletados
        processed = self.process_ccee_data(all_records)
        
        # Salva dados
        self.save_ccee_data(all_records, processed)
        
        return {
            'raw': all_records,
            'processed': processed,
            'status': 'success' if all_records else 'failed'
        }
    
    def _filter_pld_by_date(self, records: List, days_back: int) -> List:
        """Filtra registros do PLD por data"""
        filtered = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        for record in records:
            try:
                # Tenta extrair data do registro
                mes_ref = record.get('MES_REFERENCIA', '')
                dia = record.get('DIA', '')
                
                if len(mes_ref) == 6 and dia.isdigit():
                    ano = int(mes_ref[:4])
                    mes = int(mes_ref[4:6])
                    dia_int = int(dia)
                    
                    record_date = datetime(ano, mes, dia_int)
                    
                    if record_date >= cutoff_date:
                        filtered.append(record)
            except:
                continue
        
        return filtered
    
    def process_ccee_data(self, records: List) -> Dict:
        """Processa dados da CCEE"""
        if not records:
            return {}
        
        df = pd.DataFrame(records)
        
        # Converte colunas numéricas
        numeric_cols = ['PLD_HORA', 'HORA', 'PERIODO_COMERCIALIZACAO']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        summary = {
            'metadata': {
                'data_processamento': datetime.now().isoformat(),
                'total_registros': len(df),
                'periodo_coleta': f"Últimos {len(df)} registros"
            },
            'estatisticas_gerais': {},
            'por_submercado': {},
            'tendencias': {}
        }
        
        # Estatísticas gerais do PLD
        if 'PLD_HORA' in df.columns:
            pld_values = df['PLD_HORA'].dropna()
            
            if len(pld_values) > 0:
                summary['estatisticas_gerais'] = {
                    'media': float(pld_values.mean()),
                    'mediana': float(pld_values.median()),
                    'minimo': float(pld_values.min()),
                    'maximo': float(pld_values.max()),
                    'desvio_padrao': float(pld_values.std()),
                    'coeficiente_variacao': float(pld_values.std() / pld_values.mean() if pld_values.mean() != 0 else 0)
                }
        
        # Por submercado
        if 'SUBMERCADO' in df.columns and 'PLD_HORA' in df.columns:
            for subm in df['SUBMERCADO'].unique():
                subset = df[df['SUBMERCADO'] == subm]
                pld_subm = subset['PLD_HORA'].dropna()
                
                if len(pld_subm) > 0:
                    summary['por_submercado'][subm] = {
                        'registros': len(subset),
                        'pld_medio': float(pld_subm.mean()),
                        'pld_min': float(pld_subm.min()),
                        'pld_max': float(pld_subm.max()),
                        'volatilidade': float(pld_subm.std())
                    }
        
        # Tendência (últimas 24h vs anteriores)
        if 'MES_REFERENCIA' in df.columns and 'DIA' in df.columns and 'HORA' in df.columns:
            df['data_hora'] = df.apply(self._parse_pld_datetime, axis=1)
            
            if 'data_hora' in df.columns:
                df = df.sort_values('data_hora')
                
                # Separa últimas 24 horas se tiver dados suficientes
                if len(df) >= 24:
                    ultimas_24h = df.tail(24)
                    anteriores = df.iloc[:-24]
                    
                    if len(ultimas_24h) > 0 and len(anteriores) > 0:
                        pld_24h = ultimas_24h['PLD_HORA'].mean() if 'PLD_HORA' in ultimas_24h.columns else 0
                        pld_anterior = anteriores['PLD_HORA'].mean() if 'PLD_HORA' in anteriores.columns else 0
                        
                        variacao = ((pld_24h - pld_anterior) / pld_anterior * 100) if pld_anterior != 0 else 0
                        
                        summary['tendencias'] = {
                            'pld_24h': float(pld_24h),
                            'pld_anterior': float(pld_anterior),
                            'variacao_percentual': float(variacao),
                            'tendencia': 'alta' if variacao > 5 else 'baixa' if variacao < -5 else 'estavel'
                        }
        
        return summary
    
    def _parse_pld_datetime(self, row):
        """Converte campos do PLD para datetime"""
        try:
            mes_ref = str(row.get('MES_REFERENCIA', ''))
            dia = str(row.get('DIA', ''))
            hora = int(row.get('HORA', 0))
            
            if len(mes_ref) == 6 and dia.isdigit():
                ano = int(mes_ref[:4])
                mes = int(mes_ref[4:6])
                dia_int = int(dia)
                
                return datetime(ano, mes, dia_int, hora)
        except:
            pass
        return None
    
    # ==================== MÓDULO ONS ====================
    
    def collect_ons_reservatorios(self) -> Dict:
        """Coleta dados de reservatórios do ONS"""
        print("\n💧 COLETANDO DADOS DO ONS (RESERVATÓRIOS)...")
        
        url = f"{self.config['ons']['base_url']}{self.config['ons']['reservatorios_endpoint']}"
        
        try:
            response = requests.get(url, timeout=self.config['collection']['timeout'])
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    print(f"   ✅ {len(data)} reservatórios coletados")
                    
                    # Processa dados
                    processed = self.process_ons_data(data)
                    
                    # Salva dados
                    self.save_ons_data(data, processed)
                    
                    return {
                        'raw': data,
                        'processed': processed,
                        'status': 'success'
                    }
                else:
                    print(f"   ⚠️ Resposta não é uma lista: {type(data)}")
            else:
                print(f"   ❌ HTTP {response.status_code}: {response.text[:100]}")
                
        except Exception as e:
            print(f"   ❌ Erro na coleta ONS: {str(e)}")
        
        return {'raw': [], 'processed': {}, 'status': 'failed'}
    
    def process_ons_data(self, data: List) -> Dict:
        """Processa dados do ONS"""
        if not data:
            return {}
        
        df = pd.DataFrame(data)
        
        summary = {
            'metadata': {
                'data_processamento': datetime.now().isoformat(),
                'total_reservatorios': len(df),
                'data_referencia': df['Data'].iloc[0] if 'Data' in df.columns and len(df) > 0 else 'N/A'
            },
            'situacao_sin': {},
            'por_subsistema': {},
            'analise_risco': {}
        }
        
        # Situação do SIN
        if len(df) > 0:
            primeiro = df.iloc[0]
            summary['situacao_sin'] = {
                'energia_armazenada_mw': float(primeiro.get('SINEARVerificadaMWMes', 0)),
                'energia_armazenada_percentual': float(primeiro.get('SINEARPorcentagem', 0)) * 100,  # Convertendo para percentual
                'capacidade_maxima_mw': float(primeiro.get('SINMax', 0))
            }
        
        # Por subsistema
        if 'Subsistema' in df.columns and 'ReservatorioPorcentagem' in df.columns:
            for subsis in df['Subsistema'].unique():
                subset = df[df['Subsistema'] == subsis]
                
                # Converte volume para numérico
                volumes = pd.to_numeric(subset['ReservatorioPorcentagem'], errors='coerce')
                volumes_validas = volumes.dropna()
                
                if len(volumes_validas) > 0:
                    # Pega dados do subsistema do primeiro registro
                    primeiro_subs = subset.iloc[0]
                    
                    summary['por_subsistema'][subsis] = {
                        'quantidade_reservatorios': len(subset),
                        'volume_util_medio': float(volumes_validas.mean()),
                        'volume_util_min': float(volumes_validas.min()),
                        'volume_util_max': float(volumes_validas.max()),
                        'energia_armazenada_mw': float(primeiro_subs.get('SubsistemaEARVerificadaMWMes', 0)),
                        'energia_armazenada_percentual': float(primeiro_subs.get('SubsistemaValorUtil', 0)),
                        'capacidade_maxima_mw': float(primeiro_subs.get('SubsistemaMax', 0)),
                        'status': self._classificar_status_volume(float(volumes_validas.mean()))
                    }
        
        # Análise de risco
        summary['analise_risco'] = self._analisar_risco_hidrologico(summary)
        
        return summary
    
    def _classificar_status_volume(self, volume: float) -> str:
        """Classifica status baseado no volume útil"""
        if volume < 20:
            return 'CRÍTICO EXTREMO'
        elif volume < 40:
            return 'CRÍTICO'
        elif volume < 60:
            return 'ALERTA'
        elif volume < 80:
            return 'ATENÇÃO'
        else:
            return 'NORMAL'
    
    def _analisar_risco_hidrologico(self, summary: Dict) -> Dict:
        """Analisa risco hidrológico baseado nos dados"""
        analise = {
            'nivel_risco': 'DESCONHECIDO',
            'pontuacao': 0,
            'fatores': [],
            'recomendacoes': []
        }
        
        # Calcula volume médio do sistema
        volumes = []
        for subsis, data in summary.get('por_subsistema', {}).items():
            volumes.append(data.get('volume_util_medio', 0))
        
        if volumes:
            volume_medio = sum(volumes) / len(volumes)
            analise['volume_medio_sistema'] = volume_medio
            
            # Calcula pontuação de risco (0-100)
            pontuacao = max(0, min(100, (100 - volume_medio) * 1.5))
            analise['pontuacao'] = pontuacao
            
            # Define nível de risco
            if pontuacao >= 80:
                analise['nivel_risco'] = 'MUITO ALTO'
                analise['fatores'].append(f'Volume médio muito baixo ({volume_medio:.1f}%)')
                analise['recomendacoes'].append('Acionar térmicas de forma preventiva')
                analise['recomendacoes'].append('Aumentar importação de energia')
            elif pontuacao >= 60:
                analise['nivel_risco'] = 'ALTO'
                analise['fatores'].append(f'Volume médio baixo ({volume_medio:.1f}%)')
                analise['recomendacoes'].append('Monitorar PLD diariamente')
                analise['recomendacoes'].append('Considerar acionamento térmico')
            elif pontuacao >= 40:
                analise['nivel_risco'] = 'MODERADO'
                analise['fatores'].append(f'Volume médio moderado ({volume_medio:.1f}%)')
                analise['recomendacoes'].append('Acompanhar previsão hidrológica')
            elif pontuacao >= 20:
                analise['nivel_risco'] = 'BAIXO'
                analise['fatores'].append(f'Volume médio adequado ({volume_medio:.1f}%)')
            else:
                analise['nivel_risco'] = 'MUITO BAIXO'
                analise['fatores'].append(f'Volume médio excelente ({volume_medio:.1f}%)')
        
        return analise
    
    # ==================== MÓDULO DE INTEGRAÇÃO ====================
    
    def integrate_data(self, ccee_data: Dict, ons_data: Dict) -> Dict:
        """Integra dados de CCEE e ONS"""
        print("\n🔗 INTEGRANDO DADOS...")
        
        integrated = {
            'metadata': {
                'projeto': 'Kintuadi Energy System',
                'versao': '1.0',
                'data_integracao': datetime.now().isoformat(),
                'fontes': ['CCEE_PLD', 'ONS_RESERVATORIOS']
            },
            'dados_brutos': {
                'ccee_count': len(ccee_data.get('raw', [])),
                'ons_count': len(ons_data.get('raw', []))
            },
            'analise_integrada': self._create_integrated_analysis(
                ccee_data.get('processed', {}),
                ons_data.get('processed', {})
            ),
            'indicadores_chave': self._calculate_key_indicators(
                ccee_data.get('processed', {}),
                ons_data.get('processed', {})
            ),
            'dashboard_data': self._prepare_dashboard_data(
                ccee_data.get('processed', {}),
                ons_data.get('processed', {})
            )
        }
        
        # Salva dados integrados
        self.save_integrated_data(integrated)
        
        return integrated
    
    def _create_integrated_analysis(self, ccee_processed: Dict, ons_processed: Dict) -> Dict:
        """Cria análise integrada"""
        analysis = {
            'correlacao_volume_pld': 'NÃO CALCULADA',
            'pressao_mercado': 0,
            'recomendacoes_estrategicas': [],
            'alerta_operacional': False
        }
        
        # Calcula correlação entre volume e PLD (simplificado)
        volume_medio = 0
        pld_medio = 0
        
        # Obtém volume médio do SIN
        if 'por_subsistema' in ons_processed:
            volumes = [data.get('volume_util_medio', 0) for data in ons_processed['por_subsistema'].values()]
            if volumes:
                volume_medio = sum(volumes) / len(volumes)
        
        # Obtém PLD médio
        if 'estatisticas_gerais' in ccee_processed:
            pld_medio = ccee_processed['estatisticas_gerais'].get('media', 0)
        
        # Pressão de mercado (0-100)
        if volume_medio > 0 and pld_medio > 0:
            # Fórmula simplificada: quanto menor o volume, maior a pressão
            pressao = min(100, (100 - volume_medio) * (pld_medio / 200))
            analysis['pressao_mercado'] = pressao
            
            # Define correlação
            if volume_medio < 50 and pld_medio > 200:
                analysis['correlacao_volume_pld'] = 'FORTE NEGATIVA'
                analysis['alerta_operacional'] = True
                analysis['recomendacoes_estrategicas'].append(
                    'ALTA CORRELAÇÃO: Volume baixo e PLD alto. Espera-se pressão '
                    'de alta nos preços. Geradores: aproveitar spot. '
                    'Consumidores: proteger-se com contratos.'
                )
            elif volume_medio < 60:
                analysis['correlacao_volume_pld'] = 'MODERADA NEGATIVA'
                analysis['recomendacoes_estrategicas'].append(
                    'Volume em nível de alerta. Monitorar preços de mercado.'
                )
            else:
                analysis['correlacao_volume_pld'] = 'FRACA'
                analysis['recomendacoes_estrategicas'].append(
                    'Sistema com volume adequado. Mercado estável.'
                )
        
        # Adiciona recomendações baseadas em risco hidrológico
        if 'analise_risco' in ons_processed:
            risco = ons_processed['analise_risco']
            if risco.get('nivel_risco') in ['ALTO', 'MUITO ALTO']:
                analysis['alerta_operacional'] = True
                analysis['recomendacoes_estrategicas'].append(
                    f"ALERTA DE RISCO HIDROLÓGICO: {risco.get('nivel_risco')}. "
                    f"{'; '.join(risco.get('recomendacoes', []))}"
                )
        
        # Adiciona recomendações baseadas em tendência do PLD
        if 'tendencias' in ccee_processed:
            tendencia = ccee_processed['tendencias']
            if tendencia.get('tendencia') == 'alta':
                analysis['recomendacoes_estrategicas'].append(
                    f"TENDÊNCIA DE ALTA NO PLD: +{tendencia.get('variacao_percentual', 0):.1f}%. "
                    "Considerar ajustes na estratégia de contratação."
                )
        
        return analysis
    
    def _calculate_key_indicators(self, ccee_processed: Dict, ons_processed: Dict) -> Dict:
        """Calcula indicadores-chave para decisão"""
        indicators = {}
        
        # 1. Índice de Segurança Energética (0-100)
        volume_medio = 0
        if 'por_subsistema' in ons_processed:
            volumes = [data.get('volume_util_medio', 0) for data in ons_processed['por_subsistema'].values()]
            if volumes:
                volume_medio = sum(volumes) / len(volumes)
        
        indicators['seguranca_energetica'] = {
            'valor': min(100, volume_medio),  # Volume já está em percentual
            'status': self._classificar_status_volume(volume_medio),
            'descricao': 'Baseado no volume útil médio dos reservatórios'
        }
        
        # 2. Pressão sobre Preços (0-100)
        pld_medio = ccee_processed.get('estatisticas_gerais', {}).get('media', 150)
        pld_volatilidade = ccee_processed.get('estatisticas_gerais', {}).get('desvio_padrao', 0)
        
        pressao_precos = min(100, (100 - volume_medio) * (pld_medio / 250) + (pld_volatilidade / 10))
        
        indicators['pressao_precos'] = {
            'valor': pressao_precos,
            'status': 'ALTA' if pressao_precos > 70 else 'MODERADA' if pressao_precos > 40 else 'BAIXA',
            'pld_medio': pld_medio,
            'pld_volatilidade': pld_volatilidade
        }
        
        # 3. Atração para Investimentos (0-100)
        crescimento_esperado = 3.0  # % ao ano (valor padrão)
        atracao_investimento = min(100, (crescimento_esperado * 5) * (pld_medio / 150))
        
        indicators['atracao_investimento'] = {
            'valor': atracao_investimento,
            'status': 'ALTA' if atracao_investimento > 60 else 'MODERADA' if atracao_investimento > 30 else 'BAIXA',
            'descricao': 'Indicador de atratividade para novos investimentos em geração'
        }
        
        # 4. Risco Operacional
        subsistemas_criticos = 0
        if 'por_subsistema' in ons_processed:
            for data in ons_processed['por_subsistema'].values():
                if data.get('volume_util_medio', 100) < 40:
                    subsistemas_criticos += 1
        
        indicators['risco_operacional'] = {
            'valor': subsistemas_criticos,
            'status': 'ALTO' if subsistemas_criticos >= 2 else 'MODERADO' if subsistemas_criticos == 1 else 'BAIXO',
            'subsistemas_criticos': subsistemas_criticos
        }
        
        return indicators
    
    def _prepare_dashboard_data(self, ccee_processed: Dict, ons_processed: Dict) -> Dict:
        """Prepara dados simplificados para dashboard"""
        dashboard = {
            'timestamp': datetime.now().isoformat(),
            'indicadores_simples': {},
            'graficos': {}
        }
        
        # Indicadores simples
        if 'estatisticas_gerais' in ccee_processed:
            stats = ccee_processed['estatisticas_gerais']
            dashboard['indicadores_simples']['pld_medio'] = stats.get('media', 0)
            dashboard['indicadores_simples']['pld_variacao'] = stats.get('coeficiente_variacao', 0)
        
        if 'por_subsistema' in ons_processed:
            volumes = []
            for subsis, data in ons_processed['por_subsistema'].items():
                volumes.append(data.get('volume_util_medio', 0))
                
                # Adiciona por subsistema
                dashboard['indicadores_simples'][f'volume_{subsis.lower().replace(" ", "_")}'] = \
                    data.get('volume_util_medio', 0)
            
            if volumes:
                dashboard['indicadores_simples']['volume_medio_sin'] = sum(volumes) / len(volumes)
        
        # Dados para gráficos
        dashboard['graficos'] = {
            'volume_por_subsistema': ons_processed.get('por_subsistema', {}),
            'pld_por_submercado': ccee_processed.get('por_submercado', {}),
            'tendencias': ccee_processed.get('tendencias', {})
        }
        
        return dashboard
    
    # ==================== MÓDULO DE PERSISTÊNCIA ====================
    
    def save_ccee_data(self, raw_data: List, processed_data: Dict):
        """Salva dados da CCEE"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Salva raw
        with open(f"{self.data_dir}/raw/ccee_raw_{timestamp}.json", 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, ensure_ascii=False, indent=2)
        
        # Salva processed
        with open(f"{self.data_dir}/processed/ccee_processed_{timestamp}.json", 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=2)
        
        # Salva CSV
        df = pd.DataFrame(raw_data)
        df.to_csv(f"{self.data_dir}/raw/ccee_{timestamp}.csv", index=False, encoding='utf-8-sig')
        
        print(f"   💾 Dados CCEE salvos: ccee_processed_{timestamp}.json")
    
    def save_ons_data(self, raw_data: List, processed_data: Dict):
        """Salva dados do ONS"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Salva raw
        with open(f"{self.data_dir}/raw/ons_raw_{timestamp}.json", 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, ensure_ascii=False, indent=2)
        
        # Salva processed
        with open(f"{self.data_dir}/processed/ons_processed_{timestamp}.json", 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=2)
        
        # Salva CSV
        df = pd.DataFrame(raw_data)
        df.to_csv(f"{self.data_dir}/raw/ons_{timestamp}.csv", index=False, encoding='utf-8-sig')
        
        print(f"   💾 Dados ONS salvos: ons_processed_{timestamp}.json")
    
    def save_integrated_data(self, integrated_data: Dict):
        """Salva dados integrados"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Salva completo
        with open(f"{self.data_dir}/integrated/kintuadi_integrated_{timestamp}.json", 'w', encoding='utf-8') as f:
            json.dump(integrated_data, f, ensure_ascii=False, indent=2)
        
        # Salva resumo para dashboard
        dashboard_data = integrated_data.get('dashboard_data', {})
        with open(f"{self.data_dir}/integrated/dashboard_{timestamp}.json", 'w', encoding='utf-8') as f:
            json.dump(dashboard_data, f, ensure_ascii=False, indent=2)
        
        # Atualiza latest
        with open(f"{self.data_dir}/integrated/latest.json", 'w', encoding='utf-8') as f:
            json.dump(integrated_data, f, ensure_ascii=False, indent=2)
        
        print(f"   💾 Dados integrados salvos: kintuadi_integrated_{timestamp}.json")
    
    # ==================== MÓDULO DE RELATÓRIO ====================
    
    def generate_report(self, integrated_data: Dict):
        """Gera relatório completo"""
        print("\n📋 GERANDO RELATÓRIO COMPLETO...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Relatório textual
        text_report = self._generate_text_report(integrated_data)
        
        # Salva relatório
        report_filename = f"{self.reports_dir}/relatorio_kintuadi_{timestamp}.txt"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(text_report)
        
        # Relatório executivo (resumido)
        exec_report = self._generate_executive_summary(integrated_data)
        exec_filename = f"{self.reports_dir}/resumo_executivo_{timestamp}.txt"
        with open(exec_filename, 'w', encoding='utf-8') as f:
            f.write(exec_report)
        
        print(f"   📄 Relatório salvo: {report_filename}")
        print(f"   📊 Resumo executivo: {exec_filename}")
        
        # Exibe resumo no console
        print("\n" + "=" * 70)
        print(exec_report)
        print("=" * 70)
        
        return report_filename
    
    def _generate_text_report(self, data: Dict) -> str:
        """Gera relatório textual completo"""
        report = []
        report.append("=" * 80)
        report.append("KINTUADI ENERGY SYSTEM - RELATÓRIO DE ANÁLISE")
        report.append("=" * 80)
        report.append(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        report.append(f"Versão: {data['metadata'].get('versao', '1.0')}")
        
        # Indicadores-chave
        if 'indicadores_chave' in data:
            report.append("\n📈 INDICADORES-CHAVE:")
            report.append("-" * 40)
            
            for nome, indicador in data['indicadores_chave'].items():
                if isinstance(indicador, dict):
                    valor = indicador.get('valor', 0)
                    status = indicador.get('status', 'N/A')
                    
                    if 'seguranca' in nome:
                        report.append(f"• Segurança Energética: {valor:.1f}/100 ({status})")
                    elif 'pressao' in nome:
                        report.append(f"• Pressão sobre Preços: {valor:.1f}/100 ({status})")
                    elif 'atracao' in nome:
                        report.append(f"• Atração para Investimentos: {valor:.1f}/100 ({status})")
                    elif 'risco' in nome:
                        subs_criticos = indicador.get('subsistemas_criticos', 0)
                        report.append(f"• Risco Operacional: {subs_criticos} subsistema(s) crítico(s) ({status})")
        
        # Análise integrada
        if 'analise_integrada' in data:
            analise = data['analise_integrada']
            report.append("\n🔗 ANÁLISE INTEGRADA:")
            report.append("-" * 40)
            
            report.append(f"• Correlação Volume-PLD: {analise.get('correlacao_volume_pld', 'N/A')}")
            report.append(f"• Pressão de Mercado: {analise.get('pressao_mercado', 0):.1f}/100")
            report.append(f"• Alerta Operacional: {'SIM' if analise.get('alerta_operacional') else 'NÃO'}")
            
            if analise.get('recomendacoes_estrategicas'):
                report.append("\n🎯 RECOMENDAÇÕES ESTRATÉGICAS:")
                for i, rec in enumerate(analise['recomendacoes_estrategicas'], 1):
                    report.append(f"  {i}. {rec}")
        
        # Dados ONS
        if 'dados_brutos' in data and data['dados_brutos'].get('ons_count', 0) > 0:
            report.append("\n💧 SITUAÇÃO DOS RESERVATÓRIOS (ONS):")
            report.append("-" * 40)
            report.append(f"• Total de reservatórios: {data['dados_brutos']['ons_count']}")
        
        # Dados CCEE
        if 'dados_brutos' in data and data['dados_brutos'].get('ccee_count', 0) > 0:
            report.append("\n💰 MERCADO DE ENERGIA (CCEE):")
            report.append("-" * 40)
            report.append(f"• Registros PLD coletados: {data['dados_brutos']['ccee_count']}")
        
        report.append("\n" + "=" * 80)
        report.append("📁 Dados completos disponíveis na estrutura de pastas:")
        report.append("  • data/raw/ - Dados brutos das APIs")
        report.append("  • data/processed/ - Dados processados")
        report.append("  • data/integrated/ - Dados integrados")
        report.append("  • reports/ - Relatórios gerados")
        
        return '\n'.join(report)
    
    def _generate_executive_summary(self, data: Dict) -> str:
        """Gera resumo executivo"""
        summary = []
        summary.append