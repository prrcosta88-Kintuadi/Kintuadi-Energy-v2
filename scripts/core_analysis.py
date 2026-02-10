"""
Core analysis utilities for Kintuadi Energy.

CORE = visão sistêmica do SIN
- ONS (CSV) como fonte física primária
- CCEE como fonte econômica

VERSÃO REVISADA: Análise térmica com dupla perspectiva (sistema vs gerador)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json
import os

import pandas as pd
import numpy as np

# =====================================================================
# CONSTANTES REGULATÓRIAS - ANEEL/CCEE 2025
# =====================================================================
PLD_PISO = 57.31  # R$/MWh
PLD_TETO_ESTRUTURAL = 785.27  # R$/MWh (média semanal)
PLD_TETO_HORARIO = 1611.04  # R$/MWh (máximo horário)

# =====================================================================
# Utilities
# =====================================================================

def _safe_get(dct: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur = dct
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def _extract_sources(raw: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        "ons": raw.get("sources", {}).get("ons", {}),
        "ccee": raw.get("sources", {}).get("ccee", {}),
    }


def _find_ons_csv(ons: Dict[str, Any], dataset_name: str) -> Optional[str]:
    for ds in ons.get("datasets", []):
        if ds.get("dataset") == dataset_name:
            return ds.get("file")
    return None


def _extract_ccee_records(obj: Any) -> List[Dict[str, Any]]:
    if not obj:
        return []
    if isinstance(obj, dict):
        return obj.get("records", []) or obj.get("data", []) or []
    if isinstance(obj, list):
        return obj
    return []


def _status_from_records(records: List[Dict[str, Any]]) -> str:
    return "disponível" if records else "indisponível"


# =====================================================================
# Hidrologia
# =====================================================================

def _hydrology_status(ear: Optional[float]) -> Dict[str, Any]:
    if ear is None:
        return {"classe": "dados ausentes", "descricao": "EAR não disponível."}

    if ear < 40:
        c = "crítico"
    elif ear < 55:
        c = "alerta"
    elif ear < 70:
        c = "atenção"
    elif ear < 85:
        c = "confortável"
    else:
        c = "abundante"

    return {
        "classe": c,
        "descricao": "Classificação baseada no EAR médio dos subsistemas.",
    }


def _compute_hydrology_from_csv(ons: Dict[str, Any]) -> Dict[str, Any]:
    ear_file = _find_ons_csv(ons, "EAR_Diario_Subsistema")
    ena_file = _find_ons_csv(ons, "ENA_Diario_Subsistema")

    ear_medio = ena_media = tendencia = None

    try:
        if ear_file and os.path.exists(ear_file):
            df = pd.read_csv(ear_file, sep=None, engine="python")

            col = "ear_verif_subsistema_percentual"
            if col in df.columns:
                ear_medio = float(df[col].mean())

                recent = df.tail(7)[col].mean()
                past = df.tail(30)[col].mean()
                tendencia = float(recent - past) if past else None

        if ena_file and os.path.exists(ena_file):
            df = pd.read_csv(ena_file, sep=None, engine="python")
            col = "ena_verificada_mwmed"
            if col in df.columns:
                ena_media = float(df[col].mean())

    except Exception:
        pass

    return {
        "ear_medio": ear_medio,
        "ena_media": ena_media,
        "tendencia": tendencia,
        "classificacao": _hydrology_status(ear_medio),
    }


# =====================================================================
# Energia Agora (ONS) — SÉRIES HORÁRIAS
# =====================================================================

def _extract_energia_agora(ons: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processa geração e carga horária (Energia Agora).
    Retorna métricas + séries preservadas.
    """
    geracao = {}
    carga = {}

    for ds in ons.get("datasets", []):
        if ds.get("origin") != "energia_agora":
            continue

        name = ds.get("dataset", "").lower()
        file = ds.get("file")

        if not file or not os.path.exists(file):
            continue

        try:
            df = pd.read_csv(file)
            if "instante" not in df.columns:
                continue

            df["instante"] = pd.to_datetime(df["instante"])
            df = df.sort_values("instante")

            # ---------------- GERAÇÃO ----------------
            if name.startswith("geracao_") and "geracao" in df.columns:
                fonte = name.replace("geracao_", "")
                v = df["geracao"]

                geracao[fonte] = {
                    "media": float(v.mean()),
                    "max": float(v.max()),
                    "min": float(v.min()),
                    "rampa_max": float(v.diff().abs().max()),
                    "serie": df[["instante", "geracao"]].to_dict("records"),
                }

            # ---------------- CARGA ----------------
            if name.startswith("carga_") and "carga" in df.columns:
                area = name.replace("carga_", "")
                v = df["carga"]

                carga[area] = {
                    "media": float(v.mean()),
                    "max": float(v.max()),
                    "min": float(v.min()),
                    "rampa_max": float(v.diff().abs().max()),
                    "serie": df[["instante", "carga"]].to_dict("records"),
                }

        except Exception:
            continue

    status = "disponível" if (
        any(v.get("media", 0) > 0 for v in geracao.values()) or
        any(v.get("media", 0) > 0 for v in carga.values())
    ) else "indisponível"

    return {
        "generation": geracao,
        "load": carga,
        "status": status,
    }


