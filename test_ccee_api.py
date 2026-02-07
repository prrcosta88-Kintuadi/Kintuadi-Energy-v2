import os
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://dadosabertos.ccee.org.br/api/3/action/datastore_search"
DEFAULT_TIMEOUT = 30

DATASETS = [
    {
        "name": "Contabilização montante perfil agente",
        "resource_id": "76d1cf4c-da8c-47a5-9f0d-8b50079be960",
        "preview_fields": [
            "MES_REFERENCIA",
            "COD_AGENTE",
            "NOME_EMPRESARIAL",
            "COD_PERF_AGENTE",
            "SIGLA_PERFIL_AGENTE",
            "CNPJ",
            "VALOR_TM_MCP",
            "RESULTADO_FINAL",
        ],
    },
    {
        "name": "Sumário balanço energético horário submercado",
        "resource_id": "9418da65-0f9f-4f66-a43f-6517db9653f3",
        "preview_fields": [
            "MES_REFERENCIA",
            "PERIODO_COMERCIALIZACAO",
            "SUBMERCADO",
            "BE_POSITIVO",
            "BE_NEGATIVO",
            "RESULTADO_MCP",
        ],
    },
    {
        "name": "Sumário distribuição mensal",
        "resource_id": "9e8e3f5f-58a8-4744-b6da-7309a4513fcb",
        "preview_fields": [
            "MES_REFERENCIA",
            "RESULTADO_MCP_RECEBIMENTO",
            "RESULTADO_MCP_PAGAMENTO",
            "ENCARGOS_RECEBIMENTO_DIST",
            "ENCARGOS_PAGAMENTO_DIST",
            "RESULTADO_FINAL_RECEBIMENTO",
            "RESULTADO_FINAL_PAGAMENTO",
        ],
    },
]


def request_dataset(resource_id: str, limit: int = 5) -> Optional[Dict[str, Any]]:
    params = {"resource_id": resource_id, "limit": limit}
    try:
        response = requests.get(BASE_URL, params=params, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        print(f"❌ Erro na requisição: {exc}")
        return None

    if response.status_code != 200:
        print(f"❌ HTTP {response.status_code}")
        print(f"   Resposta: {response.text[:200]}")
        return None

    try:
        payload = response.json()
    except ValueError as exc:
        print(f"❌ Resposta JSON inválida: {exc}")
        return None

    if not payload.get("success"):
        print("❌ API retornou success=false")
        return None

    return payload.get("result")


def preview_records(records: List[Dict[str, Any]], fields: List[str]) -> List[Dict[str, Any]]:
    preview = []
    for record in records[:5]:
        preview.append({field: record.get(field) for field in fields})
    return preview


def test_ccee_api() -> None:
    print("🔍 TESTE DAS APIs DA CCEE")
    print("=" * 60)

    for dataset in DATASETS:
        name = dataset["name"]
        resource_id = dataset["resource_id"]
        fields = dataset["preview_fields"]

        print(f"\n📌 {name}")
        result = request_dataset(resource_id)
        if not result:
            continue

        records = result.get("records", [])
        total = result.get("total")
        print(f"✅ Registros retornados: {len(records)}")
        if total is not None:
            print(f"   Total informado: {total}")

        if records:
            sample = preview_records(records, fields)
            print("   📝 Exemplo:")
            for idx, item in enumerate(sample, start=1):
                print(f"   {idx}. {item}")

    print("\n" + "=" * 60)
    print("🎯 PRÓXIMOS PASSOS:")
    print("1. Ajuste os resource_id conforme novas bases.")
    print("2. Expanda os campos de preview conforme necessidade.")


if __name__ == "__main__":
    test_ccee_api()
