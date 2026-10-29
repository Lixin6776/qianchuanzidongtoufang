from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import MaterialExperimentCreate, MaterialExperimentRead
from app.services.material_experiments import MaterialExperimentService

router = APIRouter(prefix="/api/material-experiments", tags=["material-experiments"])


class StopMaterialExperiment(BaseModel):
    reason: str = ""


@router.get("", response_model=list[MaterialExperimentRead])
def list_material_experiments(db: Annotated[Session, Depends(get_db)]):
    return MaterialExperimentService(db).list()


@router.post("", response_model=MaterialExperimentRead, status_code=201)
def create_material_experiment(
    payload: MaterialExperimentCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return MaterialExperimentService(db).create(payload)


@router.post("/{experiment_id}/start", response_model=MaterialExperimentRead)
def start_material_experiment(
    experiment_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return MaterialExperimentService(db).start(experiment_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{experiment_id}/evaluate", response_model=MaterialExperimentRead)
def evaluate_material_experiment(
    experiment_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        analyses = request.app.state.material_analysis_store.list_analyses()
        return MaterialExperimentService(db).evaluate(experiment_id, analyses)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{experiment_id}/stop", response_model=MaterialExperimentRead)
def stop_material_experiment(
    experiment_id: str,
    payload: StopMaterialExperiment,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return MaterialExperimentService(db).stop(experiment_id, payload.reason)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
