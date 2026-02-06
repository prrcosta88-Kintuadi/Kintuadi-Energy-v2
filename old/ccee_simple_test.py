# ccee_simple_test.py
import requests
import pandas as pd
from datetime import datetime, timedelta
import json

class CCEESimpleCollector:
    def __init__(self):
        self.base_url = "https://dadosabertos.ccee.org.br/api/3/action/datastore_search"
        self.resource_id = "3f279d6b-1069-42f7-9b0a-217b084729c4"
        
    def get_pld_basic(self, limit=100, offset=0):
        """Coleta básica de dados do PLD"""
        url = f"{self.base_url}?resource_id={self.resource_id}&limit={limit}&offset={offset}"
        
        print(f"🔍 Fazendo requisição: {url}")
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("success"):
                records = data["result"]["records"]
                print(f"✅ {len(records)} registros coletados")
                return records
            else:
                print(f"❌ API retornou sucesso=False")
                return []
                
        except Exception as e:
            print(f"❌ Erro na requisição: {str(e)}")
            return []
    
    def get_pld_by_date(self, target_date=None, days_back=7):
        """
        Coleta PLD para uma data específica ou período
        
        Args:
            target_date: Data no formato 'YYYY-MM-DD'
            days_back: Número de dias para trás se target_date for None
        """
        if target_date is None:
            target_date = datetime.now().strftime("%Y-%m-%d")
        
        print(f"🎯 Buscando PLD para data: {target_date}")
        
        # Primeiro, vamos entender a estrutura dos dados
        all_records = []
        offset = 0
        limit = 500
        max_records = 2000  # Limite para não sobrecarregar
        
        while len(all_records) < max_records:
            print(f"📄 Coletando página (offset: {offset})...")
            records = self.get_pld_basic(limit=limit, offset=offset)
            
            if not records:
                break
            
            # Filtra pela data (baseado na coluna DIA)
            for record in records:
                # O campo DIA parece estar no formato "6" (apenas dia do mês)
                # Precisamos combinar com MES_REFERENCIA
                if self._matches_date(record, target_date):
                    all_records.append(record)
            
            offset += limit
            
            # Se recebeu menos que o limite, terminou
            if len(records) < limit:
                break
        
        print(f"📊 Total de registros para {target_date}: {len(all_records)}")
        return all_records
    
    def _matches_date(self, record, target_date):
        """Verifica se o registro corresponde à data alvo"""
        try:
            # Parse da data alvo
            target_dt = datetime.strptime(target_date, "%Y-%m-%d")
            target_year = target_dt.year
            target_month = target_dt.month
            target_day = target_dt.day
            
            # Extrai informações do registro
            mes_referencia = record.get("MES_REFERENCIA", "")
            dia = record.get("DIA", "")
            
            # MES_REFERENCIA está no formato "202602" (ano + mês)
            if len(mes_referencia) == 6:
                record_year = int(mes_referencia[:4])
                record_month = int(mes_referencia[4:6])
                
                # DIA está apenas como string do dia do mês
                record_day = int(dia) if dia.isdigit() else 0
                
                # Compara
                return (record_year == target_year and 
                        record_month == target_month and 
                        record_day == target_day)
            
            return False
            
        except Exception as e:
            print(f"⚠️ Erro ao processar data: {e}")
            return False
    
    def get_pld_last_7_days(self):
        """Coleta PLD dos últimos 7 dias"""
        all_data = []
        
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            print(f"\n📅 Coletando {date}...")
            
            daily_data = self.get_pld_by_date(date)
            
            # Adiciona data completa aos registros
            for record in daily_data:
                record['DATA_COMPLETA'] = date
                record['TIMESTAMP'] = f"{date} {int(record.get('HORA', 0)):02d}:00:00"
            
            all_data.extend(daily_data)
        
        return all_data
    
    def analyze_pld_data(self, records):
        """Analisa os dados do PLD coletados"""
        if not records:
            print("⚠️ Nenhum dado para analisar")
            return {}
        
        df = pd.DataFrame(records)
        
        print("\n📊 ANÁLISE DOS DADOS COLETADOS:")
        print("=" * 50)
        
        # 1. Informações básicas
        print(f"Total de registros: {len(df)}")
        print(f"Colunas disponíveis: {', '.join(df.columns)}")
        
        # 2. Submercados presentes
        if 'SUBMERCADO' in df.columns:
            submercados = df['SUBMERCADO'].unique()
            print(f"\nSubmercados encontrados: {', '.join(submercados)}")
            
            # Contagem por submercado
            print("\nRegistros por submercado:")
            for subm in submercados:
                count = len(df[df['SUBMERCADO'] == subm])
                print(f"  {subm}: {count} registros")
        
        # 3. Valores do PLD
        if 'PLD_HORA' in df.columns:
            # Converte para numérico
            df['PLD_HORA'] = pd.to_numeric(df['PLD_HORA'], errors='coerce')
            
            print(f"\nEstatísticas do PLD:")
            print(f"  Média: R$ {df['PLD_HORA'].mean():.2f}/MWh")
            print(f"  Mínimo: R$ {df['PLD_HORA'].min():.2f}/MWh")
            print(f"  Máximo: R$ {df['PLD_HORA'].max():.2f}/MWh")
            print(f"  Desvio padrão: R$ {df['PLD_HORA'].std():.2f}/MWh")
            
            # PLD por submercado
            if 'SUBMERCADO' in df.columns:
                print(f"\nPLD por submercado:")
                for subm in df['SUBMERCADO'].unique():
                    subset = df[df['SUBMERCADO'] == subm]
                    avg = subset['PLD_HORA'].mean()
                    print(f"  {subm}: R$ {avg:.2f}/MWh")
        
        # 4. Distribuição por hora
        if 'HORA' in df.columns:
            print(f"\nDistribuição por hora do dia:")
            df['HORA'] = pd.to_numeric(df['HORA'], errors='coerce')
            for hora in sorted(df['HORA'].unique()):
                count = len(df[df['HORA'] == hora])
                print(f"  Hora {int(hora):02d}:00 - {count} registros")
        
        return df
    
    def save_to_csv(self, records, filename=None):
        """Salva os dados em CSV"""
        if not records:
            print("⚠️ Nenhum dado para salvar")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"pld_ccee_{timestamp}.csv"
        
        df = pd.DataFrame(records)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        
        print(f"\n💾 Dados salvos em: {filename}")
        print(f"   Total de registros: {len(df)}")
        
        return filename
    
    def test_connection(self):
        """Testa a conexão com a API da CCEE"""
        print("🧪 TESTANDO CONEXÃO COM CCEE...")
        
        # Teste básico
        test_records = self.get_pld_basic(limit=5)
        
        if test_records:
            print("✅ Conexão estabelecida com sucesso!")
            print("\n📋 Exemplo de dados recebidos:")
            for i, record in enumerate(test_records[:3], 1):
                print(f"\nRegistro {i}:")
                for key, value in record.items():
                    print(f"  {key}: {value}")
            
            # Analisa a estrutura
            self.analyze_pld_data(test_records)
            return True
        else:
            print("❌ Falha na conexão com a CCEE")
            return False


