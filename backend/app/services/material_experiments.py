from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MaterialExperiment
from app.schemas import MaterialExperimentCreate


class MaterialExperimentService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[MaterialExperiment]:
        return list(
            self.session.scalars(
                select(MaterialExperiment).order_by(MaterialExperiment.created_at.desc())
            )
        )

    def create(self, payload: MaterialExperimentCreate) -> MaterialExperiment:
        existing = self.session.scalar(
            select(MaterialExperiment).where(
                MaterialExperiment.analysis_id == payload.analysis_id,
                MaterialExperiment.material_id == payload.material_id,
                MaterialExperiment.action_type == payload.action_type,
            )
        )
        if existing is not None:
            return existing
        item = MaterialExperiment(
            **payload.model_dump(),
            status="suggested",
            result={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def get(self, experiment_id: str) -> MaterialExperiment:
        item = self.session.get(MaterialExperiment, experiment_id)
        if item is None:
            raise LookupError("Material experiment not found")
        return item

    def start(self, experiment_id: str) -> MaterialExperiment:
        item = self.get(experiment_id)
        if item.status not in {"suggested", "observing", "insufficient"}:
            raise ValueError("Material experiment cannot be started in current status")
        now = datetime.now(UTC)
        item.status = "observing"
        item.observation_started_at = now
        item.observation_ends_at = now + timedelta(hours=24)
        item.updated_at = now
        self.session.commit()
        self.session.refresh(item)
        return item

    def stop(self, experiment_id: str, reason: str = "") -> MaterialExperiment:
        item = self.get(experiment_id)
        item.status = "stopped"
        item.result = {**item.result, "stop_reason": reason, "stopped_at": datetime.now(UTC).isoformat()}
        item.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(item)
        return item

    def evaluate(self, experiment_id: str, analyses: list[dict]) -> MaterialExperiment:
        item = self.get(experiment_id)
        if item.status not in {"observing", "insufficient"}:
            raise ValueError("Material experiment is not observing")
        candidates = [
            report
            for report in analyses
            if str(report.get("date") or "") > item.analysis_date
            and self._find_material(report, item.material_id) is not None
        ]
        if not candidates:
            item.status = "insufficient"
            item.result = {
                "verdict": "insufficient_data",
                "note": "还没有更新到该素材的下一份素材分析快照。",
            }
            item.updated_at = datetime.now(UTC)
            self.session.commit()
            self.session.refresh(item)
            return item

        latest = max(candidates, key=lambda report: str(report.get("date") or ""))
        after = self._find_material(latest, item.material_id) or {}
        before = item.baseline_metrics or {}
        deltas = {
            key: round(float(after.get(key) or 0) - float(before.get(key) or 0), 4)
            for key in ("spend", "roi", "orders", "ctr", "conversion_rate")
        }
        criteria = item.success_criteria or {}
        after_roi = after.get("roi")
        if after_roi is None:
            verdict = "insufficient_data"
        elif criteria.get("roi_min") is not None:
            verdict = "positive" if float(after_roi) >= float(criteria["roi_min"]) else "negative"
        elif criteria.get("roi_improvement_min") is not None:
            verdict = (
                "positive"
                if deltas["roi"] >= float(criteria["roi_improvement_min"])
                else "negative"
            )
        else:
            verdict = "positive" if deltas["roi"] > 0.1 else "negative" if deltas["roi"] < -0.1 else "neutral"
        item.status = "completed" if verdict != "insufficient_data" else "insufficient"
        item.result = {
            "verdict": verdict,
            "before": before,
            "after": after,
            "deltas": deltas,
            "snapshot_date": latest.get("date"),
            "observation_only": True,
            "note": "观察性相关，不是因果；结果只基于下一份素材快照。",
        }
        item.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(item)
        return item

    @staticmethod
    def _find_material(report: dict, material_id: str) -> dict | None:
        for material in report.get("materials") or []:
            if str(material.get("material_id") or "") == material_id:
                return material
        return None