# =====================================================================
# CCEE — Térmica / MCP
# =====================================================================

def compute_mcp_economico(
    pld_series: pd.Series,
    carga_series: pd.Series,
    geracao_hidraulica: pd.Series,
    cvu_medio: Optional[float]
) -> Dict[str, Any]:

    if pld_series.empty or carga_series.empty:
        return {"status": "indisponível"}

    stress_index = carga_series.mean() / max(geracao_hidraulica.mean(), 1)

    # Calcular correlações com tratamento de dados ausentes
    corr_pld_carga = None
    corr_pld_hidro = None
    
    try:
        # Alinhar séries temporais
        df_correl = pd.DataFrame({
            'pld': pld_series,
            'carga': carga_series.reindex(pld_series.index).ffill().bfill(),
            'hidro': geracao_hidraulica.reindex(pld_series.index).ffill().bfill()
        }).dropna()
        
        if len(df_correl) > 2:  # Mínimo de pontos para correlação
            corr_pld_carga = float(df_correl['pld'].corr(df_correl['carga']))
            corr_pld_hidro = float(df_correl['pld'].corr(df_correl['hidro']))
    except Exception:
        pass

    # Determinar regime baseado no stress index
    if stress_index > 1.1:
        regime = "escassez estrutural"
    elif stress_index > 0.95:
        regime = "equilíbrio"
    else:
        regime = "excedente estrutural"

    # Determinar formação de preço
    if corr_pld_hidro is not None and abs(corr_pld_hidro) > 0.6:
        formacao_preco = "estrutural"
    elif corr_pld_hidro is not None and abs(corr_pld_hidro) > 0.3:
        formacao_preco = "mista"
    else:
        formacao_preco = "conjuntural"

    # Determinar posição térmica - AGORA USANDO A NOVA LÓGICA
    pld_medio = pld_series.mean() if not pld_series.empty else None
    
    # Usar a nova análise térmica para determinar posição
    posicao_termica = "indeterminada"
    if cvu_medio is not None and pld_medio is not None and pld_medio > 0:
        razao_cvu_pld = cvu_medio / pld_medio
        percentual_cvu_pld = razao_cvu_pld * 100
        
        if percentual_cvu_pld > 150:
            posicao_termica = "folga_estrutural"
        elif percentual_cvu_pld >= 100:
            posicao_termica = "risco_custo"
        elif percentual_cvu_pld >= 95:
            posicao_termica = "pressão_moderada"
        else:
            posicao_termica = "folga_operacional"

    return {
        "status": "disponível",
        "stress_index": float(stress_index),
        "correlacoes": {
            "pld_vs_carga": corr_pld_carga,
            "pld_vs_hidraulica": corr_pld_hidro,
        },
        "regime_mcp": regime,
        "interpretação": {
            "preço": formacao_preco,
            "térmica": posicao_termica,
        },
    }


# =====================================================================
# ANÁLISE TÉRMICA REVISADA (V5) - COM DUPLA PERSPECTIVA
# =====================================================================

def calcular_razao_cvu_pld(pld_medio: Optional[float], cvu_medio: Optional[float]) -> Optional[float]:
    """
    Calcula a razão CVU/PLD (indicador fundamental).
    
    Retorna:
    - < 0.8: CVU significativamente menor que PLD
    - 0.8-0.95: CVU próximo do PLD
    - 0.95-1.0: CVU muito próximo do PLD
    - 1.0-1.5: CVU maior que PLD
    - > 1.5: CVU muito maior que PLD (folga estrutural)
    """
    if pld_medio is None or cvu_medio is None or pld_medio <= 0:
        return None
    
    return cvu_medio / pld_medio