def main():
    """Função principal de teste"""
    print("=" * 60)
    print("🧪 TESTE SIMPLIFICADO - COLETA CCEE")
    print("=" * 60)
    
    collector = CCEESimpleCollector()
    
    # 1. Testa conexão
    if not collector.test_connection():
        return
    
    # 2. Pergunta o que fazer
    print("\n" + "=" * 60)
    print("🎯 O QUE VOCÊ QUER FAZER?")
    print("1. Coletar últimos 7 dias")
    print("2. Coletar data específica")
    print("3. Coletar apenas hoje")
    print("4. Sair")
    
    choice = input("\nEscolha (1-4): ").strip()
    
    if choice == "1":
        print("\n📅 COLETANDO ÚLTIMOS 7 DIAS...")
        data = collector.get_pld_last_7_days()
        
        if data:
            collector.analyze_pld_data(data)
            collector.save_to_csv(data, "pld_ultimos_7_dias.csv")
    
    elif choice == "2":
        date_str = input("Digite a data (YYYY-MM-DD): ").strip()
        print(f"\n📅 COLETANDO DATA: {date_str}")
        data = collector.get_pld_by_date(date_str)
        
        if data:
            collector.analyze_pld_data(data)
            collector.save_to_csv(data, f"pld_{date_str}.csv")
    
    elif choice == "3":
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"\n📅 COLETANDO HOJE: {today}")
        data = collector.get_pld_by_date(today)
        
        if data:
            collector.analyze_pld_data(data)
            collector.save_to_csv(data, f"pld_{today}.csv")
    
    elif choice == "4":
        print("👋 Saindo...")
        return
    
    print("\n" + "=" * 60)
    print("✅ TESTE CONCLUÍDO!")


if __name__ == "__main__":
    main()