# test_ons_api.py
import csv
import io
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = "https://integra.ons.org.br/api"
DEFAULT_TIMEOUT = 30
OPEN_DATA_TIMEOUT = 60
OPEN_DATA_SAMPLE_LINES = 5

OPEN_DATASETS = [
    (
        "Dicionário Reservatórios (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/reservatorio/"
        "DicionarioDados_Reservatorio.json",
        "json",
    ),
    (
        "Reservatórios (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/reservatorio/RESERVATORIOS.csv",
        "csv",
    ),
    (
        "Dicionário EAR Reservatórios (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_reservatorio_di/"
        "DicionarioDados_EarPorReservatorio.json",
        "json",
    ),
    (
        "EAR Diário Reservatórios (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_reservatorio_di/"
        "EAR_DIARIO_RESERVATORIOS_2026.csv",
        "csv",
    ),
    (
        "Dicionário ENA Reservatórios (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_reservatorio_di/"
        "DicionarioDados_EnaPorReservatorio.json",
        "json",
    ),
    (
        "ENA Diário Reservatórios (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_reservatorio_di/"
        "ENA_DIARIO_RESERVATORIOS_2026.csv",
        "csv",
    ),
    (
        "Dicionário Hidrológicos Diários (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/dados_hidrologicos_di/"
        "DicionarioDados_DadosHidrologicosDiarios.json",
        "json",
    ),
    (
        "Hidrológicos Diários (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/dados_hidrologicos_di/"
        "DADOS_HIDROLOGICOS_RES_2026.csv",
        "csv",
    ),
    (
        "Dicionário Hidrológicos Horários (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/dados_hidrologicos_ho/"
        "DicionarioDados_DadosHidrologicosHorarios.json",
        "json",
    ),
    (
        "Hidrológicos Horários (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/dados_hidrologicos_ho/"
        "DADOS_HIDROLOGICOS_HO_2026_02.csv",
        "csv",
    ),
    (
        "Dicionário EAR Diário REE (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_ree_di/"
        "DicionarioDados_EarPorResEquivalente.json",
        "json",
    ),
    (
        "EAR Diário REE (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_ree_di/"
        "EAR_DIARIO_REE_2026.csv",
        "csv",
    ),
    (
        "Dicionário ENA Diário REE (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_ree_di/"
        "DicionarioDados_EnaPorResEquivalente.json",
        "json",
    ),
    (
        "ENA Diário REE (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_ree_di/"
        "ENA_DIARIO_REE_2026.csv",
        "csv",
    ),
    (
        "Dicionário EAR Diário Subsistema (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_subsistema_di/"
        "DicionarioDados_EarPorSubsistema.json",
        "json",
    ),
    (
        "EAR Diário Subsistema (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_subsistema_di/"
        "EAR_DIARIO_SUBSISTEMA_2026.csv",
        "csv",
    ),
    (
        "Dicionário EAR Diário Bacia (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_bacia_di/"
        "DicionarioDados_EarPorBacia.json",
        "json",
    ),
    (
        "EAR Diário Bacia (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ear_bacia_di/"
        "EAR_DIARIO_BACIAS_2026.csv",
        "csv",
    ),
    (
        "Dicionário ENA Diário Subsistema (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_subsistema_di/"
        "DicionarioDados_EnaPorSubsistema.json",
        "json",
    ),
    (
        "ENA Diário Subsistema (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_subsistema_di/"
        "ENA_DIARIO_SUBSISTEMA_2026.csv",
        "csv",
    ),
    (
        "Dicionário ENA Diário Bacia (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_bacia_di/"
        "DicionarioDados_EnaPorBacia.json",
        "json",
    ),
    (
        "ENA Diário Bacia (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/ena_bacia_di/"
        "ENA_DIARIO_BACIAS_2026.csv",
        "csv",
    ),
    (
        "Dicionário Volume Espera (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/res_volumeespera/"
        "DicionarioDados_VolumeEsperaRecomendado.json",
        "json",
    ),
    (
        "Volume Espera (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/res_volumeespera/"
        "RES_VOLUMEESPERA_2026.csv",
        "csv",
    ),
    (
        "Dicionário Energia Vertida Turbinável (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/energia_vertida_turbinavel_ho/"
        "DicionarioDados_EnergiaVertidaTurbinavel.json",
        "json",
    ),
    (
        "Energia Vertida Turbinável (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/energia_vertida_turbinavel_ho/"
        "ENERGIA_VERTIDA_TURBINAVEL_2026_02.csv",
        "csv",
    ),
    (
        "Dicionário Intercâmbio Nacional (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/intercambio_nacional_ho/"
        "DicionarioDados_Intercambio_Nacional.json",
        "json",
    ),
    (
        "Intercâmbio Nacional (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/intercambio_nacional_ho/"
        "INTERCAMBIO_NACIONAL_2026.csv",
        "csv",
    ),
    (
        "Dicionário Intercâmbio Internacional (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/intercambio_internacional_ho/"
        "DicionarioDados_Intercambio_Internacional.json",
        "json",
    ),
    (
        "Intercâmbio Internacional (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/intercambio_internacional_ho/"
        "INTERCAMBIO_INTERNACIONAL_2026.csv",
        "csv",
    ),
    (
        "Dicionário Intercâmbio por Modalidade (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/intercambio_modalidade_ho/"
        "DicionarioDados_Intercambio_Energia_Modalidade.json",
        "json",
    ),
    (
        "Intercâmbio por Modalidade (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/intercambio_modalidade_ho/"
        "INTERCAMBIO_ENERGIA_MODALIDADE_2026.csv",
        "csv",
    ),
    (
        "Dicionário CVU Usina Térmica (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/cvu_usitermica_se/"
        "DicionarioDados_CVU_UsinaTermica.json",
        "json",
    ),
    (
        "CVU Usina Térmica (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/cvu_usitermica_se/"
        "CVU_USINA_TERMICA_2026.csv",
        "csv",
    ),
    (
        "Dicionário Capacidade Instalada (JSON)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/capacidade-geracao/"
        "DicionarioDados_Capacidade_Instalada_Geracao.json",
        "json",
    ),
    (
        "Capacidade Instalada (CSV)",
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/capacidade-geracao/"
        "CAPACIDADE_GERACAO.csv",
        "csv",
    ),
]

