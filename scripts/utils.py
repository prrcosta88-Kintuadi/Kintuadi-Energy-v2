# scripts/utils.py - VERSÃO COMPLETA
import json
import pandas as pd
from datetime import datetime, date
import numpy as np

class JSONEncoder(json.JSONEncoder):
    """Encoder personalizado para JSON que lida com tipos especiais"""
    def default(self, obj):
        if obj is None:
            return None
        
        # Arrays numpy
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        
        # Scalars numpy
        if isinstance(obj, (np.integer, np.floating)):
            return float(obj) if isinstance(obj, np.floating) else int(obj)
        
        # Pandas
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if isinstance(obj, pd.Series):
            return obj.tolist()
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict('records')
        
        # Datas
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        
        # NaN do pandas
        try:
            if pd.isna(obj):
                return None
        except:
            pass
        
        return super().default(obj)

def make_serializable(obj):
    """
    Converte recursivamente objetos para serializáveis em JSON
    Versão corrigida para lidar com arrays do numpy
    """
    try:
        # Usa o encoder
        encoder = JSONEncoder()
        return encoder.default(obj) if hasattr(encoder, 'default') else obj
        
    except (TypeError, ValueError):
        # Fallback para tipos complexos
        if isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [make_serializable(v) for v in obj]
        elif hasattr(obj, 'isoformat'):  # Para datas
            return obj.isoformat()
        else:
            try:
                return str(obj)
            except:
                return None

def save_json(data, filename):
    """Salva dados em JSON com encoding correto"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, cls=JSONEncoder, ensure_ascii=False, indent=2)
        print(f"✅ JSON salvo: {filename}")
        return True
    except Exception as e:
        print(f"❌ Erro ao salvar JSON {filename}: {str(e)}")
        # Tenta método alternativo
        try:
            serializable_data = make_serializable(data)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, ensure_ascii=False, indent=2)
            print(f"✅ JSON salvo (método alternativo): {filename}")
            return True
        except:
            return False

def load_json(filename):
    """Carrega dados de JSON"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Erro ao carregar JSON {filename}: {str(e)}")
        return None