def calcular_margem_seguranca_sistema(pld_medio: Optional[float], cvu_medio: Optional[float]) -> Optional[float]:
    """
    Calcula margem de segurança do SISTEMA.
    
    Margem = ((PLD - CVU) / PLD) × 100%  se PLD > CVU
           = 0%                          se PLD <= CVU
    
    Interpretação (perspectiva do sistema):
    - > 20%: Margem adequada
    - 10-20%: Margem reduzida
    - 5-10%: Margem crítica
    - < 5%: Margem insuficiente
    - = 0%: CVU >= PLD (risco de custos)
    """
    if pld_medio is None or cvu_medio is None or pld_medio <= 0:
        return None
    
    if pld_medio > cvu_medio:
        return ((pld_medio - cvu_medio) / pld_medio) * 100
    else:
        return 0.0


def calcular_margem_vs_teto(cvu_medio: Optional[float]) -> Optional[float]:
    """
    Calcula margem de segurança em relação ao teto estrutural.
    
    Margem = ((Teto estrutural - CVU) / Teto estrutural) × 100%
    
    Interpretação:
    - > 5%: Margem adequada
    - 1-5%: Margem reduzida
    - < 1%: Margem crítica
    - <= 0%: Teto comprometido
    """
    if cvu_medio is None:
        return None
    
    return ((PLD_TETO_ESTRUTURAL - cvu_medio) / PLD_TETO_ESTRUTURAL) * 100


def calcular_viabilidade_termica(pld_medio: Optional[float], cvu_medio: Optional[float]) -> Dict[str, Any]:
    """
    Analisa viabilidade das térmicas (perspectiva do GERADOR).
    
    Retorna:
    - spread absoluto (R$/MWh)
    - viabilidade econômica (booleana)
    - classificação da perspectiva do gerador
    """
    if pld_medio is None or cvu_medio is None:
        return {
            "spread_absoluto": None,
            "viabilidade_economica": None,
            "perspectiva_gerador": "indisponível"
        }
    
    spread = pld_medio - cvu_medio
    
    if spread > 0:
        return {
            "spread_absoluto": spread,
            "viabilidade_economica": True,
            "perspectiva_gerador": "competitiva",
            "descricao": "Despacho economicamente viável para térmicas"
        }
    else:
        return {
            "spread_absoluto": spread,
            "viabilidade_economica": False,
            "perspectiva_gerador": "estrutural",
            "descricao": "Despacho por necessidade do sistema (EAR baixo ou restrição)"
        }


def calcular_dependencia_termica_efetiva(
    razao_cvu_pld: Optional[float], 
    ear_medio: Optional[float]
) -> Optional[float]:
    """
    Calcula dependência térmica EFETIVA considerando contexto hídrico.
    
    Fórmula revisada: Dependência = max(0, (razao_cvu_pld - 0.8)) × (1 - EAR_normalizado)
    
    Onde:
    - razao_cvu_pld - 0.8: penaliza apenas quando CVU > 80% do PLD
    - 1 - EAR_normalizado: inverso da condição hídrica
    
    Interpretação:
    - Baixa (< 0.1): Sistema com folga
    - Moderada (0.1-0.3): Atenção
    - Alta (0.3-0.5): Dependência significativa
    - Crítica (> 0.5): Sistema altamente dependente
    """
    if razao_cvu_pld is None or ear_medio is None:
        return None
    
    # Só considera dependência se CVU > 80% do PLD
    excesso_sobre_limiar = max(0, razao_cvu_pld - 0.8)
    
    # Normaliza EAR (0-1)
    ear_norm = max(0, min(1, ear_medio / 100))
    
    # Dependência = excesso de custo × (1 - folga hídrica)
    dependencia = excesso_sobre_limiar * (1 - ear_norm)
    
    return dependencia


