import json

import pytest


class FakeSessionContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeSessionFactory:
    def __call__(self):
        return FakeSessionContext()


@pytest.mark.asyncio
async def test_document_sync_run_returns_auditable_summary(monkeypatch):
    from orion_api import sync_pncp_documents

    class FakeClient:
        pass

    class FakeStore:
        pass

    expected = {
        "source": "PNCP",
        "external_id": "10000000000003-2026-15",
        "listed": 2,
        "archived": 2,
        "removed": 0,
        "complete": True,
        "archived_documents": [],
        "failures": [],
    }
    client = FakeClient()
    store = FakeStore()

    async def fake_sync(session, **kwargs):
        assert isinstance(session, FakeSessionContext)
        assert kwargs["client"] is client
        assert kwargs["store"] is store
        assert kwargs["max_bytes"] > 0
        assert callable(kwargs["heartbeat"])
        await kwargs["heartbeat"]()
        return expected

    async def fake_create(session, *, external_id):
        assert external_id == "10000000000003-2026-15"
        return 71

    async def fake_heartbeat(session, *, operation_id):
        assert operation_id == 71
        return True

    async def fake_finish(session, **kwargs):
        assert kwargs["operation_id"] == 71
        assert kwargs["result"]["complete"] is True

    monkeypatch.setattr(sync_pncp_documents, "create_document_sync_operation", fake_create)
    monkeypatch.setattr(sync_pncp_documents, "heartbeat_document_sync_operation", fake_heartbeat)
    monkeypatch.setattr(sync_pncp_documents, "finish_document_sync_operation", fake_finish)
    monkeypatch.setattr(
        sync_pncp_documents, "synchronize_pncp_procurement_documents", fake_sync
    )
    result = await sync_pncp_documents.run(
        cnpj="10000000000003",
        year=2026,
        sequence=15,
        client=client,
        store=store,
        session_factory=FakeSessionFactory(),
    )

    assert result["operation"] == "pncp_document_sync"
    assert result["operation_id"] == 71
    assert result["complete"] is True
    assert result["archived"] == 2
    assert result["started_at"]


def test_document_sync_cli_exits_with_code_two_for_partial_result(monkeypatch, capsys):
    from orion_api import sync_pncp_documents

    async def fake_run(**kwargs):
        return {
            "operation": "pncp_document_sync",
            "complete": False,
            "listed": 2,
            "archived": 1,
            "failures": [{"document_sequence": 4, "error": "temporarily unavailable"}],
        }

    monkeypatch.setattr(sync_pncp_documents, "run", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "sync_pncp_documents",
            "--cnpj",
            "10000000000003",
            "--year",
            "2026",
            "--sequence",
            "15",
        ],
    )

    with pytest.raises(SystemExit) as error:
        sync_pncp_documents.main()

    assert error.value.code == 2
    output = json.loads(capsys.readouterr().out)
    assert output["complete"] is False
    assert output["archived"] == 1
