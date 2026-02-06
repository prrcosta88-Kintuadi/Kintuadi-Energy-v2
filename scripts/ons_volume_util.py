# scripts/ons_volume_util.py - VERSÃO CORRIGIDA
import requests
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional, Tuple
from .audit_logger import AuditLogger

logger = logging.getLogger(__name__)

class ONSVolumeUtilCollector:
    """Coletor de dados históricos de volume útil do ONS - VERSÃO CORRIGIDA"""
    
    # Mapeamento de origens disponíveis
    ORIGENS_VALIDAS = ["TRL", "SSC", "FTP", "ATR"]
    
    # Mapeamento de intervalos
    INTERVALOS_VALIDOS = ["H0", "DI"]
    
    def __init__(self, authenticator, enable_audit: bool = True):
        """
        Args:
            authenticator: Instância de ONSAuthenticator
            enable_audit: Ativar sistema de auditoria
        """
        self.auth = authenticator
        self.base_url = "https://integra.ons.org.br/api/hidrologia"
        self.enable_audit = enable_audit
        
        if enable_audit:
            self.audit_logger = AuditLogger()
        
        # Cache de reservatórios
        self._reservatorios_cache = None
        self._cache_time = None
        
        # Cache de dados históricos por reservatório
        self._historical_cache = {}
    
    def get_reservatorios_list(self, force_refresh: bool = False) -> List[Dict]:
        """Obtém lista de reservatórios disponíveis"""
        
        # Verifica cache (60 minutos para lista de reservatórios)
        if (not force_refresh and self._reservatorios_cache and self._cache_time and 
            (datetime.now() - self._cache_time).seconds < 3600):
            logger.debug("Usando cache de reservatórios")
            return self._reservatorios_cache
        
        endpoint = f"{self.base_url}/reservatorios"
        
        # CORREÇÃO: Usa quantidade=240 como no exemplo
        headers = self.auth.get_auth_headers_with_pagination(pagina=1, quantidade=240)
        
        if not headers:
            logger.error("Falha na autenticação ONS")
            return []
        
        try:
            logger.info("Buscando lista de reservatórios do ONS...")
            response = requests.get(endpoint, headers=headers, timeout=30)
            
            # Auditoria
            if self.enable_audit:
                self.audit_logger.log_api_call(
                    source="ONS_VOLUME_UTIL_LIST",
                    url=endpoint,
                    params={"pagina": 1, "quantidade": 240},
                    response_status=response.status_code,
                    data_sample=response.json() if response.status_code == 200 else None
                )
            
            if response.status_code == 200:
                data = response.json()
                
                # CORREÇÃO: A API pode retornar diferentes formatos
                if isinstance(data, list):
                    logger.info(f"Encontrados {len(data)} reservatórios")
                    self._reservatorios_cache = data
                    self._cache_time = datetime.now()
                    
                    # Salva dados brutos para auditoria
                    if self.enable_audit:
                        self.audit_logger.save_raw_data(
                            source="ONS_RESERVATORIOS_LIST",
                            raw_data=data,
                            metadata={
                                'url': endpoint,
                                'quantidade': len(data),
                                'autenticado': True,
                                'pagina': 1
                            }
                        )
                    
                    return data
                elif isinstance(data, dict):
                    # Tenta encontrar a lista em diferentes chaves
                    for key in ['data', 'result', 'reservatorios', 'items']:
                        if key in data and isinstance(data[key], list):
                            data_list = data[key]
                            logger.info(f"Encontrados {len(data_list)} reservatórios")
                            self._reservatorios_cache = data_list
                            self._cache_time = datetime.now()
                            return data_list
                    
                    logger.warning(f"Formato inesperado na resposta: {list(data.keys())}")
                    return []
                    
        except Exception as e:
            logger.error(f"Erro ao listar reservatórios: {e}")
        
        return []
    
    def get_volume_util_historico(self, reservatorio_id: str, 
                                 dias_hist: int = 7,
                                 intervalo: str = "DI",
                                 origem: str = "ATR") -> Dict:
        """
        Obtém dados históricos de volume útil - VERSÃO CORRIGIDA
        
        Args:
            reservatorio_id: ID do reservatório (ex: "10")
            dias_hist: Número de dias de histórico
            intervalo: "DI" (diário) ou "H0" (horário)
            origem: "TRL", "SSC", "FTP" ou "ATR"
        """
        
        # Valida parâmetros
        if intervalo not in self.INTERVALOS_VALIDOS:
            logger.warning(f"Intervalo inválido: {intervalo}. Usando 'DI'")
            intervalo = "DI"
        
        if origem not in self.ORIGENS_VALIDAS:
            logger.warning(f"Origem inválida: {origem}. Usando 'ATR'")
            origem = "ATR"
        
        # Calcula datas
        fim = datetime.now()
        inicio = fim - timedelta(days=dias_hist)
        
        endpoint = f"{self.base_url}/reservatorios/{reservatorio_id}/volumeUtil"
        
        # CORREÇÃO: Formato correto dos parâmetros
        params = {
            'Inicio': inicio.strftime('%Y-%m-%d %H:%M:%S'),
            'Fim': fim.strftime('%Y-%m-%d %H:%M:%S'),
            'Intervalo': intervalo,
            'Origem': origem
        }
        
        # CORREÇÃO: Usa headers com paginação
        headers = self.auth.get_auth_headers_with_pagination(pagina=1, quantidade=240)
        
        if not headers:
            logger.error("Falha na autenticação para volume histórico")
            return {
                'status': 'error',
                'error': 'Falha na autenticação',
                'data': []
            }
        
        try:
            logger.info(f"Buscando histórico para reservatório {reservatorio_id}...")
            logger.debug(f"Params: {params}")
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            
            # Auditoria
            if self.enable_audit:
                self.audit_logger.log_api_call(
                    source="ONS_VOLUME_UTIL_HIST",
                    url=endpoint,
                    params=params,
                    response_status=response.status_code,
                    data_sample=response.json() if response.status_code == 200 else None
                )
            
            if response.status_code == 200:
                data = response.json()
                
                # CORREÇÃO: A API pode retornar diferentes formatos
                if isinstance(data, list):
                    dados_lista = data
                elif isinstance(data, dict):
                    # Tenta extrair dados de diferentes estruturas
                    dados_lista = []
                    for key in ['data', 'result', 'volumeUtil', 'items', 'values']:
                        if key in data and isinstance(data[key], list):
                            dados_lista = data[key]
                            break
                    
                    if not dados_lista:
                        logger.warning(f"Formato inesperado: {list(data.keys())}")
                        dados_lista = []
                else:
                    dados_lista = []
                
                # Processa os dados
                dados_processados = self._process_volume_data(dados_lista)
                
                # Salva dados brutos para auditoria
                if self.enable_audit:
                    self.audit_logger.save_raw_data(
                        source=f"ONS_VOLUME_UTIL_{reservatorio_id}",
                        raw_data=data,
                        metadata={
                            'reservatorio_id': reservatorio_id,
                            'inicio': inicio.isoformat(),
                            'fim': fim.isoformat(),
                            'intervalo': intervalo,
                            'origem': origem,
                            'parametros': params
                        }
                    )
                
                # Atualiza cache
                cache_key = f"{reservatorio_id}_{intervalo}_{origem}_{dias_hist}"
                self._historical_cache[cache_key] = {
                    'data': dados_processados,
                    'timestamp': datetime.now()
                }
                
                return {
                    'status': 'success',
                    'reservatorio_id': reservatorio_id,
                    'periodo': {
                        'inicio': inicio.isoformat(),
                        'fim': fim.isoformat(),
                        'dias': dias_hist
                    },
                    'parametros': {
                        'intervalo': intervalo,
                        'origem': origem
                    },
                    'dados': dados_processados,
                    'metadata': {
                        'total_registros': len(dados_processados),
                        'intervalo': intervalo,
                        'origem': origem,
                        'coleta_timestamp': datetime.now().isoformat()
                    }
                }
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg = f"{error_msg}: {error_detail}"
                except:
                    pass
                
                logger.error(f"Erro HTTP {response.status_code} para reservatório {reservatorio_id}")
                return {
                    'status': 'error',
                    'error': error_msg,
                    'reservatorio_id': reservatorio_id,
                    'data': []
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout ao coletar dados do reservatório {reservatorio_id}")
            return {
                'status': 'error',
                'error': 'Timeout na requisição',
                'reservatorio_id': reservatorio_id,
                'data': []
            }
        except Exception as e:
            logger.error(f"Erro ao coletar volume histórico: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'reservatorio_id': reservatorio_id,
                'data': []
            }
    
    def _process_volume_data(self, raw_data: List) -> List[Dict]:
        """Processa dados brutos de volume útil"""
        processed = []
        
        for item in raw_data:
            if isinstance(item, dict):
                # Tenta extrair data e volume de diferentes formatos
                data_hora = None
                volume = None
                
                # Procura por campos comuns
                for date_key in ['dataHora', 'data', 'timestamp', 'DataHora', 'Data']:
                    if date_key in item:
                        data_hora = item[date_key]
                        break
                
                for vol_key in ['volumeUtil', 'volume', 'valor', 'VolumeUtil', 'Volume']:
                    if vol_key in item:
                        volume = item[vol_key]
                        break
                
                if data_hora and volume is not None:
                    try:
                        # Tenta converter volume para float
                        if isinstance(volume, str):
                            volume = float(volume.replace(',', '.'))
                        
                        processed.append({
                            'dataHora': data_hora,
                            'volumeUtil': float(volume),
                            'dados_completos': item
                        })
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Erro ao processar item: {e}")
                        continue
        
        return processed
    
    def get_volume_multiplas_origens(self, reservatorio_id: str, 
                                    dias_hist: int = 7) -> Dict:
        """Obtém dados de múltiplas origens para comparação"""
        
        resultados = {}
        
        for origem in self.ORIGENS_VALIDAS:
            logger.info(f"Coletando dados com origem {origem}...")
            dados = self.get_volume_util_historico(
                reservatorio_id=reservatorio_id,
                dias_hist=dias_hist,
                intervalo="DI",
                origem=origem
            )
            
            resultados[origem] = dados
        
        # Compara os resultados
        comparacao = self._compare_data_sources(resultados)
        
        return {
            'status': 'success',
            'reservatorio_id': reservatorio_id,
            'resultados_por_origem': resultados,
            'comparacao': comparacao
        }
    
    def _compare_data_sources(self, resultados: Dict) -> Dict:
        """Compara dados de diferentes origens"""
        comparacao = {}
        
        # Coleta médias por origem
        medias = {}
        for origem, resultado in resultados.items():
            if resultado['status'] == 'success' and resultado['dados']:
                volumes = [d['volumeUtil'] for d in resultado['dados'] if 'volumeUtil' in d]
                if volumes:
                    medias[origem] = sum(volumes) / len(volumes)
        
        if medias:
            # Calcula desvios
            media_geral = sum(medias.values()) / len(medias)
            comparacao['media_geral'] = media_geral
            comparacao['desvios'] = {}
            
            for origem, media in medias.items():
                desvio = ((media - media_geral) / media_geral * 100) if media_geral > 0 else 0
                comparacao['desvios'][origem] = {
                    'media': media,
                    'desvio_percentual': desvio,
                    'status': 'CONSISTENTE' if abs(desvio) < 5 else 'DIVERGENTE'
                }
        
        return comparacao
    
    def find_reservatorio_by_name(self, nome: str) -> List[Dict]:
        """Encontra reservatório pelo nome (parcial)"""
        
        reservatorios = self.get_reservatorios_list()
        
        if not reservatorios:
            return []
        
        encontrados = []
        nome_lower = nome.lower()
        
        for res in reservatorios:
            res_nome = res.get('nome', '')
            if isinstance(res_nome, str) and nome_lower in res_nome.lower():
                encontrados.append(res)
        
        return encontrados
    
    def get_reservatorio_info(self, reservatorio_id: str) -> Optional[Dict]:
        """Obtém informações detalhadas de um reservatório"""
        
        reservatorios = self.get_reservatorios_list()
        
        if not reservatorios:
            return None
        
        for res in reservatorios:
            if str(res.get('id')) == str(reservatorio_id):
                return res
        
        return None
    
    def analyze_trends_detailed(self, reservatorio_id: str, 
                               dias_hist: int = 30) -> Dict:
        """Análise detalhada de tendências com múltiplas origens"""
        
        # Obtém dados da origem principal (ATR)
        dados_principal = self.get_volume_util_historico(
            reservatorio_id=reservatorio_id,
            dias_hist=dias_hist,
            intervalo="DI",
            origem="ATR"
        )
        
        if dados_principal['status'] != 'success':
            return dados_principal
        
        # Converte para DataFrame para análise
        df_data = []
        for ponto in dados_principal['dados']:
            try:
                data_hora = datetime.fromisoformat(ponto['dataHora'].replace('Z', '+00:00'))
                df_data.append({
                    'data': data_hora.date(),
                    'data_hora': data_hora,
                    'volume': ponto['volumeUtil']
                })
            except:
                continue
        
        if not df_data:
            return {'status': 'error', 'error': 'Dados insuficientes para análise'}
        
        df = pd.DataFrame(df_data)
        
        if df.empty:
            return {'status': 'error', 'error': 'DataFrame vazio'}
        
        # Análise avançada
        analysis = {
            'status': 'success',
            'reservatorio_id': reservatorio_id,
            'periodo_dias': dias_hist,
            'estatisticas': {},
            'tendencias': {},
            'alertas': [],
            'analise_tecnica': {}
        }
        
        # Agrupa por dia se necessário
        if 'data' in df.columns:
            df_daily = df.groupby('data').agg({
                'volume': ['mean', 'min', 'max', 'std']
            }).round(2)
            
            df_daily.columns = ['media', 'minimo', 'maximo', 'desvio_padrao']
            df_daily = df_daily.reset_index()
            
            # Análise de tendência linear
            if len(df_daily) >= 3:
                x = range(len(df_daily))
                y = df_daily['media'].values
                
                # Regressão linear simples
                try:
                    coeff = np.polyfit(x, y, 1)
                    slope = coeff[0]  # Inclinação (tendência diária)
                    
                    analysis['tendencias']['linear'] = {
                        'inclinacao_diaria': float(slope),
                        'inclinacao_percentual_diaria': float((slope / y.mean()) * 100) if y.mean() > 0 else 0,
                        'direcao': 'ALTA' if slope > 0 else 'BAIXA',
                        'forca': 'FORTE' if abs(slope) > 0.5 else 'MODERADA' if abs(slope) > 0.2 else 'FRACA'
                    }
                except:
                    pass
        
        # Estatísticas básicas
        volumes = df['volume'].values
        analysis['estatisticas'] = {
            'media': float(volumes.mean()),
            'mediana': float(np.median(volumes)),
            'minimo': float(volumes.min()),
            'maximo': float(volumes.max()),
            'desvio_padrao': float(volumes.std()),
            'coeficiente_variacao': float((volumes.std() / volumes.mean()) * 100) if volumes.mean() > 0 else 0,
            'ultimo_valor': float(volumes[-1]),
            'primeiro_valor': float(volumes[0]),
            'variacao_periodo': float(volumes[-1] - volumes[0]),
            'variacao_percentual': float(((volumes[-1] - volumes[0]) / volumes[0]) * 100) if volumes[0] > 0 else 0
        }
        
        # Alertas baseados no último valor
        ultimo_volume = analysis['estatisticas']['ultimo_valor']
        
        if ultimo_volume < 10:
            analysis['alertas'].append({
                'nivel': 'EMERGÊNCIA',
                'codigo': 'VOL_EMERG',
                'mensagem': f'Volume em nível de emergência: {ultimo_volume:.1f}%',
                'volume': ultimo_volume,
                'limite': 10
            })
        elif ultimo_volume < 20:
            analysis['alertas'].append({
                'nivel': 'CRÍTICO',
                'codigo': 'VOL_CRIT',
                'mensagem': f'Volume em nível crítico: {ultimo_volume:.1f}%',
                'volume': ultimo_volume,
                'limite': 20
            })
        elif ultimo_volume < 40:
            analysis['alertas'].append({
                'nivel': 'ALERTA',
                'codigo': 'VOL_ALERT',
                'mensagem': f'Volume em alerta: {ultimo_volume:.1f}%',
                'volume': ultimo_volume,
                'limite': 40
            })
        
        # Análise de velocidade de variação
        variacao_diaria = analysis['tendencias'].get('linear', {}).get('inclinacao_diaria', 0)
        
        if variacao_diaria < -1:
            analysis['alertas'].append({
                'nivel': 'ALERTA',
                'codigo': 'DECL_RAPIDO',
                'mensagem': f'Declínio rápido detectado: {variacao_diaria:.2f}%/dia',
                'velocidade': variacao_diaria
            })
        
        # Projeção (simples)
        if variacao_diaria != 0:
            dias_ate_20 = (20 - ultimo_volume) / variacao_diaria if variacao_diaria < 0 else None
            dias_ate_10 = (10 - ultimo_volume) / variacao_diaria if variacao_diaria < 0 else None
            
            if dias_ate_20 and dias_ate_20 > 0:
                analysis['analise_tecnica']['projecao_20_percent'] = {
                    'dias_estimados': int(dias_ate_20),
                    'data_estimada': (datetime.now() + timedelta(days=dias_ate_20)).strftime('%Y-%m-%d'),
                    'confianca': 'BAIXA' if abs(variacao_diaria) < 0.1 else 'MEDIA' if abs(variacao_diaria) < 0.5 else 'ALTA'
                }
        
        return analysis

# Para análise técnica avançada
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("NumPy não instalado. Algumas análises estarão limitadas.")