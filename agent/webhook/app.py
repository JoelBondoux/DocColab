from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, Request, Response, status

from agent.sync.sync_manager import SyncManager, WebhookVerificationError


def create_webhook_app(manager: SyncManager) -> FastAPI:
    app = FastAPI(
        title="DocColab webhook receiver",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/status")
    async def document_status() -> dict[str, object]:
        documents = []
        for document_id in manager.documents:
            state = manager.state.get_document(document_id)
            documents.append(
                {
                    "document_id": document_id,
                    "status": state.status,
                    "version": state.version,
                    "last_writer": state.last_writer,
                    "last_error": state.last_error,
                    "updated_at": state.updated_at,
                }
            )
        return {"documents": documents}

    @app.post("/webhooks/google", status_code=status.HTTP_204_NO_CONTENT)
    async def google_webhook(request: Request) -> Response:
        headers = {key.lower(): value for key, value in request.headers.items()}
        try:
            document_id = manager.validate_google_notification(headers)
        except WebhookVerificationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if document_id:
            asyncio.create_task(manager.notify(document_id))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app
