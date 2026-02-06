# scripts/ccee_collector_v2.py - COM AUDITORIA
import requests
import pandas as pd
from datetime import datetime, timedelta, date
import logging
from typing import List, Dict, Optional
from .data_models import PLDData, DataMetadata
from .audit_logger import AuditLogger

logger = logging.getLogger(__name__)

class CCEEPLDCollector:
    """Coletor otimizado de dados PLD da CCEE com auditoria"""
    
    def __init__(self, cache_ttl_minutes: int = 60, enable_audit: bool = True):
        self.base_url = "https://dadosabertos.ccee.org.br/api/3/action"
        self.resource_id = "3f279d6b-1069-42f7-9b0a-217b084729c4"
        self.cache_ttl = cache_ttl_minutes
        self._cache = {}
        self._cache_time = {}
        
        # Sistema de auditoria
        self.enable_audit = enable_audit
        if enable_audit:
            self.audit_logger = AuditLogger()
    
    def collect_pld_data(self, days: int = 7) -> Dict:
        """Coleta dados PLD com auditoria completa"""
        
        metadata = DataMetadata(
            source="CCEE_PLD",
            collection_time=datetime.now().isoformat(),
            status="pending",
            records_processed=0
        )
        
        try:
            # Verifica cache
            cache_key = f"pld_{days}d"
            if self._is_cache_valid(cache_key):
                logger.info(f"Usando dados em cache: {cache_key}")
                return self._cache[cache_key]
            
            # 1. Busca dados brutos
            logger.info("Coletando dados brutos da CCEE...")
            raw_data = self._fetch_pld_data(days)
            
            if not raw_data:
                metadata.status = "error"
                metadata.error_message = "Nenhum dado coletado"
                return {"metadata": metadata.to_dict(), "data": []}
            
            # Auditoria: Salva dados brutos
            if self.enable_audit:
                self.audit_logger.save_raw_data(
                    source="CCEE_PLD",
                    raw_data=raw_data,
                    metadata={
                        'resource_id': self.resource_id,
                        'days_requested': days,
                        'collection_time': metadata.collection_time
                    }
                )
            
            # 2. Processa dados
            logger.info("Processando dados PLD...")
            pld_objects = self._create_pld_objects(raw_data)
            
            # Auditoria: Log da transformação
            if self.enable_audit:
                self.audit_logger.log_data_transformation(
                    source="CCEE",
                    raw_data=raw_data[:3],
                    processed_data=[p.to_dict() for p in pld_objects[:3]],
                    transformation="raw_json_to_pld_objects"
                )
            
            # 3. Calcula estatísticas
            stats = self._calculate_statistics(pld_objects)
            
            # 4. Valida anomalias
            self._validate_pld_anomalies(pld_objects, stats)
            
            # 5. Cria timeseries
            timeseries = self._create_timeseries(pld_objects, days)
            
            # Prepara resultado
            result = {
                "metadata": metadata,
                "data": [pld.to_dict() for pld in pld_objects],
                "statistics": stats,
                "timeseries": timeseries,
                "raw_data_sample": raw_data[:2]  # Para debug
            }
            
            # Atualiza metadados
            result["metadata"].status = "success"
            result["metadata"].records_processed = len(pld_objects)
            
            # Auditoria: Log da consolidação
            if self.enable_audit:
                self.audit_logger.log_consolidation(
                    sources=["CCEE_API"],
                    consolidated_data=result,
                    rules_applied=["date_parsing", "pld_calculation", "submarket_grouping", "timeseries_generation"]
                )
            
            # Atualiza cache
            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.now()
            
            logger.info(f"CCEE: Processados {len(pld_objects)} registros PLD")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro no coletor CCEE: {e}")
            metadata.status = "error"
            metadata.error_message = str(e)
            return {"metadata": metadata.to_dict(), "data": []}
    
    def _fetch_pld_data(self, days: int) -> List[Dict]:
        """Busca dados da API com paginação e logging"""
        all_records = []
        offset = 0
        limit = 500
        max_pages = 3
        
        for page in range(max_pages):
            try:
                params = {
                    "resource_id": self.resource_id,
                    "limit": limit,
                    "offset": offset,
                    "sort": "_id desc"
                }
                
                logger.debug(f"CCEE: Página {page + 1}, offset {offset}")
                
                response = requests.get(
                    f"{self.base_url}/datastore_search",
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Auditoria: Log da chamada API
                if self.enable_audit and page == 0:  # Log apenas primeira página
                    self.audit_logger.log_api_call(
                        source="CCEE_PLD",
                        url=f"{self.base_url}/datastore_search",
                        params=params,
                        response_status=response.status_code,
                        data_sample=data.get('result', {}).get('records', [])[:2]
                    )
                
                if not data.get("success", False):
                    logger.warning(f"CCEE: API retornou success=False na página {page + 1}")
                    break
                
                records = data["result"].get("records", [])
                
                if not records:
                    logger.info(f"CCEE: Nenhum registro na página {page + 1}")
                    break
                
                logger.info(f"CCEE: Página {page + 1}: {len(records)} registros")
                
                # Adiciona todos os registros
                all_records.extend(records)
                
                # Log do primeiro registro
                if page == 0 and records:
                    first = records[0]
                    logger.debug(f"Primeiro registro CCEE:")
                    logger.debug(f"  MES_REFERENCIA: {first.get('MES_REFERENCIA')}")
                    logger.debug(f"  DIA: {first.get('DIA')}")
                    logger.debug(f"  HORA: {first.get('HORA')}")
                    logger.debug(f"  PLD_HORA: {first.get('PLD_HORA')}")
                    logger.debug(f"  SUBMERCADO: {first.get('SUBMERCADO')}")
                
                # Se temos dados suficientes, para
                if len(all_records) >= 1000:
                    logger.info(f"CCEE: Coletados {len(all_records)} registros (suficiente)")
                    break
                
                # Se chegou ao fim
                if len(records) < limit:
                    break
                
                offset += limit
                
            except Exception as e:
                logger.error(f"CCEE: Erro na página {page + 1}: {e}")
                break
        
        logger.info(f"CCEE: Total bruto coletado: {len(all_records)} registros")
        return all_records
    
    def _create_pld_objects(self, raw_data: List[Dict]) -> List[PLDData]:
        """Converte dados brutos para objetos PLD com validação"""
        pld_objects = []
        validation_errors = []
        
        for i, record in enumerate(raw_data):
            try:
                # Obtém data do formato MES_REFERENCIA (AAAAMM) e DIA
                mes_ref = record.get("MES_REFERENCIA", "")
                dia = record.get("DIA", "")
                
                # Valida campos obrigatórios
                if not mes_ref or not dia:
                    validation_errors.append({
                        'index': i,
                        'erro': 'Campos MES_REFERENCIA ou DIA vazios',
                        'dados': {k: v for k, v in record.items() if k in ['MES_REFERENCIA', 'DIA', 'HORA', 'PLD_HORA']}
                    })
                    continue
                
                # Constrói data
                data_str = self._build_date_string(mes_ref, dia)
                
                # Obtém hora
                hora = record.get("HORA", 0)
                try:
                    hora_int = int(hora)
                    hora_str = f"{hora_int:04d}"
                except:
                    hora_str = "0000"
                
                # Converte hora (HHMM -> HH:MM)
                if len(hora_str) == 4:
                    hora_formatada = f"{hora_str[:2]}:{hora_str[2:]}"
                else:
                    hora_formatada = "00:00"
                
                # Converte PLD para float
                pld_raw = record.get("PLD_HORA", 0)
                try:
                    pld_valor = float(pld_raw)
                except:
                    pld_valor = 0.0
                
                # Valida PLD (normalmente entre 0-1000 R$/MWh)
                if pld_valor < 0 or pld_valor > 5000:
                    validation_errors.append({
                        'index': i,
                        'erro': f'PLD fora do range aceitável: {pld_valor}',
                        'dados': record
                    })
                    continue
                
                pld_obj = PLDData(
                    data=data_str,
                    hora=hora_formatada,
                    submercado=record.get("SUBMERCADO", "N/A"),
                    pld_valor=pld_valor,
                    periodo_comercializacao=str(record.get("PERIODO_COMERCIALIZACAO", "N/A"))
                )
                pld_objects.append(pld_obj)
                
            except (ValueError, TypeError, KeyError) as e:
                validation_errors.append({
                    'index': i,
                    'erro': str(e),
                    'dados': {k: v for k, v in record.items() if k in ['MES_REFERENCIA', 'DIA', 'HORA', 'PLD_HORA']}
                })
                continue
        
        # Log de validações
        if validation_errors:
            logger.warning(f"CCEE: {len(validation_errors)} erros de validação")
            for error in validation_errors[:3]:
                logger.debug(f"  Erro: {error}")
        
        logger.info(f"CCEE: {len(pld_objects)} registros processados com sucesso")
        return pld_objects
    
    def _build_date_string(self, mes_ref: str, dia: str) -> str:
        """Constrói string de data no formato YYYY-MM-DD com validação"""
        try:
            # Mes_ref deve ser AAAAMM (ex: 202602)
            if len(mes_ref) != 6 or not mes_ref.isdigit():
                logger.warning(f"CCEE: MES_REFERENCIA inválido: {mes_ref}")
                return datetime.now().strftime("%Y-%m-%d")
            
            ano = mes_ref[:4]
            mes = mes_ref[4:6]
            
            # Valida ano (deve ser entre 2020-2030)
            ano_int = int(ano)
            if ano_int < 2020 or ano_int > 2030:
                logger.warning(f"CCEE: Ano inválido: {ano}")
                return datetime.now().strftime("%Y-%m-%d")
            
            # Valida mês (1-12)
            mes_int = int(mes)
            if mes_int < 1 or mes_int > 12:
                logger.warning(f"CCEE: Mês inválido: {mes}")
                return datetime.now().strftime("%Y-%m-%d")
            
            # Dia pode vir como string (ex: "6")
            dia_str = str(dia).strip()
            if not dia_str.isdigit():
                logger.warning(f"CCEE: Dia não numérico: {dia}")
                dia_str = "1"
            
            dia_int = int(dia_str)
            if dia_int < 1 or dia_int > 31:
                logger.warning(f"CCEE: Dia inválido: {dia}")
                dia_str = "1"
            
            # Garante que dia tenha 2 dígitos
            dia_fmt = dia_str.zfill(2)
            
            return f"{ano}-{mes}-{dia_fmt}"
            
        except Exception as e:
            logger.warning(f"CCEE: Erro ao construir data: {e}")
            return datetime.now().strftime("%Y-%m-%d")
    
    def _calculate_statistics(self, pld_objects: List[PLDData]) -> Dict:
        """Calcula estatísticas dos dados PLD com detalhes"""
        if not pld_objects:
            return {}
        
        values = [pld.pld_valor for pld in pld_objects if pld.pld_valor > 0]
        
        if not values:
            return {}
        
        df = pd.Series(values)
        
        # Estatísticas detalhadas
        stats = {
            "geral": {
                "pld_medio": float(df.mean()),
                "pld_min": float(df.min()),
                "pld_max": float(df.max()),
                "pld_std": float(df.std()),
                "pld_mediana": float(df.median()),
                "pld_q1": float(df.quantile(0.25)),
                "pld_q3": float(df.quantile(0.75)),
                "quantidade": len(values),
                "distribuicao": {
                    "abaixo_100": len([v for v in values if v < 100]),
                    "entre_100_200": len([v for v in values if 100 <= v < 200]),
                    "entre_200_300": len([v for v in values if 200 <= v < 300]),
                    "acima_300": len([v for v in values if v >= 300])
                }
            }
        }
        
        # Por submercado
        submercados = {}
        for pld in pld_objects:
            sub = pld.submercado
            if sub not in submercados:
                submercados[sub] = []
            submercados[sub].append(pld.pld_valor)
        
        stats["por_submercado"] = {}
        for sub, valores in submercados.items():
            if valores:
                s = pd.Series(valores)
                stats["por_submercado"][sub] = {
                    "pld_medio": float(s.mean()),
                    "pld_min": float(s.min()),
                    "pld_max": float(s.max()),
                    "pld_std": float(s.std()),
                    "quantidade": len(valores),
                    "percentual_total": (len(valores) / len(values)) * 100
                }
        
        # Log das estatísticas
        logger.info(f"CCEE Estatísticas: PLD médio = R$ {stats['geral']['pld_medio']:.2f}/MWh")
        logger.info(f"  Range: R$ {stats['geral']['pld_min']:.2f} - R$ {stats['geral']['pld_max']:.2f}")
        
        return stats
    
    def _validate_pld_anomalies(self, pld_objects: List[PLDData], stats: Dict):
        """Valida anomalias nos dados PLD"""
        if not self.enable_audit:
            return
        
        pld_medio = stats.get('geral', {}).get('pld_medio', 0)
        
        # Alerta para PLD muito alto (> 400 R$/MWh)
        if pld_medio > 400:
            self.audit_logger.log_anomaly(
                source="CCEE",
                data_point="pld_medio_sistema",
                expected=(100, 300),  # Range esperado
                actual=pld_medio,
                severity="HIGH"
            )
        
        # Verifica valores extremos (> 1000 R$/MWh)
        extreme_values = [
            p for p in pld_objects 
            if p.pld_valor > 1000
        ]
        
        for pld in extreme_values[:3]:
            self.audit_logger.log_anomaly(
                source="CCEE",
                data_point=f"pld_extremo_{pld.submercado}",
                expected=(0, 500),
                actual=pld.pld_valor,
                severity="MEDIUM"
            )
    
    def _create_timeseries(self, pld_objects: List[PLDData], days: int) -> List[Dict]:
        """Cria série temporal para gráficos"""
        if not pld_objects:
            return []
        
        # Agrupa por data
        data_map = {}
        for pld in pld_objects:
            if pld.data not in data_map:
                data_map[pld.data] = []
            data_map[pld.data].append(pld.pld_valor)
        
        # Calcula estatísticas por dia
        timeseries = []
        for data_str, valores in sorted(data_map.items()):
            if valores:
                s = pd.Series(valores)
                timeseries.append({
                    "data": data_str,
                    "pld_medio": float(s.mean()),
                    "pld_min": float(s.min()),
                    "pld_max": float(s.max()),
                    "pld_std": float(s.std()),
                    "quantidade": len(valores)
                })
        
        # Filtra últimos N dias
        if days and timeseries:
            try:
                # Converte datas para ordenar
                timeseries_with_dates = []
                for item in timeseries:
                    try:
                        date_obj = datetime.strptime(item["data"], "%Y-%m-%d").date()
                        timeseries_with_dates.append((date_obj, item))
                    except:
                        continue
                
                # Ordena por data e pega os últimos N dias
                timeseries_with_dates.sort(key=lambda x: x[0])
                recent_items = timeseries_with_dates[-days:]
                return [item[1] for item in recent_items]
            except Exception as e:
                logger.warning(f"Erro ao filtrar timeseries: {e}")
        
        return timeseries[-days:] if days else timeseries
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Verifica se cache ainda é válido"""
        if cache_key not in self._cache or cache_key not in self._cache_time:
            return False
        
        cache_age = datetime.now() - self._cache_time[cache_key]
        return cache_age.total_seconds() < (self.cache_ttl * 60)
    
    def get_detailed_report(self) -> Dict:
        """Gera relatório detalhado da coleta"""
        data = self.collect_pld_data()
        
        if data['metadata'].status != 'success':
            return {"error": "Coleta não foi bem-sucedida"}
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "resumo": {
                "total_registros": data['statistics']['geral']['quantidade'],
                "pld_medio": data['statistics']['geral']['pld_medio'],
                "pld_min": data['statistics']['geral']['pld_min'],
                "pld_max": data['statistics']['geral']['pld_max'],
                "volatilidade": data['statistics']['geral']['pld_std']
            },
            "submercados": {},
            "distribuicao_precos": data['statistics']['geral']['distribuicao']
        }
        
        # Detalhes por submercado
        for subm, stats in data['statistics']['por_submercado'].items():
            report["submercados"][subm] = {
                "pld_medio": stats.get("pld_medio", 0),
                "registros": stats.get("quantidade", 0),
                "percentual": stats.get("percentual_total", 0)
            }
        
        # Timeseries resumida
        if data['timeseries']:
            report["evolucao_recente"] = data['timeseries'][-3:]  # Últimos 3 dias
        
        return report