def calcular_indicadores_termicos_revisados(
    pld_medio: Optional[float], 
    cvu_medio: Optional[float], 
    ear_medio: Optional[float]
) -> Dict[str, Any]:
    """
    Calcula indicadores térmicos com DUPLA PERSPECTIVA.
    
    Versão V5: Correção do conceito - CVU alto vs PLD baixo = FOLGA, não risco.
    """
    
    # 1. CÁLCULOS FUNDAMENTAIS
    razao_cvu_pld = calcular_razao_cvu_pld(pld_medio, cvu_medio)
    percentual_cvu_pld = razao_cvu_pld * 100 if razao_cvu_pld is not None else None
    
    margem_seguranca = calcular_margem_seguranca_sistema(pld_medio, cvu_medio)
    margem_vs_teto = calcular_margem_vs_teto(cvu_medio)
    dependencia_efetiva = calcular_dependencia_termica_efetiva(razao_cvu_pld, ear_medio)
    
    # Análise de viabilidade do gerador
    analise_gerador = calcular_viabilidade_termica(pld_medio, cvu_medio)
    
    # 2. ANÁLISE DO SISTEMA (PERSPECTIVA DA MODICIDADE TARIFÁRIA)
    
    # Cenário 1: CVU muito maior que PLD → FOLGA ESTRUTURAL
    if percentual_cvu_pld and percentual_cvu_pld > 150:
        classificacao_sistema = "folga_estrutural"
        risco_sistêmico = "muito_baixo"
        descricao_sistema = (
            f"Sistema operando com folga ampla. "
            f"CVU (💰 {cvu_medio:.1f}) muito acima do PLD (💰 {pld_medio:.1f}) "
            f"indica térmicas fora do despacho econômico."
        )
        recomendacao_sistema = "Operação normal. Modicidade tarifária preservada."
    
    # Cenário 2: CVU entre 100-150% do PLD → RISCO DE CUSTOS
    elif percentual_cvu_pld and percentual_cvu_pld >= 100:
        classificacao_sistema = "risco_custo"
        risco_sistêmico = "alto" if ear_medio and ear_medio < 50 else "moderado"
        descricao_sistema = (
            f"Sistema pode requerer despacho térmico com prejuízo econômico. "
            f"CVU (R$ {cvu_medio:.1f}) ≥ PLD (R$ {pld_medio:.1f})."
        )
        if ear_medio and ear_medio < 50:
            recomendacao_sistema = (
                "Despacho térmico necessário por escassez hídrica. "
                "Monitorar impactos tarifários."
            )
        else:
            recomendacao_sistema = (
                "Avaliar necessidade real de despacho térmico. "
                "Considerar alternativas operacionais."
            )
    
    # Cenário 3: CVU entre 95-100% do PLD → PRESSÃO MODERADA
    elif percentual_cvu_pld and percentual_cvu_pld >= 95:
        classificacao_sistema = "pressão_moderada"
        risco_sistêmico = "moderado"
        descricao_sistema = (
            f"CVU (R$ {cvu_medio:.1f}) muito próximo do PLD (R$ {pld_medio:.1f}). "
            f"Térmicas próximas da competitividade econômica."
        )
        recomendacao_sistema = (
            "Acompanhar evolução da relação PLD-CVU. "
            "Preparar planos de contingência se necessário."
        )
    
    # Cenário 4: CVU entre 80-95% do PLD → ATENÇÃO
    elif percentual_cvu_pld and percentual_cvu_pld >= 80:
        classificacao_sistema = "atenção"
        risco_sistêmico = "baixo"
        descricao_sistema = (
            f"CVU (R$ {cvu_medio:.1f}) representa {percentual_cvu_pld:.0f}% do PLD. "
            f"Margem de segurança adequada."
        )
        recomendacao_sistema = "Monitoramento rotineiro. Sistema operando normalmente."
    
    # Cenário 5: CVU < 80% do PLD → FOLGA OPERACIONAL
    elif percentual_cvu_pld and percentual_cvu_pld < 80:
        classificacao_sistema = "folga_operacional"
        risco_sistêmico = "muito_baixo"
        descricao_sistema = (
            f"CVU (R$ {cvu_medio:.1f}) significativamente abaixo do PLD (R$ {pld_medio:.1f}). "
            f"Sistema com ampla folga em relação às térmicas."
        )
        recomendacao_sistema = "Operação confortável. Otimização de custos garantida."
    
    # Cenário 6: Dados insuficientes
    else:
        classificacao_sistema = "indisponível"
        risco_sistêmico = "indeterminado"
        descricao_sistema = "Dados insuficientes para análise térmica."
        recomendacao_sistema = "Aguardar disponibilidade de dados."
    
    # 3. CONTEXTUALIZAÇÃO HIDROLÓGICA
    if ear_medio is not None:
        if ear_medio > 70:
            contexto_hidrologico = "abundante"
            impacto_hidrologico = "mitigante"
        elif ear_medio > 55:
            contexto_hidrologico = "confortável"
            impacto_hidrologico = "neutro"
        elif ear_medio > 40:
            contexto_hidrologico = "atenção"
            impacto_hidrologico = "agravante"
        else:
            contexto_hidrologico = "crítico"
            impacto_hidrologico = "fortemente_agravante"
    else:
        contexto_hidrologico = "indisponível"
        impacto_hidrologico = "indeterminado"
    
    return {
        # =============================================
        # INDICADORES QUANTITATIVOS
        # =============================================
        "indicadores_quantitativos": {
            "razao_cvu_pld": razao_cvu_pld,
            "percentual_cvu_pld": percentual_cvu_pld,
            "spread_absoluto": analise_gerador["spread_absoluto"],
            "margem_seguranca_sistema": margem_seguranca,
            "margem_vs_teto": margem_vs_teto,
            "dependencia_termica_efetiva": dependencia_efetiva,
        },
        
        # =============================================
        # ANÁLISE DO SISTEMA (MODICIDADE TARIFÁRIA)
        # =============================================
        "analise_sistema": {
            "classificacao": classificacao_sistema,
            "risco_sistêmico": risco_sistêmico,
            "descricao": descricao_sistema,
            "recomendacao": recomendacao_sistema,
            "interpretacao": f"CVU representa {percentual_cvu_pld:.0f}% do PLD" if percentual_cvu_pld else "N/A"
        },
        
        # =============================================
        # ANÁLISE DO GERADOR TÉRMICO
        # =============================================
        "analise_gerador": analise_gerador,
        
        # =============================================
        # CONTEXTO HIDROLÓGICO
        # =============================================
        "contexto_hidrologico": {
            "ear_medio": ear_medio,
            "classificacao_hidrologica": contexto_hidrologico,
            "impacto_pressao_termica": impacto_hidrologico,
            "dependencia_efetiva": dependencia_efetiva,
            "interpretacao": (
                f"EAR {ear_medio:.1f}% ({contexto_hidrologico}) "
                f"{'agravando' if impacto_hidrologico in ['agravante', 'fortemente_agravante'] else 'mitigando'} "
                f"pressão térmica" if ear_medio is not None else "N/A"
            )
        },
        
        # =============================================
        # DADOS DE REFERÊNCIA
        # =============================================
        "dados_referencia": {
            "pld_medio": pld_medio,
            "cvu_medio": cvu_medio,
            "teto_estrutural": PLD_TETO_ESTRUTURAL,
            "limite_folga_estrutural": 150,  # % acima do qual é folga estrutural
            "limite_pressao": 95,  # % acima do qual há pressão
            "limite_risco": 100,   # % acima do qual há risco de custos
        },
        
        # =============================================
        # METADADOS DA ANÁLISE
        # =============================================
        "metadados": {
            "versao_analise": "termica_v5_dupla_perspectiva",
            "data_calculo": datetime.now().isoformat(),
            "perspectivas_incluidas": ["sistema_modicidade", "gerador_viabilidade"],
            "explicacao": (
                "Análise térmica revisada com dupla perspectiva: "
                "1) Sistema (modicidade tarifária) e "
                "2) Gerador (viabilidade econômica). "
                "CVU alto vs PLD baixo = FOLGA ESTRUTURAL, não risco."
            )
        }
    }


