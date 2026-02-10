# test_collector.py
import sys
import os

# Adiciona o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_ons():
    """Testa apenas o coletor ONS"""
    print("🧪 TESTANDO COLETOR ONS...")
    from scripts.ons_reservatorios import ONSReservatoriosCollector
    
    collector = ONSReservatoriosCollector()
    data = collector.get_situacao_reservatorios()
    
    if data:
        print(f"✅ ONS: {len(data)} reservatórios coletados")
        df, summary = collector.process_reservatorios_data(data)
        print(f"   Volume médio: {summary.get('geral', {}).get('volume_medio_geral', 0):.1f}%")
        return True
    else:
        print("❌ ONS: Falha na coleta")
        return False

def test_ccee():
    """Testa apenas o coletor CCEE"""
    print("\n🧪 TESTANDO COLETOR CCEE...")
    from scripts.ccee_collector import CCEECollector
    
    collector = CCEECollector()
    data = collector.get_recent_pld(limit=100)  # Pequena amostra
    
    if data:
        print(f"✅ CCEE: {len(data)} registros coletados")
        df = collector.create_dataframe(data)
        stats = collector.calculate_statistics(df)
        
        if 'geral' in stats:
            print(f"   PLD médio: R$ {stats['geral'].get('pld_medio', 0):.2f}/MWh")
        
        return True
    else:
        print("❌ CCEE: Falha na coleta")
        return False

def test_integrated():
    """Testa o coletor integrado"""
    print("\n🧪 TESTANDO COLETOR INTEGRADO...")
    from scripts.integrated_collector import KintuadiIntegratedCollector
    
    collector = KintuadiIntegratedCollector()
    result = collector.collect_all()
    
    if result:
        print("✅ Coletor integrado funcionou!")
        return True
    else:
        print("❌ Coletor integrado falhou")
        return False

def main():
    """Testa todos os componentes"""
    print("=" * 60)
    print("🧪 TESTE COMPLETO KINTUADI ENERGY")
    print("=" * 60)
    
    # Cria diretório de dados se não existir
    os.makedirs("data", exist_ok=True)
    
    # Testa componentes
    ons_ok = test_ons()
    ccee_ok = test_ccee()
    
    if ons_ok and ccee_ok:
        print("\n✅ Componentes básicos OK!")
        
        # Pergunta se quer testar integrado
        resposta = input("\nDeseja testar o coletor integrado? (s/n): ").strip().lower()
        
        if resposta == 's':
            test_integrated()
    else:
        print("\n❌ Algum componente falhou. Corrija antes de testar integrado.")
    
    print("\n" + "=" * 60)
    print("🧪 TESTE CONCLUÍDO")

if __name__ == "__main__":
    main()