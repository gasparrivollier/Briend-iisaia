from datetime import datetime

from fastapi import APIRouter, Depends, Request

from ..alerts import BUENOS_AIRES, AlertResult, run_deadline_check
from ..sessions import protected, require_admin

router = APIRouter(prefix='/api/alertas', tags=['alertas'], dependencies=[*protected, Depends(require_admin)])


@router.post('/ejecutar', response_model=AlertResult)
def execute(request: Request):
    return run_deadline_check(
        request.app.state.engine,
        request.app.state.settings,
        datetime.now(BUENOS_AIRES).date(),
        manual=True,
    )