def _compute_cvu_from_csv(ons: Dict[str, Any]) -> Optional[float]:
    cvu_file = _find_ons_csv(ons, "CVU_Usina_Termica")

    if not cvu_file or not os.path.exists(cvu_file):
        return None

    try:
        df = pd.read_csv(cvu_file, sep=None, engine="python")
        if "val_cvu" not in df.columns:
            return None

        cvus = df["val_cvu"].dropna()
        cvus = cvus[cvus > 0]

        return float(cvus.mean()) if not cvus.empty else None

    except Exception:
        return None


# =====================================================================
# NOVAS FUNÇÕES PARA ANÁLISE DE PLD
# =====================================================================

def _calcular_volatilidade_normalizada(pld_series: pd.Series) -> Optional[float]:
    """Calcula volatilidade normalizada considerando limites regulatórios."""
    if pld_series.empty:
        return None
    
    desvio_padrao = pld_series.std()
    banda_total = PLD_TETO_ESTRUTURAL - PLD_PISO
    
    if banda_total > 0:
        return (desvio_padrao / banda_total) * 100  # Em percentual
    return None


def _calcular_posicao_relativa_pld(pld_medio: Optional[float]) -> Optional[float]:
    """Calcula posição relativa do PLD médio na banda regulatória."""
    if pld_medio is None:
        return None
    
    banda_total = PLD_TETO_ESTRUTURAL - PLD_PISO
    if banda_total > 0:
        posicao = ((pld_medio - PLD_PISO) / banda_total) * 100
        return max(0, min(100, posicao))  # Clip entre 0-100%
    return None


