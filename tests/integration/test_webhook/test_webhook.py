import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


def test_webhook_returns_200_immediately():
    with patch("app.main.TelegramAdapter") as mock_tg_cls, \
         patch("app.main.checkpointer_context") as mock_ctx:
        mock_tg_cls.return_value.set_webhook = AsyncMock()

        # Make checkpointer_context return a mock checkpointer via async context manager
        mock_cp = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_cp)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("app.infrastructure.container.container.get_message_processor") as mock_get_proc:
            processor = AsyncMock()
            async def dep(request=None):
                return processor
            mock_get_proc.side_effect = dep

            from app.main import app
            with TestClient(app) as client:
                payload = {
                    "update_id": 1,
                    "message": {
                        "message_id": 1,
                        "chat": {"id": 99999},
                        "text": "Hello",
                    },
                }
                response = client.post("/webhook/telegram", json=payload)
                assert response.status_code == 200
                assert response.json() == {"ok": True}


def test_health_endpoint_returns_ok():
    with patch("app.main.TelegramAdapter") as mock_tg_cls, \
         patch("app.main.checkpointer_context") as mock_ctx:
        mock_tg_cls.return_value.set_webhook = AsyncMock()
        mock_cp = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_cp)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        from app.main import app
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "dependencies" in data
