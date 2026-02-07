# scripts/ons_collector_v2.py - COM AUDITORIA
import os
import requests
import pandas as pd
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from .data_models import ReservoirData, DataMetadata
from .audit_logger import AuditLogger

logger = logging.getLogger(__name__)

class ONSReservoirCollector:
    """Coletor otimizado de dados de reservatórios do ONS com auditoria"""
    
    def __init__(self, cache_ttl_minutes: int = 30, enable_audit: bool = True):
        self.base_url = "https://integra.ons.org.br/api"
        self.cache_ttl = cache_ttl_minutes
        self._cache = {}
        self._cache_time = {}

        self._energia_agora_endpoints = [
            "Geracao_SIN_Eolica_json",
            "Geracao_SIN_Hidraulica_json",
            "Geracao_SIN_Nuclear_json",
            "Geracao_SIN_Solar_json",
            "Geracao_SIN_Termica_json",
            "Geracao_Norte_Eolica_json",
            "Geracao_Norte_Hidraulica_json",
            "Geracao_Norte_Nuclear_json",
            "Geracao_Norte_Solar_json",
            "Geracao_Norte_Termica_json",
            "Geracao_Nordeste_Eolica_json",
            "Geracao_Nordeste_Hidraulica_json",
            "Geracao_Nordeste_Nuclear_json",
            "Geracao_Nordeste_Solar_json",
            "Geracao_Nordeste_Termica_json",
            "Geracao_Sudeste_Eolica_json",
            "Geracao_Sudeste_Hidraulica_json",
            "Geracao_Sudeste_Nuclear_json",
            "Geracao_Sudeste_Solar_json",
            "Geracao_Sudeste_Termica_json",
            "Geracao_Sul_Eolica_json",
            "Geracao_Sul_Hidraulica_json",
            "Geracao_Sul_Nuclear_json",
            "Geracao_Sul_Solar_json",
            "Geracao_Sul_Termica_json",
        ]
        self._carga_agora_endpoints = [
            "Carga_SIN_json",
            "Carga_Norte_json",
            "Carga_Nordeste_json",
            "Carga_SudesteECentroOeste_json",
            "Carga_Sul_json",
        ]
        self._open_data_datasets = [
            {
                "name": "Reservatórios",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/reservatorio/"
                "DicionarioDados_Reservatorio.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/reservatorio/"
                "RESERVATORIOS.csv",
            },
            {
                "name": "EAR Diário Reservatórios",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_reservatorio_di/"
                "DicionarioDados_EarPorReservatorio.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_reservatorio_di/"
                "EAR_DIARIO_RESERVATORIOS_2026.csv",
            },
            {
                "name": "ENA Diário Reservatórios",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_reservatorio_di/"
                "DicionarioDados_EnaPorReservatorio.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_reservatorio_di/"
                "ENA_DIARIO_RESERVATORIOS_2026.csv",
            },
            {
                "name": "Dados Hidrológicos Diários",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/dados_hidrologicos_di/"
                "DicionarioDados_DadosHidrologicosDiarios.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/dados_hidrologicos_di/"
                "DADOS_HIDROLOGICOS_RES_2026.csv",
            },
            {
                "name": "Dados Hidrológicos Horários",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/dados_hidrologicos_ho/"
                "DicionarioDados_DadosHidrologicosHorarios.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/dados_hidrologicos_ho/"
                "DADOS_HIDROLOGICOS_HO_2026_02.csv",
            },
            {
                "name": "EAR Diário REE",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_ree_di/"
                "DicionarioDados_EarPorResEquivalente.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_ree_di/"
                "EAR_DIARIO_REE_2026.csv",
            },
            {
                "name": "ENA Diário REE",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_ree_di/"
                "DicionarioDados_EnaPorResEquivalente.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_ree_di/"
                "ENA_DIARIO_REE_2026.csv",
            },
            {
                "name": "EAR Diário Subsistema",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_subsistema_di/"
                "DicionarioDados_EarPorSubsistema.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_subsistema_di/"
                "EAR_DIARIO_SUBSISTEMA_2026.csv",
            },
            {
                "name": "EAR Diário Bacia",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_bacia_di/"
                "DicionarioDados_EarPorBacia.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_bacia_di/"
                "EAR_DIARIO_BACIAS_2026.csv",
            },
            {
                "name": "ENA Diário Subsistema",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_subsistema_di/"
                "DicionarioDados_EnaPorSubsistema.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_subsistema_di/"
                "ENA_DIARIO_SUBSISTEMA_2026.csv",
            },
            {
                "name": "ENA Diário Bacia",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_bacia_di/"
                "DicionarioDados_EnaPorBacia.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_bacia_di/"
                "ENA_DIARIO_BACIAS_2026.csv",
            },
            {
                "name": "Volume Espera",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/res_volumeespera/"
                "DicionarioDados_VolumeEsperaRecomendado.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/res_volumeespera/"
                "RES_VOLUMEESPERA_2026.csv",
            },
            {
                "name": "Energia Vertida Turbinável",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/energia_vertida_turbinavel_ho/"
                "DicionarioDados_EnergiaVertidaTurbinavel.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/energia_vertida_turbinavel_ho/"
                "ENERGIA_VERTIDA_TURBINAVEL_2026_02.csv",
            },
            {
                "name": "Intercâmbio Nacional",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/intercambio_nacional_ho/"
                "DicionarioDados_Intercambio_Nacional.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/intercambio_nacional_ho/"
                "INTERCAMBIO_NACIONAL_2026.csv",
            },
            {
                "name": "Intercâmbio Internacional",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/intercambio_internacional_ho/"
                "DicionarioDados_Intercambio_Internacional.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/intercambio_internacional_ho/"
                "INTERCAMBIO_INTERNACIONAL_2026.csv",
            },
            {
                "name": "Intercâmbio por Modalidade",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/intercambio_modalidade_ho/"
                "DicionarioDados_Intercambio_Energia_Modalidade.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/intercambio_modalidade_ho/"
                "INTERCAMBIO_ENERGIA_MODALIDADE_2026.csv",
            },
            {
                "name": "CVU Usina Térmica",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/cvu_usitermica_se/"
                "DicionarioDados_CVU_UsinaTermica.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/cvu_usitermica_se/"
                "CVU_USINA_TERMICA_2026.csv",
            },
            {
                "name": "Capacidade Instalada",
                "dict_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/capacidade-geracao/"
                "DicionarioDados_Capacidade_Instalada_Geracao.json",
                "csv_url": "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/capacidade-geracao/"
                "CAPACIDADE_GERACAO.csv",
            },
        ]
        
        # Sistema de auditoria
        self.enable_audit = enable_audit
        if enable_audit:
            self.audit_logger = AuditLogger()
    
    def collect_reservoir_data(self) -> Dict:
        """Coleta dados de reservatórios com auditoria completa"""
        
        metadata = DataMetadata(
            source="ONS_RESERVATORIOS",
            collection_time=datetime.now().isoformat(),
            status="pending",
            records_processed=0
        )
        
        try:
            # Verifica cache
            cache_key = "reservoir_data"
            if self._is_cache_valid(cache_key):
                logger.info(f"Usando dados em cache: {cache_key}")
                return self._cache[cache_key]
            
            # 1. Busca dados brutos
            logger.info("Coletando dados brutos do ONS...")
            raw_data = self._fetch_reservoir_data()
            
            if not raw_data:
                metadata.status = "error"
                metadata.error_message = "Nenhum dado coletado"
                return {"metadata": metadata.to_dict(), "data": []}
            
            # Auditoria: Salva dados brutos
            if self.enable_audit:
                self.audit_logger.save_raw_data(
                    source="ONS_RESERVATORIOS",
                    raw_data=raw_data,
                    metadata={
                        'url': f"{self.base_url}/energiaagora/Get/SituacaoDosReservatorios",
                        'collection_time': metadata.collection_time
                    }
                )
            
            # 2. Processa dados
            logger.info("Processando dados dos reservatórios...")
            reservoir_objects = self._create_reservoir_objects(raw_data)
            
            # Auditoria: Log da transformação
            if self.enable_audit:
                self.audit_logger.log_data_transformation(
                    source="ONS",
                    raw_data=raw_data[:3],  # Amostra
                    processed_data=[r.to_dict() for r in reservoir_objects[:3]],
                    transformation="raw_json_to_reservoir_objects"
                )
            
            # 3. Calcula estatísticas
            stats = self._calculate_reservoir_statistics(reservoir_objects)
            ear_ree_volume = self._calculate_ear_ree_volume_percent()
            if ear_ree_volume is not None:
                stats["geral"]["volume_medio_sistema_ear_ree"] = ear_ree_volume
                stats["geral"]["volume_medio"] = ear_ree_volume
                stats["geral"]["status_sistema"] = self._determine_system_status(ear_ree_volume)
            
            # 4. Valida anomalias
            self._validate_data_anomalies(reservoir_objects, stats)
            
            # Prepara resultado
            result = {
                "metadata": metadata,
                "data": [res.to_dict() for res in reservoir_objects],
                "statistics": stats,
                "subsistemas": self._group_by_subsistema(reservoir_objects),
                "raw_data_sample": raw_data[:2]  # Para debug
            }
            
            # Atualiza metadados
            result["metadata"].status = "success"
            result["metadata"].records_processed = len(reservoir_objects)
            
            # Auditoria: Log da consolidação
            if self.enable_audit:
                self.audit_logger.log_consolidation(
                    sources=["ONS_API"],
                    consolidated_data=result,
                    rules_applied=["volume_calculation", "status_determination", "subsystem_grouping"]
                )
            
            # Atualiza cache
            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.now()
            
            logger.info(f"ONS: Coletados {len(reservoir_objects)} reservatórios")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro no coletor ONS: {e}")
            metadata.status = "error"
            metadata.error_message = str(e)
            return {"metadata": metadata.to_dict(), "data": []}

    def collect_energia_agora(self, limit: int = 3) -> Dict[str, Dict]:
        """Coleta amostras de geração da API Energia Agora."""
        return self._collect_energy_series(self._energia_agora_endpoints, limit)

    def collect_carga_agora(self, limit: int = 3) -> Dict[str, Dict]:
        """Coleta amostras de carga da API Energia Agora."""
        return self._collect_energy_series(self._carga_agora_endpoints, limit)

    def collect_balanco_energetico(self) -> Dict:
        """Coleta o balanço energético consolidado."""
        endpoint = f"{self.base_url}/energiaagora/GetBalancoEnergeticoConsolidado/null"
        headers = {"accept": "application/json"}
        try:
            response = requests.get(endpoint, headers=headers, timeout=30)
            if response.status_code == 204:
                return {"success": True, "records": [], "status_code": 204}
            response.raise_for_status()
            return {"success": True, "records": response.json(), "status_code": response.status_code}
        except Exception as exc:
            logger.error(f"Erro ao buscar balanço energético: {exc}")
            return {"success": False, "error": str(exc)}

    def collect_open_data_csv(self, limit: int = 500) -> Dict[str, Dict[str, Any]]:
        """Coleta datasets ONS via links CSV diretos."""
        datasets = {}
        os.makedirs("data/ons_open_data", exist_ok=True)
        for dataset in self._open_data_datasets:
            csv_url = dataset.get("csv_url")
            if csv_url:
                self._download_csv_file(csv_url, "data/ons_open_data")
            datasets[dataset["name"]] = self._fetch_open_data_csv(dataset, limit=limit)
        return datasets

    def _fetch_open_data_csv(self, dataset: Dict[str, str], limit: int = 500) -> Dict[str, Any]:
        csv_url = dataset.get("csv_url")
        if not csv_url:
            return {"success": False, "error": "CSV url ausente", "records": []}
        try:
            df = pd.read_csv(
                csv_url,
                nrows=limit,
                sep=";",
                encoding="latin1",
                on_bad_lines="skip",
            )
        except Exception as exc:
            logger.error(f"Erro ao ler CSV ONS {dataset.get('name')}: {exc}")
            return {"success": False, "error": str(exc), "records": []}

        return {
            "success": True,
            "records": df.to_dict(orient="records"),
            "columns": list(df.columns),
            "source_url": csv_url,
            "dictionary_url": dataset.get("dict_url"),
            "sample_size": len(df),
        }

    def _download_csv_file(self, csv_url: str, output_dir: str) -> Optional[str]:
        filename = os.path.basename(csv_url.split("?")[0])
        if not filename:
            return None
        output_path = os.path.join(output_dir, filename)
        try:
            response = requests.get(csv_url, timeout=60)
            response.raise_for_status()
            with open(output_path, "wb") as file:
                file.write(response.content)
            return output_path
        except Exception as exc:
            logger.error(f"Erro ao baixar CSV ONS {csv_url}: {exc}")
            return None

    def _collect_energy_series(self, endpoints: List[str], limit: int = 3) -> Dict[str, Dict]:
        results = {}
        base_url = f"{self.base_url}/energiaagora/Get"
        headers = {"accept": "application/json"}

        for endpoint in endpoints:
            url = f"{base_url}/{endpoint}"
            try:
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 204:
                    results[endpoint] = {"success": True, "records": [], "status_code": 204}
                    continue
                response.raise_for_status()
                data = response.json()
                records = data[:limit] if isinstance(data, list) else data
                results[endpoint] = {"success": True, "records": records, "status_code": response.status_code}
            except Exception as exc:
                logger.error(f"Erro ao buscar {endpoint}: {exc}")
                results[endpoint] = {"success": False, "error": str(exc)}

        return results
    
    def _fetch_reservoir_data(self) -> List[Dict]:
        """Busca dados da API do ONS com logging detalhado"""
        endpoint = f"{self.base_url}/energiaagora/Get/SituacaoDosReservatorios"
        
        try:
            headers = {"accept": "application/json"}
            logger.debug(f"Chamando API ONS: {endpoint}")
            
            response = requests.get(endpoint, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Auditoria: Log da chamada API
            if self.enable_audit:
                self.audit_logger.log_api_call(
                    source="ONS_RESERVATORIOS",
                    url=endpoint,
                    params={},
                    response_status=response.status_code,
                    data_sample=data[:2] if isinstance(data, list) else data
                )
            
            if isinstance(data, list):
                logger.info(f"ONS: Recebidos {len(data)} registros brutos")
                
                # Log detalhado do primeiro registro
                if data:
                    first_record = data[0]
                    logger.debug(f"Primeiro registro ONS: {first_record.get('ReservatorioNome', 'N/A')}")
                    logger.debug(f"  Volume: {first_record.get('ReservatorioPorcentagem', 'N/A')}%")
                    logger.debug(f"  Subsistema: {first_record.get('Subsistema', 'N/A')}")
                
                return data
            else:
                logger.warning(f"Formato inesperado de resposta ONS: {type(data)}")
                return []
                
        except Exception as e:
            logger.error(f"Erro ao buscar dados ONS: {e}")
            return []
    
    def _create_reservoir_objects(self, raw_data: List[Dict]) -> List[ReservoirData]:
        """Converte dados brutos para objetos ReservoirData com validação"""
        reservoir_objects = []
        validation_errors = []
        
        for i, record in enumerate(raw_data):
            try:
                # Obtém nome do reservatório
                nome = record.get("ReservatorioNome", f"Desconhecido_{i}")
                
                # Converte porcentagem de volume
                volume_raw = record.get("ReservatorioPorcentagem", 0)
                volume_percent = self._safe_float(volume_raw)
                
                # Valida volume
                if volume_percent < 0 or volume_percent > 100:
                    validation_errors.append({
                        'reservatorio': nome,
                        'campo': 'ReservatorioPorcentagem',
                        'valor': volume_raw,
                        'valor_convertido': volume_percent,
                        'erro': 'Volume fora do range 0-100%'
                    })
                    continue  # Pula reservatórios inválidos
                
                # Converte volume útil
                volume_util = self._safe_float(record.get("ReservatorioVolumeUtil", 0))
                
                # Converte energia armazenada
                energia = self._safe_float(record.get("ReservatorioEARVerificadaMWMes", 0))
                
                # Obtém subsistema
                subsistema = record.get("Subsistema", "N/A")
                
                reservoir_obj = ReservoirData(
                    nome=nome,
                    subsistema=subsistema,
                    volume_percentual=volume_percent,
                    volume_util=volume_util,
                    energia_armazenada=energia,
                    data_atualizacao=datetime.now().isoformat()
                )
                reservoir_objects.append(reservoir_obj)
                
            except (ValueError, TypeError, KeyError) as e:
                validation_errors.append({
                    'reservatorio': record.get('ReservatorioNome', f'Index_{i}'),
                    'erro': str(e),
                    'dados': {k: v for k, v in record.items() if k in ['ReservatorioNome', 'Subsistema', 'ReservatorioPorcentagem']}
                })
                continue
        
        # Log de validações
        if validation_errors:
            logger.warning(f"ONS: {len(validation_errors)} erros de validação")
            for error in validation_errors[:3]:  # Mostra apenas os 3 primeiros
                logger.debug(f"  Erro: {error}")
        
        return reservoir_objects
    
    def _safe_float(self, value) -> float:
        """Converte valor para float de forma segura"""
        if value is None:
            return 0.0
        
        try:
            if isinstance(value, str):
                # Remove vírgula decimal e converte
                value = value.replace(",", ".")
                # Remove caracteres não numéricos (exceto ponto e sinal)
                value = ''.join(c for c in value if c.isdigit() or c in '.-')
                return float(value)
            else:
                return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def _calculate_reservoir_statistics(self, reservoirs: List[ReservoirData]) -> Dict:
        """Calcula estatísticas dos reservatórios com detalhes"""
        if not reservoirs:
            return {}
        
        volumes = [r.volume_percentual for r in reservoirs if r.volume_percentual > 0]
        volume_utils = [r.volume_util for r in reservoirs if r.volume_util > 0]
        
        if not volumes:
            return {}
        
        df = pd.Series(volumes)
        volume_medio_ponderado = self._calculate_weighted_volume_medio(reservoirs)
        volume_util_total = sum(volume_utils)
        volume_medio_base = volume_medio_ponderado if volume_medio_ponderado is not None else float(df.mean())
        
        # Estatísticas detalhadas
        stats = {
            "geral": {
                "volume_medio": float(volume_medio_base),
                "volume_medio_simples": float(df.mean()),
                "volume_medio_ponderado": float(volume_medio_ponderado) if volume_medio_ponderado is not None else None,
                "volume_util_total": float(volume_util_total) if volume_util_total > 0 else None,
                "volume_min": float(df.min()),
                "volume_max": float(df.max()),
                "volume_std": float(df.std()),
                "volume_mediana": float(df.median()),
                "total_reservatorios": len(reservoirs),
                "status_sistema": self._determine_system_status(volume_medio_base),
                "distribuicao": {
                    "abaixo_40%": len([v for v in volumes if v < 40]),
                    "entre_40_60%": len([v for v in volumes if 40 <= v < 60]),
                    "entre_60_80%": len([v for v in volumes if 60 <= v < 80]),
                    "acima_80%": len([v for v in volumes if v >= 80])
                }
            }
        }
        
        # Por subsistema
        stats["por_subsistema"] = {}
        for reservoir in reservoirs:
            sub = reservoir.subsistema
            if sub not in stats["por_subsistema"]:
                stats["por_subsistema"][sub] = {
                    "volumes": [],
                    "nomes": [],
                    "energias": []
                }
            stats["por_subsistema"][sub]["volumes"].append(reservoir.volume_percentual)
            stats["por_subsistema"][sub]["nomes"].append(reservoir.nome)
            stats["por_subsistema"][sub]["energias"].append(reservoir.energia_armazenada)
        
        # Calcula estatísticas por subsistema
        for sub, data in stats["por_subsistema"].items():
            if data["volumes"]:
                s = pd.Series(data["volumes"])
                e = pd.Series([e for e in data["energias"] if e > 0])
                
                stats["por_subsistema"][sub]["volume_medio"] = float(s.mean())
                stats["por_subsistema"][sub]["volume_min"] = float(s.min())
                stats["por_subsistema"][sub]["volume_max"] = float(s.max())
                stats["por_subsistema"][sub]["quantidade"] = len(data["volumes"])
                stats["por_subsistema"][sub]["status"] = self._determine_subsystem_status(s.mean())
                
                if len(e) > 0:
                    stats["por_subsistema"][sub]["energia_total"] = float(e.sum())
                    stats["por_subsistema"][sub]["energia_media"] = float(e.mean())
        
        # Log das estatísticas
        logger.info(f"ONS Estatísticas: Volume médio = {stats['geral']['volume_medio']:.1f}%")
        logger.info(f"  Distribuição: <40%: {stats['geral']['distribuicao']['abaixo_40%']}, 40-60%: {stats['geral']['distribuicao']['entre_40_60%']}")
        
        return stats

    def _calculate_ear_ree_volume_percent(self) -> Optional[float]:
        dataset = next(
            (item for item in self._open_data_datasets if item["name"] == "EAR Diário REE"),
            None,
        )
        if not dataset:
            return None
        csv_url = dataset.get("csv_url")
        if not csv_url:
            return None
        try:
            df = pd.read_csv(
                csv_url,
                sep=";",
                encoding="latin1",
                on_bad_lines="skip",
            )
        except Exception as exc:
            logger.error(f"Erro ao ler EAR Diário REE: {exc}")
            return None

        required_columns = {"ear_data", "ear_max_ree", "ear_verif_ree_mwmes"}
        column_map = {str(col).lower(): col for col in df.columns}
        if not required_columns.issubset(column_map.keys()):
            logger.error("EAR Diário REE: colunas esperadas não encontradas.")
            return None
        df = df.rename(columns=column_map)

        df["ear_data"] = pd.to_datetime(df["ear_data"], errors="coerce")
        df = df.dropna(subset=["ear_data"])
        if df.empty:
            return None

        latest_date = df["ear_data"].max()
        latest = df[df["ear_data"] == latest_date].copy()
        latest["ear_verif_ree_mwmes"] = pd.to_numeric(
            latest["ear_verif_ree_mwmes"], errors="coerce"
        ).fillna(0)
        latest["ear_max_ree"] = pd.to_numeric(
            latest["ear_max_ree"], errors="coerce"
        ).fillna(0)
        total_verif = latest["ear_verif_ree_mwmes"].sum()
        total_max = latest["ear_max_ree"].sum()
        if total_max == 0:
            return None
        return (total_verif / total_max) * 100.0
    
    def _calculate_weighted_volume_medio(self, reservoirs: List[ReservoirData]) -> Optional[float]:
        """Calcula o volume médio ponderado pela capacidade estimada."""
        total_volume_util = 0.0
        total_capacidade = 0.0

        for reservoir in reservoirs:
            percent = reservoir.volume_percentual
            volume_util = reservoir.volume_util
            if percent <= 0 or volume_util <= 0:
                continue
            capacidade = volume_util / (percent / 100.0)
            total_volume_util += volume_util
            total_capacidade += capacidade

        if total_capacidade == 0:
            return None
        return (total_volume_util / total_capacidade) * 100.0
    
    def _validate_data_anomalies(self, reservoirs: List[ReservoirData], stats: Dict):
        """Valida anomalias nos dados"""
        if not self.enable_audit:
            return
        
        volume_medio = stats.get('geral', {}).get('volume_medio', 0)
        
        # Alerta para volume muito baixo (< 20%)
        if volume_medio < 20:
            self.audit_logger.log_anomaly(
                source="ONS",
                data_point="volume_medio_sistema",
                expected=(40, 80),  # Range esperado
                actual=volume_medio,
                severity="CRITICAL"
            )
        
        # Verifica reservatórios individuais críticos
        critical_reservoirs = [
            r for r in reservoirs 
            if r.volume_percentual < 10  # Reservatórios abaixo de 10%
        ]
        
        for res in critical_reservoirs[:5]:  # Limita a 5 para não poluir logs
            self.audit_logger.log_anomaly(
                source="ONS",
                data_point=f"reservatorio_{res.nome}",
                expected=(30, 100),
                actual=res.volume_percentual,
                severity="HIGH"
            )
    
    def _group_by_subsistema(self, reservoirs: List[ReservoirData]) -> Dict:
        """Agrupa reservatórios por subsistema"""
        groups = {}
        
        for reservoir in reservoirs:
            sub = reservoir.subsistema
            if sub not in groups:
                groups[sub] = []
            groups[sub].append(reservoir.to_dict())
        
        return groups
    
    def _determine_system_status(self, volume_medio: float) -> str:
        """Determina status do sistema baseado no volume médio"""
        if volume_medio < 20:
            return "EMERGÊNCIA"
        elif volume_medio < 40:
            return "CRÍTICO"
        elif volume_medio < 60:
            return "ALERTA"
        elif volume_medio < 70:
            return "ATENÇÃO"
        else:
            return "NORMAL"
    
    def _determine_subsystem_status(self, volume_medio: float) -> str:
        """Determina status do subsistema"""
        if volume_medio < 20:
            return "EMERGÊNCIA"
        elif volume_medio < 40:
            return "CRÍTICO"
        elif volume_medio < 50:
            return "ALERTA"
        elif volume_medio < 70:
            return "ATENÇÃO"
        else:
            return "NORMAL"
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Verifica se cache ainda é válido"""
        if cache_key not in self._cache or cache_key not in self._cache_time:
            return False
        
        cache_age = datetime.now() - self._cache_time[cache_key]
        return cache_age.total_seconds() < (self.cache_ttl * 60)
    
    def get_detailed_report(self) -> Dict:
        """Gera relatório detalhado da coleta"""
        data = self.collect_reservoir_data()
        
        if data['metadata'].status != 'success':
            return {"error": "Coleta não foi bem-sucedida"}
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "resumo": {
                "total_reservatorios": data['statistics']['geral']['total_reservatorios'],
                "volume_medio_sistema": data['statistics']['geral']['volume_medio'],
                "status_sistema": data['statistics']['geral']['status_sistema'],
                "reservatorios_criticos": data['statistics']['geral']['distribuicao']['abaixo_40%']
            },
            "subsistemas": {},
            "reservatorios_criticos": []
        }
        
        # Detalhes por subsistema
        for subsis, stats in data['statistics']['por_subsistema'].items():
            report["subsistemas"][subsis] = {
                "volume_medio": stats.get("volume_medio", 0),
                "quantidade": stats.get("quantidade", 0),
                "status": stats.get("status", "N/A")
            }
        
        # Lista reservatórios críticos (< 20%)
        for reservoir in data['data']:
            if reservoir.get('volume_percentual', 100) < 20:
                report["reservatorios_criticos"].append({
                    "nome": reservoir.get('nome', 'N/A'),
                    "subsistema": reservoir.get('subsistema', 'N/A'),
                    "volume": reservoir.get('volume_percentual', 0),
                    "energia_mw": reservoir.get('energia_armazenada', 0)
                })
        
        return report