def _classificar_volatilidade_pld(volatilidade_norm: Optional[float]) -> str:
    """Classifica a volatilidade do PLD considerando a banda regulatória."""
    if volatilidade_norm is None:
        return "indisponível"
    
    if volatilidade_norm < 10:
        return "baixa"
    elif volatilidade_norm < 25:
        return "moderada"
    elif volatilidade_norm < 40:
        return "alta"
    else:
        return "extrema"


def _classificar_nivel_pld(pld_medio: Optional[float]) -> str:
    """Classifica o nível do PLD médio."""
    if pld_medio is None:
        return "indisponível"
    
    posicao_relativa = _calcular_posicao_relativa_pld(pld_medio)
    if posicao_relativa is None:
        return "indisponível"
    
    if posicao_relativa < 33:
        return "baixo"
    elif posicao_relativa < 66:
        return "moderado"
    else:
        return "elevado"


def _analisar_tendencia_pld(pld_series: pd.Series) -> Dict[str, Any]:
    """Analisa tendência do PLD nas últimas 24h."""
    if pld_series.empty or len(pld_series) < 24:
        return {"tendencia": None, "descricao": "Dados insuficientes"}
    
    # Últimas 24 horas
    ultimas_24h = pld_series.tail(24)
    if len(ultimas_24h) < 12:
        return {"tendencia": None, "descricao": "Dados insuficientes"}
    
    # Calcular tendência linear
    try:
        x = range(len(ultimas_24h))
        y = ultimas_24h.values
        coeficiente = np.polyfit(x, y, 1)[0] if len(y) > 1 else 0
        
        if coeficiente > 5:
            tendencia = "alta"
            descricao = "Tendência de alta forte (> R$ 5/h)"
        elif coeficiente > 1:
            tendencia = "leve alta"
            descricao = "Tendência de leve alta"
        elif coeficiente < -5:
            tendencia = "baixa"
            descricao = "Tendência de baixa forte"
        elif coeficiente < -1:
            tendencia = "leve baixa"
            descricao = "Tendência de leve baixa"
        else:
            tendencia = "estável"
            descricao = "Preços estáveis"
            
        return {
            "tendencia": tendencia,
            "coeficiente": float(coeficiente),
            "descricao": descricao
        }
    except Exception:
        return {"tendencia": None, "descricao": "Erro no cálculo"}


# =====================================================================
# Ciclo do SIN
# =====================================================================
def classify_sin_cycle(
    ear_medio: Optional[float],
    ena_media: Optional[float],
    stress_index: Optional[float],
) -> Dict[str, Any]:

    if ear_medio is None or stress_index is None:
        return {
            "cycle": "indeterminado",
            "description": "Dados insuficientes para classificar o ciclo do SIN.",
        }

    if ear_medio > 75 and stress_index < 0.9:
        cycle = "úmido"
        desc = "Abundância hídrica com folga estrutural de oferta."
    elif ear_medio < 45 and stress_index > 1.1:
        cycle = "crítico"
        desc = "Escassez hídrica com estresse estrutural do sistema."
    elif stress_index > 1.0:
        cycle = "seco"
        desc = "Oferta pressionada, dependência térmica elevada."
    else:
        cycle = "transição"
        desc = "Sistema em equilíbrio instável."

    return {
        "cycle": cycle,
        "description": desc,
    }


# =====================================================================
# Core builder
# =====================================================================

