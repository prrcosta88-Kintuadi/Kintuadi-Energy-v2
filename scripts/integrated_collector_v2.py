# scripts/integrated_collector_v2.py - CORREÇÃO
import json
import logging
from datetime import datetime
import os
from typing import Dict, Optional
from xml.etree.ElementTree import Element, ElementTree

logger = logging.getLogger(__name__)

class KintuadiIntegratedCollectorV2:
    """Coletor integrado versão 2.0 - Completamente reformulado"""
    
    def __init__(self):
        # Configura logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('logs/kintuadi.log')
            ]
        )
        
        # Cria diretórios necessários
        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        self.ons_collector = None
        self.ccee_collector = None
        self.analyzer = None
        self.ons_collector_v2 = None
        self.ccee_collector_v2 = None
        
        # Importa coletores otimizados
        try:
            from .ons_collector_v2 import ONSReservoirCollector
            from .ccee_collector_v2 import CCEEPLDCollector
            from .analyzer_v2 import EnergyMarketAnalyzer
            
            self.ons_collector = ONSReservoirCollector(cache_ttl_minutes=30, enable_audit=True)
            self.ccee_collector = CCEEPLDCollector(cache_ttl_minutes=60, enable_audit=True)
            self.analyzer = EnergyMarketAnalyzer()
            self.ons_collector_v2 = self.ons_collector
            self.ccee_collector_v2 = self.ccee_collector
            
            self.modules_loaded = True
            
        except Exception as e:
            logger.error(f"Erro ao carregar módulos: {e}")
            self.modules_loaded = False
    
    def collect_all(self) -> Optional[Dict]:
        """Executa coleta completa de dados"""
        
        if not self.modules_loaded:
            logger.error("Módulos não carregados. Verifique os imports.")
            return None
        if not self.ons_collector or not self.ccee_collector or not self.analyzer:
            logger.error("Coletores não inicializados. Verifique erros de importação.")
            return None
        
        logger.info("=" * 70)
        logger.info("⚡ KINTUADI ENERGY INTELLIGENCE v2.0")
        logger.info("=" * 70)
        logger.info(f"Início da coleta: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        
        try:
            results = {
                'metadata': {
                    'collection_start': datetime.now().isoformat(),
                    'version': '2.0.0',
                    'project': 'Kintuadi Energy Intelligence',
                    'modules_loaded': self.modules_loaded
                },
                'sources': {}
            }
            
            # 1. Coleta ONS
            logger.info("\n[1/3] Coletando dados do ONS...")
            ons_results = self.ons_collector.collect_reservoir_data()
            ons_results["open_data_csv"] = self.ons_collector.collect_open_data_csv(limit=500)
            results['sources']['ons'] = ons_results
            
            # CORREÇÃO: Acessa status corretamente
            if hasattr(ons_results['metadata'], 'status'):
                status = ons_results['metadata'].status
                if status == 'success':
                    records = ons_results['metadata'].records_processed
                    logger.info(f"✅ ONS: {records} reservatórios")
                else:
                    error_msg = ons_results['metadata'].error_message or 'Erro desconhecido'
                    logger.warning(f"⚠️ ONS: {error_msg}")
            else:
                logger.warning(f"⚠️ ONS: Estrutura de metadados inválida")
            
            # 2. Coleta CCEE
            logger.info("\n[2/3] Coletando dados da CCEE...")
            ccee_results = self.ccee_collector.collect_pld_data(days=7)
            ccee_results["open_data_csv"] = self.ccee_collector.collect_open_data_csv(limit=500)
            results['sources']['ccee'] = ccee_results
            
            # CORREÇÃO: Acessa status corretamente
            if hasattr(ccee_results['metadata'], 'status'):
                status = ccee_results['metadata'].status
                if status == 'success':
                    records = ccee_results['metadata'].records_processed
                    logger.info(f"✅ CCEE: {records} registros PLD")
                else:
                    error_msg = ccee_results['metadata'].error_message or 'Erro desconhecido'
                    logger.warning(f"⚠️ CCEE: {error_msg}")
            else:
                logger.warning(f"⚠️ CCEE: Estrutura de metadados inválida")
            
            # 3. Análise integrada
            logger.info("\n[3/3] Gerando análise de mercado...")
            analysis = self.analyzer.analyze_market(ons_results, ccee_results)
            
            # CORREÇÃO: Converte analysis para dict
            if hasattr(analysis, 'to_dict'):
                results['analysis'] = analysis.to_dict()
            else:
                results['analysis'] = analysis
            
            # 4. Status geral
            results['metadata']['collection_end'] = datetime.now().isoformat()
            try:
                start_time = datetime.fromisoformat(results['metadata']['collection_start'])
                end_time = datetime.fromisoformat(results['metadata']['collection_end'])
                results['metadata']['collection_duration'] = (end_time - start_time).total_seconds()
            except:
                results['metadata']['collection_duration'] = 0
            
            # Calcula status geral
            successful_sources = 0
            total_sources = len(results['sources'])
            
            for source_name, source_data in results['sources'].items():
                if hasattr(source_data.get('metadata', {}), 'status'):
                    if source_data['metadata'].status == 'success':
                        successful_sources += 1
            
            if successful_sources == total_sources:
                results['metadata']['overall_status'] = 'success'
                status_icon = '✅'
            elif successful_sources > 0:
                results['metadata']['overall_status'] = 'partial'
                status_icon = '⚠️'
            else:
                results['metadata']['overall_status'] = 'error'
                status_icon = '❌'
            
            # 5. Salva resultados
            logger.info("\n💾 Salvando resultados...")
            self._save_results(results)
            
            # 6. Log resumo
            self._log_summary(results)
            
            logger.info(f"\n{status_icon} COLETA CONCLUÍDA")
            logger.info(f"Status: {results['metadata']['overall_status'].upper()}")
            logger.info(f"Duração: {results['metadata']['collection_duration']:.1f}s")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ ERRO NA COLETA: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _save_results(self, data: Dict):
        """Salva resultados em arquivos"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Converte objetos para dict antes de salvar
            data_to_save = self._convert_objects_to_dict(data)
            
            # 1. Dados completos (para backup e análise)
            complete_file = f"data/kintuadi_complete_{timestamp}.json"
            with open(complete_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False, default=str)
            complete_xml_file = f"data/kintuadi_complete_{timestamp}.xml"
            self._save_xml(self._prepare_dashboard_xml_data(data_to_save), complete_xml_file, "kintuadi_complete")
            
            # 2. Dados para dashboard (formatado)
            dashboard_data = self._prepare_dashboard_data(data_to_save)
            dashboard_file = f"data/kintuadi_dashboard_{timestamp}.json"
            with open(dashboard_file, 'w', encoding='utf-8') as f:
                json.dump(dashboard_data, f, indent=2, ensure_ascii=False, default=str)
            
            dashboard_xml_file = f"data/kintuadi_dashboard_{timestamp}.xml"
            self._save_xml(self._prepare_dashboard_xml_data(dashboard_data), dashboard_xml_file, "kintuadi_dashboard")
            
            # 3. Atualiza arquivo latest
            latest_file = "data/kintuadi_latest.json"
            with open(latest_file, 'w', encoding='utf-8') as f:
                json.dump(dashboard_data, f, indent=2, ensure_ascii=False, default=str)
            latest_xml_file = "data/kintuadi_latest.xml"
            self._save_xml(self._prepare_dashboard_xml_data(dashboard_data), latest_xml_file, "kintuadi_dashboard")
            
            # 4. Log de sucesso
            success_file = f"data/kintuadi_success_{timestamp}.log"
            with open(success_file, 'w', encoding='utf-8') as f:
                f.write(f"Coleta concluída: {timestamp}\n")
                f.write(f"Status: {data['metadata']['overall_status']}\n")
                f.write(f"Arquivos gerados:\n")
                f.write(f"  - {complete_file}\n")
                f.write(f"  - {dashboard_file}\n")
                f.write(f"  - {dashboard_xml_file}\n")
                f.write(f"  - {latest_file}\n")
                f.write(f"  - {latest_xml_file}\n")
                f.write(f"  - {complete_xml_file}\n")
            
            logger.info(f"📁 Arquivos salvos:")
            logger.info(f"   • Completo: {complete_file}")
            logger.info(f"   • Dashboard: {dashboard_file}")
            logger.info(f"   • Latest: {latest_file}")
            logger.info(f"   • Dashboard XML: {dashboard_xml_file}")
            logger.info(f"   • Latest XML: {latest_xml_file}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar resultados: {e}")
    
    def _convert_objects_to_dict(self, data: Dict) -> Dict:
        """Converte todos os objetos para dicionários"""
        if isinstance(data, dict):
            return {k: self._convert_objects_to_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_objects_to_dict(v) for v in data]
        elif hasattr(data, 'to_dict'):
            return data.to_dict()
        elif hasattr(data, '__dict__'):
            return {k: self._convert_objects_to_dict(v) for k, v in data.__dict__.items()}
        else:
            return data
    
    def _save_xml(self, data: Dict, path: str, root_name: str) -> None:
        root = self._to_xml_element(root_name, data)
        tree = ElementTree(root)
        tree.write(path, encoding="utf-8", xml_declaration=True)

    def _to_xml_element(self, name: str, value) -> Element:
        tag = self._sanitize_xml_tag(name)
        element = Element(tag)
        if isinstance(value, dict):
            for key, item in value.items():
                element.append(self._to_xml_element(key, item))
        elif isinstance(value, list):
            for item in value:
                element.append(self._to_xml_element("item", item))
        else:
            element.text = "" if value is None else str(value)
        return element

    def _sanitize_xml_tag(self, tag: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in str(tag))
        if safe and safe[0].isdigit():
            safe = f"n_{safe}"
        return safe or "item"
    
    def _prepare_dashboard_data(self, data: Dict) -> Dict:
        """Prepara dados simplificados para o dashboard"""
        
        # Extrai dados das fontes
        ons_data = data.get('sources', {}).get('ons', {})
        ccee_data = data.get('sources', {}).get('ccee', {})
        analysis_data = data.get('analysis', {})
        
        # Converte metadados se necessário
        ons_metadata = ons_data.get('metadata', {})
        if hasattr(ons_metadata, 'to_dict'):
            ons_metadata = ons_metadata.to_dict()
        
        ccee_metadata = ccee_data.get('metadata', {})
        if hasattr(ccee_metadata, 'to_dict'):
            ccee_metadata = ccee_metadata.to_dict()
        
        # Estrutura otimizada para o dashboard
        dashboard_data = {
            'metadata': {
                'timestamp': data.get('metadata', {}).get('collection_end', datetime.now().isoformat()),
                'overall_status': data.get('metadata', {}).get('overall_status', 'unknown'),
                'collection_duration': data.get('metadata', {}).get('collection_duration', 0)
            },
            'ons': {
                'statistics': ons_data.get('statistics', {}),
                'subsistemas': ons_data.get('subsistemas', {}),
                'metadata': ons_metadata,
                'data_sample': ons_data.get('data', [])[:5],  # Amostra para debug
                'open_data_csv': ons_data.get('open_data_csv', {}),
            },
            'ccee': {
                'statistics': ccee_data.get('statistics', {}),
                'timeseries': ccee_data.get('timeseries', []),
                'metadata': ccee_metadata,
                'data_sample': ccee_data.get('data', [])[:5],  # Amostra para debug
                'open_data_csv': ccee_data.get('open_data_csv', {}),
            },
            'analysis': analysis_data
        }
        
        # Garante que todos os números sejam float
        def convert_numbers(obj):
            if isinstance(obj, dict):
                return {k: convert_numbers(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numbers(v) for v in obj]
            elif isinstance(obj, (int, float)):
                return float(obj)
            else:
                return obj
        
        return convert_numbers(dashboard_data)

    def _prepare_dashboard_xml_data(self, dashboard_data: Dict) -> Dict:
        normalized = self._normalize_for_xml(dashboard_data)
        return normalized if isinstance(normalized, dict) else {"data": normalized}

    def _normalize_for_xml(self, value):
        if isinstance(value, dict):
            return {key: self._normalize_for_xml(item) for key, item in value.items()}
        if isinstance(value, list):
            if value and all(isinstance(item, dict) for item in value):
                columns = list(value[0].keys())
                rows = [self._normalize_for_xml(item) for item in value]
                return {"columns": columns, "rows": rows}
            return [self._normalize_for_xml(item) for item in value]
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, (int, float)):
            return self._format_number(value)
        return value

    def _format_number(self, value):
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            text = f"{value:.6f}".rstrip("0").rstrip(".")
            return text.replace(".", ",")
        return str(value)
    
    def _log_summary(self, data: Dict):
        """Gera log resumido da coleta"""
        
        try:
            ons_stats = data.get('sources', {}).get('ons', {}).get('statistics', {}).get('geral', {})
            ccee_stats = data.get('sources', {}).get('ccee', {}).get('statistics', {}).get('geral', {})
            analysis = data.get('analysis', {})
            
            # Valores padrão
            volume_medio = ons_stats.get('volume_medio', 0)
            total_reservatorios = ons_stats.get('total_reservatorios', 0)
            status_sistema = ons_stats.get('status_sistema', 'N/A')
            
            pld_medio = ccee_stats.get('pld_medio', 0)
            pld_std = ccee_stats.get('pld_std', 0)
            quantidade_pld = ccee_stats.get('quantidade', 0)
            
            tendencia = analysis.get('tendencia_mercado', 'N/A')
            indice_seguranca = analysis.get('indice_seguranca', 0)
            alerta = analysis.get('alerta', False)
            
            summary = f"""
╔{'═'*60}╗
║{'RESUMO DA COLETA':^60}║
╠{'═'*60}╣
║ {'ONS:':<15} {total_reservatorios} reservatórios ║
║ {'Volume médio:':<15} {volume_medio:.1f}% ║
║ {'Status:':<15} {status_sistema:<42} ║
╠{'─'*60}╣
║ {'CCEE:':<15} {quantidade_pld} registros PLD ║
║ {'PLD médio:':<15} R$ {pld_medio:.2f}/MWh ║
║ {'Variação:':<15} R$ {pld_std:.2f}/MWh ║
╠{'─'*60}╣
║ {'ANÁLISE:':<15} {tendencia:<42} ║
║ {'Índice segurança:':<15} {indice_seguranca:.1f}/100 ║
║ {'Alerta:':<15} {'ATIVO' if alerta else 'INATIVO':<42} ║
╚{'═'*60}╝
            """
            
            logger.info(summary)
            
        except Exception as e:
            logger.warning(f"Erro ao gerar resumo: {e}")
    
    def quick_collect(self):
        """Coleta rápida com feedback no console"""
        print("🚀 Iniciando coleta rápida Kintuadi v2.0...")
        print("⏳ Isso pode levar alguns segundos...\n")
        
        results = self.collect_all()
        
        if results and results['metadata']['overall_status'] != 'error':
            print("\n✅ Coleta concluída!")
            
            # Mostra resumo simples
            ons_stats = results.get('sources', {}).get('ons', {}).get('statistics', {}).get('geral', {})
            ccee_stats = results.get('sources', {}).get('ccee', {}).get('statistics', {}).get('geral', {})
            
            print(f"📊 RESUMO:")
            print(f"  • ONS: {ons_stats.get('total_reservatorios', 0)} reservatórios")
            print(f"  • Volume médio: {ons_stats.get('volume_medio', 0):.1f}%")
            print(f"  • CCEE: {ccee_stats.get('quantidade', 0)} registros PLD")
            print(f"  • PLD médio: R$ {ccee_stats.get('pld_medio', 0):.2f}/MWh")
            
            print(f"\n📁 Dados disponíveis na pasta 'data/'")
            print(f"🌐 Execute o dashboard: streamlit run dashboard_integrado.py")
        else:
            print("\n❌ Falha na coleta. Verifique os logs em 'logs/kintuadi.log'")
        
        return results
