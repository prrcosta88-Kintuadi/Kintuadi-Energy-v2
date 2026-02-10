# scripts/energy_analyzer.py
from datetime import datetime

class EnergyAnalyzer:
    """Analisa dados energéticos e gera insights"""
    
    def analyze_integrated_data(self, ons_data, ccee_data):
        """Analisa dados integrados ONS + CCEE"""
        analysis = {
            'data_analise': datetime.now().isoformat(),
            'indicadores': {},
            'recomendacoes': [],
            'alerta': False
        }
        
        # Extrai dados do ONS
        ons_summary = ons_data.get('summary', {})
        ons_geral = ons_summary.get('geral', {})
        
        # Extrai dados da CCEE
        ccee_stats = ccee_data.get('statistics', {})
        ccee_geral = ccee_stats.get('geral', {})
        
        # 1. Índice de Segurança Energética
        volume_medio = ons_geral.get('volume_medio_geral', 0)
        analysis['indicadores']['seguranca_energetica'] = volume_medio
        
        if volume_medio < 40:
            analysis['alerta'] = True
            analysis['recomendacoes'].append(
                "🚨 ALERTA CRÍTICO: Volume dos reservatórios abaixo de 40%. "
                "Expectativa de forte alta no PLD e necessidade de acionamento térmico emergencial."
            )
        elif volume_medio < 60:
            analysis['alerta'] = True
            analysis['recomendacoes'].append(
                "⚠️ SISTEMA EM ALERTA: Volume dos reservatórios entre 40-60%. "
                "Monitorar preços no mercado spot e considerar ajustes na estratégia de contratação."
            )
        
        # 2. Pressão sobre Preços
        pld_medio = ccee_geral.get('pld_medio', 150)
        pld_volatilidade = ccee_geral.get('pld_desvio', 0)
        
        # Fórmula simplificada de pressão
        pressao_precos = min(100, max(0, (100 - volume_medio) * (pld_medio / 200)))
        analysis['indicadores']['pressao_precos'] = pressao_precos
        
        # 3. Recomendações por perfil
        analysis['recomendacoes_por_perfil'] = {
            'geradores': self._get_recommendations_for_generators(volume_medio, pld_medio),
            'consumidores': self._get_recommendations_for_consumers(volume_medio, pld_medio),
            'comercializadores': self._get_recommendations_for_traders(volume_medio, pld_medio, pld_volatilidade)
        }
        
        # 4. Tendência de Mercado
        analysis['tendencia_mercado'] = self._get_market_trend(volume_medio, pld_medio)
        
        return analysis
    
    def _get_recommendations_for_generators(self, volume, pld):
        """Recomendações para geradores"""
        recommendations = []
        
        if volume < 60 and pld > 200:
            recommendations.append("Aumentar exposição ao mercado spot - PLD elevado com tendência de alta")
        elif volume > 70 and pld < 150:
            recommendations.append("Oportunidade para contratos de longo prazo com preço fixo")
        
        if volume < 50:
            recommendations.append("Preparar geração térmica para possível despacho emergencial")
        
        return recommendations if recommendations else ["Manter estratégia atual"]
    
    def _get_recommendations_for_consumers(self, volume, pld):
        """Recomendações para consumidores"""
        recommendations = []
        
        if volume < 60:
            recommendations.append("Considerar aumento de contratação no ACR para proteção contra volatilidade")
        elif volume > 70 and pld < 180:
            recommendations.append("Momento favorável para migração ou aumento de carga no ACL")
        
        if pld > 250:
            recommendations.append("Avaliar projetos de geração distribuída (solar) para reduzir exposição")
        
        return recommendations if recommendations else ["Manter estratégia atual"]
    
    def _get_recommendations_for_traders(self, volume, pld, volatilidade):
        """Recomendações para comercializadores"""
        recommendations = []
        
        if volume < 60:
            recommendations.append("Incluir prêmio de risco nos preços oferecidos")
        elif volume > 70:
            recommendations.append("Preços competitivos podem atrair novos clientes")
        
        if volatilidade > 50:
            recommendations.append("Alta volatilidade - ajustar limites de exposição")
        
        return recommendations if recommendations else ["Manter estratégia atual"]
    
    def _get_market_trend(self, volume, pld):
        """Determina tendência do mercado"""
        if volume < 50 and pld > 200:
            return "ALTA FORTE - Condições críticas de oferta"
        elif volume < 60 and pld > 180:
            return "ALTA MODERADA - Sistema em alerta"
        elif volume > 70 and pld < 150:
            return "ESTÁVEL - Condições favoráveis"
        elif volume > 80 and pld < 120:
            return "BAIXA - Excesso de oferta"
        else:
            return "NEUTRA - Condições equilibradas"
    
    def simulate_contract_scenario(self, profile, exposure, risk_tolerance):
        """
        Simula cenário de contratação
        
        Args:
            profile: 'generator', 'consumer', 'trader'
            exposure: Exposição desejada ao spot (0-100%)
            risk_tolerance: 'low', 'medium', 'high'
        """
        return {
            'perfil': profile,
            'exposicao_spot': exposure,
            'tolerancia_risco': risk_tolerance,
            'estrategia_recomendada': self._get_strategy_for_profile(profile, exposure, risk_tolerance),
            'metricas_esperadas': {
                'custo_medio_estimado': 150 + (100 - exposure) * 0.5,
                'volatilidade_esperada': exposure * 0.8,
                'protecao_risco': 100 - exposure
            }
        }
    
    def _get_strategy_for_profile(self, profile, exposure, risk_tolerance):
        """Determina estratégia baseada no perfil"""
        strategies = {
            'generator': {
                'low': f"Contratos longos ({100-exposure}%) + Spot limitado ({exposure}%)",
                'medium': f"Contratos médios ({70}%) + Spot ({30}%)",
                'high': f"Contratos curtos ({40}%) + Spot amplo ({60}%)"
            },
            'consumer': {
                'low': f"ACR majoritário ({80}%) + ACL limitado ({20}%)",
                'medium': f"ACR ({60}%) + ACL ({40}%) balanceado",
                'high': f"ACL majoritário ({70}%) + ACR ({30}%)"
            },
            'trader': {
                'low': "Arbitragem regional + contratos balanceados",
                'medium': "Mix de contratos + hedge no mercado futuro",
                'high': "Exposição controlada ao spot + derivativos"
            }
        }
        
        return strategies.get(profile, {}).get(risk_tolerance, "Estratégia padrão")