def build_core_analysis(raw_data: Dict[str, Any], output_dir: str = "data") -> Dict[str, Any]:
    sources = _extract_sources(raw_data)
    ons = sources["ons"]
    ccee = sources["ccee"]

    # ---------------- Hidrologia ----------------
    hydrology = _compute_hydrology_from_csv(ons)

    # ---------------- Operação ONS ----------------
    operacao = _extract_energia_agora(ons)

    # ---------------- Preços (PLD horário CCEE) ----------------
    pld_medio = pld_std = pld_min = pld_max = None
    pld_por_submercado = {}
    pld_serie_7d = {}
    pld_series_full = pd.Series(dtype=float)

    pld_records = ccee.get("data", [])

    if pld_records:
        df_pld = pd.DataFrame(pld_records)

        required = {"MES_REFERENCIA", "DIA", "HORA", "PLD_HORA"}
        if required.issubset(df_pld.columns):

            # 🔑 construir timestamp PRIMEIRO
            df_pld["MES_REFERENCIA"] = df_pld["MES_REFERENCIA"].astype(str)

            df_pld["timestamp"] = pd.to_datetime(
                df_pld["MES_REFERENCIA"].str[:4] + "-" +
                df_pld["MES_REFERENCIA"].str[4:] + "-" +
                df_pld["DIA"].astype(str) + " " +
                df_pld["HORA"].astype(str) + ":00",
                errors="coerce"
            )

            df_pld["timestamp"] = (
                df_pld["timestamp"]
                .dt.tz_localize(
                    "America/Sao_Paulo",
                    nonexistent="shift_forward",
                    ambiguous="NaT"
                )
            )

            df_pld = df_pld.dropna(subset=["timestamp", "PLD_HORA"])

            # ===============================
            # MÉTRICAS AGREGADAS
            # ===============================
            if not df_pld.empty:
                pld_medio = float(df_pld["PLD_HORA"].mean())
                pld_std   = float(df_pld["PLD_HORA"].std())
                pld_min   = float(df_pld["PLD_HORA"].min())
                pld_max   = float(df_pld["PLD_HORA"].max())
                
                # Série temporal completa para análises
                pld_series_full = df_pld.set_index("timestamp")["PLD_HORA"]

                if "SUBMERCADO" in df_pld.columns:
                    pld_por_submercado = (
                        df_pld.groupby("SUBMERCADO")["PLD_HORA"]
                        .mean()
                        .to_dict()
                    )

            # ===============================
            # SÉRIE TEMPORAL – ÚLTIMOS 7 DIAS
            # ===============================
            cutoff = df_pld["timestamp"].max() - timedelta(days=7)
            df_7d = df_pld[df_pld["timestamp"] >= cutoff]

            if not df_7d.empty:
                for sm, g in df_7d.groupby("SUBMERCADO"):
                    pld_serie_7d[sm] = (
                        g.sort_values("timestamp")
                        [["timestamp", "PLD_HORA"]]
                        .rename(columns={
                            "timestamp": "instante",
                            "PLD_HORA": "pld"
                        })
                        .to_dict("records")
                    )

    # ---------------- Séries para MCP econômico ----------------
    pld_series = pd.Series(dtype=float)
    carga_sin_series = pd.Series(dtype=float)
    geracao_hidro_sin_series = pd.Series(dtype=float)

    if pld_records and not df_pld.empty:
        pld_series = (
            df_pld
            .sort_values("timestamp")
            .set_index("timestamp")["PLD_HORA"]
        )

    oper = operacao.get("generation", {})
    load = operacao.get("load", {})

    # Carga SIN
    if "sin" in load:
        carga_sin_series = pd.Series(
            [x["carga"] for x in load["sin"]["serie"]],
            index=[x["instante"] for x in load["sin"]["serie"]],
        )

    # Geração hidráulica SIN
    if "sin_hidraulica" in oper:
        geracao_hidro_sin_series = pd.Series(
            [x["geracao"] for x in oper["sin_hidraulica"]["serie"]],
            index=[x["instante"] for x in oper["sin_hidraulica"]["serie"]],
        )

    # ---------------- Despacho térmico ----------------
    cvu_medio = _compute_cvu_from_csv(ons)
    
    # Calcular indicadores térmicos REVISADOS (v5)
    indicadores_termicos = calcular_indicadores_termicos_revisados(
        pld_medio=pld_medio,
        cvu_medio=cvu_medio,
        ear_medio=hydrology.get("ear_medio")
    )

    # ---------------- MCP Econômico ----------------
    mcp_economico = compute_mcp_economico(
        pld_series=pld_series,
        carga_series=carga_sin_series,
        geracao_hidraulica=geracao_hidro_sin_series,
        cvu_medio=cvu_medio,
    )
    
    # ---------------- Ciclo do SIN ----------------
    sin_cycle = classify_sin_cycle(
        ear_medio=hydrology.get("ear_medio"),
        ena_media=hydrology.get("ena_media"),
        stress_index=mcp_economico.get("stress_index"),
    )

    # ---------------- Análises de PLD (NOVAS) ----------------
    # Calcular volatilidade normalizada
    volatilidade_norm = _calcular_volatilidade_normalizada(pld_series_full)
    classificacao_vol = _classificar_volatilidade_pld(volatilidade_norm)
    
    # Calcular posição relativa
    posicao_relativa = _calcular_posicao_relativa_pld(pld_medio)
    classificacao_nivel = _classificar_nivel_pld(pld_medio)
    
    # Análise de tendência
    tendencia_pld = _analisar_tendencia_pld(pld_series_full)
    
    # ---------------- Alerts (ATUALIZADOS com nova lógica) ----------------
    alerts: List[str] = []

    # Alertas hídricos
    if hydrology["classificacao"]["classe"] in {"crítico", "alerta"}:
        alerts.append("Estresse hídrico relevante.")

    # Alertas de PLD
    if pld_medio and posicao_relativa and posicao_relativa > 66:
        alerts.append(f"PLD médio elevado ({pld_medio:.2f} R$/MWh, {posicao_relativa:.0f}% da banda).")

    # Alertas térmicos REVISADOS (usando nova lógica)
    analise_sistema = indicadores_termicos.get("analise_sistema", {})
    classificacao_sistema = analise_sistema.get("classificacao")
    risco_sistêmico = analise_sistema.get("risco_sistêmico")
    
    if risco_sistêmico == "alto":
        percentual_cvu_pld = indicadores_termicos.get("indicadores_quantitativos", {}).get("percentual_cvu_pld")
        if percentual_cvu_pld:
            alerts.append(f"Risco térmico alto: CVU em {percentual_cvu_pld:.0f}% do PLD (despacho com prejuízo possível).")
    
    # Alertas de margem vs teto
    margem_vs_teto = indicadores_termicos.get("indicadores_quantitativos", {}).get("margem_vs_teto")
    if margem_vs_teto is not None:
        if margem_vs_teto < 1:
            alerts.append(f"Margem vs teto crítica ({margem_vs_teto:.1f}%). CVU próximo do teto estrutural.")
        elif margem_vs_teto < 5:
            alerts.append(f"Margem vs teto reduzida ({margem_vs_teto:.1f}%).")
    
    # Alertas de volatilidade extrema
    if classificacao_vol == "extrema":
        alerts.append(f"Volatilidade extrema do PLD ({volatilidade_norm:.0f}% da banda).")

    # ---------------- Construir estrutura CORE ----------------
    core = {
        "timestamp": datetime.now().isoformat(),
        "hydrology": hydrology,
        "mcp_economico": mcp_economico,
        "sin_cycle": sin_cycle,
        "prices": {
            "pld_medio": pld_medio,
            "pld_min": pld_min,
            "pld_max": pld_max,
            "pld_std": pld_std,
            "pld_volatilidade_norm": volatilidade_norm,
            "pld_posicao_relativa": posicao_relativa,
            "pld_classificacao_vol": classificacao_vol,
            "pld_classificacao_nivel": classificacao_nivel,
            "pld_tendencia": tendencia_pld,
            "limites_regulatorios": {
                "piso": PLD_PISO,
                "teto_estrutural": PLD_TETO_ESTRUTURAL,
                "teto_horario": PLD_TETO_HORARIO
            },
            "por_submercado": pld_por_submercado,
            "pld_horario_7d": pld_serie_7d,
        },
        # ESTRUTURA REVISADA: Análise térmica com dupla perspectiva
        "thermal_analysis": indicadores_termicos,
        "operacao": operacao,
        "alerts": alerts,
        "metadata": {
            "analysis_version": "core-6.0",  # Atualizada para v6 com correção conceitual
            "sources": ["ONS (CSV + Energia Agora)", "CCEE"],
            "limites_aneel_2025": True,
            "analise_termica_versao": "v5_dupla_perspectiva",
            "correcao_conceitual": True,  # Sinaliza que CVU alto vs PLD baixo = FOLGA
            "perspectivas_incluidas": ["sistema_modicidade", "gerador_viabilidade"],
            "generated_at": datetime.now().isoformat(),
        },
    }

    # ---------------- Persist ----------------
    os.makedirs(output_dir, exist_ok=True)
    
    # REMOVER versões antigas primeiro
    for filename in os.listdir(output_dir):
        if filename.startswith("core_analysis_") and filename.endswith(".json"):
            os.remove(os.path.join(output_dir, filename))
    
    # Salvar apenas o arquivo mais recente
    path = os.path.join(output_dir, "core_analysis_latest.json")
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(core, f, indent=2, ensure_ascii=False, default=str)
    return core