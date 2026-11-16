from orion_api.repository import _payload_hash


def test_payload_hash_is_stable_for_different_key_order():
    first = {"nome": "Pregão", "valor": 1200, "orgao": {"cnpj": "123"}}
    second = {"orgao": {"cnpj": "123"}, "valor": 1200, "nome": "Pregão"}

    assert _payload_hash(first) == _payload_hash(second)


def test_payload_hash_changes_when_source_payload_changes():
    first = {"numeroControlePNCP": "A", "situacao": "aberta"}
    second = {"numeroControlePNCP": "A", "situacao": "encerrada"}

    assert _payload_hash(first) != _payload_hash(second)
