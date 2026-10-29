from app.schemas import MaterialExperimentCreate
from app.services.material_experiments import MaterialExperimentService


def _payload():
    return MaterialExperimentCreate(
        analysis_id="analysis-1",
        analysis_date="2026-10-28",
        material_id="m1",
        material_name="素材A",
        action_type="replicate_winner",
        title="复刻高 ROI 素材",
        reason="ROI 达标",
        baseline_metrics={"spend": 1000, "roi": 1.8, "orders": 10},
        success_criteria={"roi_min": 2.5, "min_orders": 10},
        stop_condition="ROI 低于基线",
    )


def test_material_experiment_starts_and_evaluates_next_snapshot(db_session):
    service = MaterialExperimentService(db_session)
    item = service.create(_payload())
    assert item.status == "suggested"
    item = service.start(item.id)
    assert item.status == "observing"

    evaluated = service.evaluate(
        item.id,
        [
            {
                "date": "2026-10-29",
                "materials": [
                    {"material_id": "m1", "spend": 1400, "roi": 2.8, "orders": 14}
                ],
            }
        ],
    )
    assert evaluated.status == "completed"
    assert evaluated.result["verdict"] == "positive"
    assert evaluated.result["deltas"]["roi"] == 1.0
    assert evaluated.result["observation_only"] is True


def test_material_experiment_without_next_snapshot_is_insufficient(db_session):
    service = MaterialExperimentService(db_session)
    item = service.create(_payload())
    service.start(item.id)
    result = service.evaluate(item.id, [{"date": "2026-10-28", "materials": []}])
    assert result.status == "insufficient"
    assert result.result["verdict"] == "insufficient_data"


def test_material_experiment_can_be_stopped(db_session):
    service = MaterialExperimentService(db_session)
    item = service.create(_payload())
    item = service.start(item.id)
    stopped = service.stop(item.id, "素材表现不符合预期")
    assert stopped.status == "stopped"
    assert stopped.result["stop_reason"] == "素材表现不符合预期"