EXPECTED_API_DISABLE_MESSAGE = "API desabilitada"
ENERGIA_AGORA_ENDPOINTS = [
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

CARGA_AGORA_ENDPOINTS = [
    "Carga_SIN_json",
    "Carga_Norte_json",
    "Carga_Nordeste_json",
    "Carga_SudesteECentroOeste_json",
    "Carga_Sul_json",
]


@dataclass(frozen=True)
class AuthToken:
    token_type: str
    access_token: str
    expires_in: Optional[int] = None


def build_auth_headers(token: AuthToken) -> Dict[str, str]:
    return {
        "Authorization": f"{token.token_type.capitalize()} {token.access_token}",
        "accept": "application/json",
        "Content-Type": "application/json",
    }


def authenticate(username: str, password: str) -> Optional[AuthToken]:
    auth_url = f"{API_BASE_URL}/autenticar"
    payload = {"usuario": username, "senha": password}
    headers = {"accept": "application/json", "Content-Type": "application/json"}

    try:
        response = requests.post(auth_url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        print(f"❌ Erro na autenticação: {exc}")
        return None

    if response.status_code != 200:
        print(f"❌ Falha na autenticação: HTTP {response.status_code}")
        print(f"   Resposta: {response.text[:200]}")
        return None

    auth_data = response.json()
    token = auth_data.get("access_token")
    token_type = auth_data.get("token_type", "bearer")
    if not token:
        print("❌ Token não retornado pela API.")
        return None

    expires_in = auth_data.get("expires_in")
    print("✅ Autenticação bem-sucedida!")
    print(f"   Token type: {token_type}")
    print(f"   Expira em: {expires_in if expires_in is not None else 'N/A'} segundos")
    print(f"   Token (início): {token[:50]}...")

    return AuthToken(token_type=token_type, access_token=token, expires_in=expires_in)


def test_reservatorios(headers: Dict[str, str]) -> Optional[List[Dict[str, Any]]]:
    reservatorios_url = f"{API_BASE_URL}/hidrologia/reservatorios"
    paged_headers = {**headers, "Pagina": "1", "Quantidade": "50"}

    try:
        response = requests.get(reservatorios_url, headers=paged_headers, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        print(f"❌ Erro na listagem: {exc}")
        return None

    if response.status_code != 200:
        print(f"❌ Erro na listagem: HTTP {response.status_code}")
        print(f"   Resposta: {response.text[:200]}")
        return None

    data = response.json()
    if isinstance(data, list):
        print(f"✅ {len(data)} reservatórios encontrados")
        print("\n   📝 Exemplos:")
        for i, res in enumerate(data[:5]):
            if isinstance(res, dict):
                print(f"   {i+1}. ID: {res.get('id', 'N/A')}, Nome: {res.get('nome', 'N/A')}")
            else:
                print(f"   {i+1}. {res}")

        with open("test_reservatorios.json", "w", encoding="utf-8") as file:
            json.dump(data[:10], file, indent=2, ensure_ascii=False)
        print("   💾 Salvo em: test_reservatorios.json")
        return data

    if isinstance(data, dict):
        print("✅ Resposta em formato dicionário")
        print(f"   Keys: {list(data.keys())}")
        for key in ["data", "result", "reservatorios"]:
            if key in data and isinstance(data[key], list):
                print(f"   Reservatórios em '{key}': {len(data[key])}")
                return data[key]
        return None

    print(f"⚠️ Formato inesperado: {type(data)}")
    return None


def test_volume_util(headers: Dict[str, str], reservatorio_id: str) -> None:
    fim = datetime.now()
    inicio = fim - timedelta(days=3)

    volume_url = f"{API_BASE_URL}/hidrologia/reservatorios/{reservatorio_id}/volumeUtil"
    params = {
        "Inicio": inicio.strftime("%Y-%m-%d %H:%M:%S"),
        "Fim": fim.strftime("%Y-%m-%d %H:%M:%S"),
        "Intervalo": "DI",
        "Origem": "ATR",
    }
    volume_headers = {**headers, "Pagina": "1", "Quantidade": "240"}

    try:
        response = requests.get(
            volume_url, headers=volume_headers, params=params, timeout=DEFAULT_TIMEOUT
        )
    except requests.RequestException as exc:
        print(f"❌ Erro no volume histórico: {exc}")
        return

    if response.status_code != 200:
        print(f"❌ Erro no volume histórico: HTTP {response.status_code}")
        print(f"   Resposta: {response.text[:200]}")
        return

    data = response.json()
    print("✅ Dados históricos obtidos!")
    print(f"   Tipo de resposta: {type(data)}")

    if isinstance(data, list):
        print(f"   Total de registros: {len(data)}")
        if data:
            print("\n   📅 Primeiros registros:")
            for i, registro in enumerate(data[:3]):
                if isinstance(registro, dict):
                    print(
                        f"   {i+1}. {registro.get('dataHora', 'N/A')}:"
                        f" {registro.get('volumeUtil', 'N/A')}%"
                    )
                else:
                    print(f"   {i+1}. {registro}")

        with open("test_volume_data.json", "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False, default=str)
        print("   💾 Salvo em: test_volume_data.json")
        return

    if isinstance(data, dict):
        print(f"   Formato dicionário - Keys: {list(data.keys())}")
        for key in ["data", "result", "volumeUtil"]:
            if key in data:
                print(f"   Dados em '{key}': {type(data[key])}")
                if isinstance(data[key], list):
                    print(f"   Itens: {len(data[key])}")
                    if data[key]:
                        print(f"   Exemplo: {data[key][0]}")
        return

    print(f"   Resposta: {data}")


def is_api_disabled_response(response: requests.Response) -> bool:
    if response.status_code != 503:
        return False
    try:
        payload = response.json()
    except ValueError:
        return EXPECTED_API_DISABLE_MESSAGE.lower() in response.text.lower()
    message = str(payload.get("message", ""))
    return EXPECTED_API_DISABLE_MESSAGE.lower() in message.lower()


def fetch_open_data_sample(url: str, data_type: str) -> Tuple[bool, str]:
    try:
        response = requests.get(url, timeout=OPEN_DATA_TIMEOUT)
    except requests.RequestException as exc:
        return False, f"erro de conexão: {exc}"

    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"

    if data_type == "json":
        try:
            payload = response.json()
        except ValueError as exc:
            return False, f"json inválido: {exc}"
        if isinstance(payload, list):
            preview = payload[:2]
            return True, f"lista com {len(payload)} itens. Exemplo: {preview}"
        if isinstance(payload, dict):
            keys = list(payload.keys())[:10]
            return True, f"dicionário com chaves: {keys}"
        return True, f"tipo inesperado: {type(payload)}"

    if data_type == "csv":
        text_stream = io.StringIO(response.text)
        reader = csv.reader(text_stream)
        rows = []
        for _, row in zip(range(OPEN_DATA_SAMPLE_LINES), reader):
            rows.append(row)
        if not rows:
            return True, "CSV vazio"
        return True, f"{len(rows)} linhas de amostra: {rows}"

    return False, f"tipo não suportado: {data_type}"


def test_open_data_sources() -> None:
    print("\n4. 📂 Testando bases de dados abertos ONS...")
    for name, url, data_type in OPEN_DATASETS:
        ok, details = fetch_open_data_sample(url, data_type)
        status = "✅" if ok else "❌"
        print(f"{status} {name}: {details}")


def test_energia_agora() -> None:
    print("\n3. ⚡ Testando API Energia Agora (geração)...")
    base_url = f"{API_BASE_URL}/energiaagora/Get"
    headers = {"accept": "application/json"}
    for endpoint in ENERGIA_AGORA_ENDPOINTS:
        url = f"{base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as exc:
            print(f"❌ {endpoint}: erro de conexão: {exc}")
            continue

        if response.status_code == 204:
            print(f"⚠️ {endpoint}: sem registros (HTTP 204)")
            continue


        if response.status_code != 200:
            print(f"❌ {endpoint}: HTTP {response.status_code}")
            print(f"   Resposta: {response.text[:200]}")
            continue

        try:
            payload = response.json()
        except ValueError as exc:
            print(f"❌ {endpoint}: resposta JSON inválida: {exc}")
            continue

        if isinstance(payload, list):
            preview = payload[:3]
            print(f"✅ {endpoint}: {len(payload)} registros. Exemplo: {preview}")
        else:
            print(f"⚠️ {endpoint}: resposta inesperada ({type(payload)})")


def test_carga_agora() -> None:
    print("\n4. 🔌 Testando API Energia Agora (carga)...")
    base_url = f"{API_BASE_URL}/energiaagora/Get"
    headers = {"accept": "application/json"}
    for endpoint in CARGA_AGORA_ENDPOINTS:
        url = f"{base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as exc:
            print(f"❌ {endpoint}: erro de conexão: {exc}")
            continue

        if response.status_code == 204:
            print(f"⚠️ {endpoint}: sem registros (HTTP 204)")
            continue

        if response.status_code != 200:
            print(f"❌ {endpoint}: HTTP {response.status_code}")
            print(f"   Resposta: {response.text[:200]}")
            continue

        try:
            payload = response.json()
        except ValueError as exc:
            print(f"❌ {endpoint}: resposta JSON inválida: {exc}")
            continue

        if isinstance(payload, list):
            preview = payload[:3]
            print(f"✅ {endpoint}: {len(payload)} registros. Exemplo: {preview}")
        else:
            print(f"⚠️ {endpoint}: resposta inesperada ({type(payload)})")


def test_balanco_energetico() -> None:
    print("\n5. 📈 Testando balanço energético consolidado...")
    url = f"{API_BASE_URL}/energiaagora/GetBalancoEnergeticoConsolidado/null"
    headers = {"accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        print(f"❌ Balanço energético: erro de conexão: {exc}")
        return

    if response.status_code == 204:
        print("⚠️ Balanço energético: sem registros (HTTP 204)")
        return

    if response.status_code != 200:
        print(f"❌ Balanço energético: HTTP {response.status_code}")
        print(f"   Resposta: {response.text[:200]}")
        return

    try:
        payload = response.json()
    except ValueError as exc:
        print(f"❌ Balanço energético: resposta JSON inválida: {exc}")
        return

    if isinstance(payload, dict):
        keys = list(payload.keys())
        print(f"✅ Balanço energético: chaves principais: {keys}")
        if "Data" in payload:
            print(f"   Data: {payload.get('Data')}")
    else:
        print(f"⚠️ Balanço energético: resposta inesperada ({type(payload)})")


def test_ons_api_direct() -> None:
    """Testa as APIs do ONS para verificar saúde e exemplos de dados."""

    print("🔍 TESTE DIRETO DA API ONS VOLUME UTIL")
    print("=" * 60)

    username = os.getenv("ONS_USERNAME")
    password = os.getenv("ONS_PASSWORD")

    if not username or not password:
        print("❌ Credenciais ONS não configuradas")
        return

    print(f"👤 Usuário: {username}")

    print("\n1. 🔐 Testando autenticação...")
    token = authenticate(username, password)
    if not token:
        return

    headers = build_auth_headers(token)

    print("\n2. 📋 Testando listagem de reservatórios...")
    reservatorios = test_reservatorios(headers)

    test_energia_agora()
    test_carga_agora()
    test_balanco_energetico()

    print("\n6. 📊 Testando volume útil histórico...")
    print("\n4. 📊 Testando volume útil histórico...")
    reservatorio_id = "10"
    if reservatorios and isinstance(reservatorios[0], dict):
        reservatorio_id = str(reservatorios[0].get("id") or reservatorio_id)

    try:
        response = requests.get(
            f"{API_BASE_URL}/hidrologia/reservatorios/{reservatorio_id}/volumeUtil",
            headers={**headers, "Pagina": "1", "Quantidade": "1"},
            params={"Inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        print(f"❌ Erro no volume histórico: {exc}")
        response = None

    if response is not None and is_api_disabled_response(response):
        print("⚠️ API do ONS indisponível. Usando dados abertos.")
        test_open_data_sources()
    else:
        test_volume_util(headers, reservatorio_id)

    print("\n" + "=" * 60)
    print("🎯 PRÓXIMOS PASSOS:")
    print("1. Analise os arquivos gerados:")
    print("   - test_reservatorios.json")
    print("   - test_volume_data.json")
    print("2. Execute: python scripts/ons_volume_util.py")
    print("3. Integre ao coletor principal se funcionar")

if __name__ == "__main__":
    test_ons_api_direct()
