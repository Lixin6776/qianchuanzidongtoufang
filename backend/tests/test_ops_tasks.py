from app.schemas import OpsTaskCreate, OpsTaskUpdate
from app.services.ops_tasks import OpsTaskService


def test_ops_task_lifecycle_assigns_owner_and_completes(db_session):
    service = OpsTaskService(db_session)
    item = service.create(
        OpsTaskCreate(
            title="复盘素材低效问题",
            description="检查低 ROI 素材是否与承接有关",
            owner="投手A",
            priority="high",
            success_criteria="30 分钟内完成归因并给出动作",
            stop_condition="数据未通过校验时暂停判断",
        )
    )
    assert item.status == "open"
    item = service.update(item.id, OpsTaskUpdate(status="in_progress", owner="投手B"))
    assert item.status == "in_progress"
    assert item.owner == "投手B"
    item = service.update(item.id, OpsTaskUpdate(status="done", result="已调整素材测试方向"))
    assert item.status == "done"
    assert item.completed_at is not None
    assert item.result == "已调整素材测试方向"


def test_ops_task_api_create_and_update(client):
    created = client.post(
        "/api/ops-tasks",
        json={
            "title": "验证素材实验",
            "owner": "运营A",
            "priority": "medium",
            "success_criteria": "下一份素材快照 ROI 达标",
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    updated = client.patch(f"/api/ops-tasks/{task_id}", json={"status": "done", "result": "已验证"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "done"
