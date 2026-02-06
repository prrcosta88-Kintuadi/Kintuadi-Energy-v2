# Novo arquivo: scripts/analyzer_v2.py
import logging
from datetime import datetime
from typing import Dict, List
from .data_models import MarketAnalysis

logger = logging.getLogger(__name__)

class EnergyMarketAnalyzer:
    """Analisador otimizado de mercado de energia"""
    
    def analyze_market(self, ons_data: Dict, ccee_data: Dict) -> MarketAnalysis:
        """Analisa dados integrados ONS + CCEE"""
        
        # Extrai indicadores
        ons_stats = ons_data.get("statistics", {}).get("geral", {})
        ccee_stats = ccee_data.get("statistics", {}).get("geral", {})
        
        volume_medio = ons_stats.get("volume_medio", 0)
        pld_medio = ccee_stats.get("pld_medio", 0)
        pld_volatilidade = ccee_stats.get("pld_std", 0)
        
        # Calcula tendência
        tendencia = self._calculate_market_trend(volume_medio, pld_medio)
        
        # Verifica alertas
        alerta, nivel_alerta = self._check_alerts(volume_medio, pld_medio, pld_volatilidade)
        
        # Calcula índice de segurança
        indice_seguranca = self._calculate_security_index(volume_medio, pld_medio)
        
        # Gera recomendações
        recomendacoes = self._generate_recommendations(
            volume_medio, pld_medio, pld_volatilidade, nivel_alerta
        )
        
        # Cria objeto de análise
        analysis = MarketAnalysis(
            timestamp=datetime.now().isoformat(),
            tendencia_mercado=tendencia,
            indice_seguranca=indice_seguranca,
            alerta=alerta,
            nivel_alerta=nivel_alerta,
            recomendacoes=recomendacoes,
            indicadores={
                "volume_medio": volume_medio,
                "pld_medio": pld_medio,
                "pld_volatilidade": pld_volatilidade,
                "pld_variacao_percentual": (pld_volatilidade / pld_medio * 100) if pld_medio > 0 else 0
            }
        )
        
        logger.info(f"Análise gerada: {tendencia}, Índice: {indice_seguranca:.1f}")
        
        return analysis
    
    def _calculate_market_trend(self, volume: float, pld: float) -> str:
        """Calcula tendência do mercado"""
        
        if volume < 30 and pld > 400:
            return "🔥 ALTA EXTREMA - Emergência energética"
        elif volume < 40 and pld > 300:
            return "📈 ALTA FORTE - Condições críticas"
        elif volume < 50 and pld > 200:
            return "⬆️ ALTA MODERADA - Pressão nos preços"
        elif volume < 60 and pld > 150:
            return "↗️ LEVE ALTA - Monitoramento necessário"
        elif volume > 80 and pld < 100:
            return "↘️ LEVE BAIXA - Condições favoráveis"
        elif volume > 85 and pld < 80:
            return "⬇️ BAIXA MODERADA - Excesso de oferta"
        elif volume > 90 and pld < 60:
            return "💧 BAIXA FORTE - Excedente significativo"
        else:
            return "➡️ ESTÁVEL - Equilíbrio oferta/demanda"
    
    def _check_alerts(self, volume: float, pld: float, volatilidade: float) -> tuple:
        """Verifica condições de alerta"""
        
        # Alerta de volume
        if volume < 30:
            return True, "CRÍTICO"
        elif volume < 40:
            return True, "ALTO"
        elif volume < 50:
            return True, "MÉDIO"
        
        # Alerta de preço
        if pld > 500:
            return True, "CRÍTICO"
        elif pld > 300:
            return True, "ALTO"
        elif pld > 200:
            return True, "MÉDIO"
        
        # Alerta de volatilidade
        if pld > 0 and (volatilidade / pld * 100) > 50:
            return True, "VOLÁTIL"
        
        return False, "BAIXO"
    
    def _calculate_security_index(self, volume: float, pld: float) -> float:
        """Calcula índice de segurança energética (0-100)"""
        
        # Componente volume (0-60 pontos)
        if volume >= 90:
            volume_score = 60
        elif volume >= 70:
            volume_score = 40 + (volume - 70) * 1
        elif volume >= 50:
            volume_score = 20 + (volume - 50) * 1
        elif volume >= 30:
            volume_score = 10 + (volume - 30) * 0.5
        else:
            volume_score = volume * 0.33
        
        # Componente preço (0-40 pontos)
        if pld <= 100:
            price_score = 40
        elif pld <= 200:
            price_score = 40 - ((pld - 100) / 100 * 20)
        elif pld <= 400:
            price_score = 20 - ((pld - 200) / 200 * 15)
        else:
            price_score = 5 - ((pld - 400) / 600 * 5)
        
        total_score = volume_score + price_score
        
        # Ajusta para escala 0-100
        adjusted_score = min(100, max(0, total_score))
        
        return round(adjusted_score, 1)
    
    def _generate_recommendations(self, volume: float, pld: float, 
                                  volatilidade: float, nivel_alerta: str) -> List[str]:
        """Gera recomendações estratégicas"""
        
        recomendacoes = []
        
        # Recomendações baseadas no volume
        if volume < 40:
            recomendacoes.append("🚨 **AÇÃO IMEDIATA NECESSÁRIA**")
            recomendacoes.append("- Acionar geração térmica emergencial")
            recomendacoes.append("- Ativar mecanismos de racionamento preventivo")
            recomendacoes.append("- Suspender manutenções programadas")
        
        elif volume < 60:
            recomendacoes.append("⚠️ **MONITORAMENTO INTENSIVO**")
            recomendacoes.append("- Preparar térmicas para despacho")
            recomendacoes.append("- Revisar contratos de fornecimento")
            recomendacoes.append("- Aumentar exposição ao mercado spot")
        
        elif volume > 80:
            recomendacoes.append("✅ **CONDIÇÕES FAVORÁVEIS**")
            recomendacoes.append("- Oportunidade para manutenções")
            recomendacoes.append("- Negociar contratos de longo prazo")
            recomendacoes.append("- Considerar exportação de excedentes")
        
        # Recomendações baseadas no preço
        if pld > 300:
            recomendacoes.append("💰 **PLD ELEVADO**")
            recomendacoes.append("- Incluir prêmio de risco significativo")
            recomendacoes.append("- Usar derivativos para hedge")
            recomendacoes.append("- Revisar limites de exposição")
        
        elif pld < 100:
            recomendacoes.append("💸 **PLD BAIXO**")
            recomendacoes.append("- Momento para contratação no ACL")
            recomendacoes.append("- Considerar expansão de consumo")
            recomendacoes.append("- Avaliar projetos de eficiência energética")
        
        # Recomendações baseadas na volatilidade
        if pld > 0 and (volatilidade / pld * 100) > 30:
            recomendacoes.append("📊 **ALTA VOLATILIDADE**")
            recomendacoes.append("- Diversificar portfólio de contratação")
            recomendacoes.append("- Usar opções para proteção")
            recomendacoes.append("- Monitorar mercado diariamente")
        
        # Recomendação geral se não houver outras
        if not recomendacoes:
            recomendacoes.append("📈 **MERCADO ESTÁVEL**")
            recomendacoes.append("- Manter estratégia atual")
            recomendacoes.append("- Monitorar indicadores regularmente")
        
        return recomendacoes