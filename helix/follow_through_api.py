"""Key-authenticated, local-only outcome routes. No execution endpoint is installed."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from .follow_through import ConflictError, CreateOutcome, FollowThroughStore, UpdateOutcome, View


def install_follow_through_routes(app, store: FollowThroughStore, auth):
    router = APIRouter(prefix='/api/follow-through', dependencies=[Depends(auth)])

    def run(action, *args):
        try:
            return action(*args)
        except ConflictError as exc:
            raise HTTPException(409, str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get('')
    def listing(view: View = 'all', limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        return run(store.list, view, limit, offset)

    @router.post('', status_code=201)
    def create(body: CreateOutcome):
        return {'outcome': run(store.create, body)}

    @router.get('/export')
    def export():
        return JSONResponse(store.export(), headers={
            'Cache-Control': 'no-store',
            'Content-Disposition': 'attachment; filename="helix-follow-through.json"',
        })

    @router.get('/{outcome_id}')
    def get(outcome_id: str):
        return {'outcome': run(store.get, outcome_id)}

    @router.patch('/{outcome_id}')
    def update(outcome_id: str, body: UpdateOutcome):
        return {'outcome': run(store.update, outcome_id, body)}

    @router.delete('/{outcome_id}')
    def delete(outcome_id: str, expected_version: int = Query(ge=1)):
        run(store.delete, outcome_id, expected_version)
        return {'deleted': True, 'source_message_deleted': False,
                'secure_erasure_guaranteed': False}

    app.include_router(router)
