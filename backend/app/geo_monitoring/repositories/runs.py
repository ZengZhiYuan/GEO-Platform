"""监测运行与查询任务仓储。"""

from hashlib import sha256

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.geo_monitoring.models import AIPlatform, MonitorRun, Prompt, QueryTask


# 按 ID 查询未删除的监测运行
def get_by_id(db: Session, run_id: int) -> MonitorRun | None:
    return db.execute(
        select(MonitorRun).where(
            MonitorRun.id == run_id,
            MonitorRun.is_deleted.is_(False),
        )
    ).scalar_one_or_none()


# 分页查询监测运行，支持按项目与状态筛选
def list_runs(
    db: Session,
    *,
    page: int,
    page_size: int,
    project_id: int | None = None,
    status: str | None = None,
) -> tuple[list[MonitorRun], int]:
    conditions = [MonitorRun.is_deleted.is_(False)]
    if project_id is not None:
        conditions.append(MonitorRun.project_id == project_id)
    if status:
        conditions.append(MonitorRun.status == status)
    total = db.execute(
        select(func.count()).select_from(MonitorRun).where(*conditions)
    ).scalar_one()
    items = list(
        db.execute(
            select(MonitorRun)
            .where(*conditions)
            .order_by(MonitorRun.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


# 将监测运行实体加入当前会话
def add_run(db: Session, run: MonitorRun) -> None:
    db.add(run)


# 为运行批量生成提示词×平台的查询子任务
def build_query_tasks(
    db: Session,
    run: MonitorRun,
    prompts: list[Prompt],
    platforms: list[AIPlatform],
    *,
    max_attempts: int,
) -> None:
    for prompt in prompts:
        for platform in platforms:
            # 基于运行号、提示词与平台生成幂等键
            key_source = f"{run.run_no}:{prompt.id}:{platform.platform_code}"
            db.add(
                QueryTask(
                    run_id=run.id,
                    prompt_id=prompt.id,
                    platform_code=platform.platform_code,
                    idempotency_key=sha256(key_source.encode("utf-8")).hexdigest(),
                    status="pending",
                    max_attempts=max_attempts,
                    request_json={
                        "prompt_code": prompt.prompt_code,
                        "prompt_text": prompt.prompt_text,
                        "prompt_type": prompt.prompt_type,
                        "scene_tag": prompt.scene_tag,
                        "contains_brand": prompt.contains_brand,
                        "content_hash": prompt.content_hash,
                        "prompt_set_version": run.prompt_set_version,
                    },
                )
            )


# 分页查询运行下的查询子任务，支持按状态与平台筛选
def list_query_tasks(
    db: Session,
    *,
    run_id: int,
    page: int,
    page_size: int,
    status: str | None = None,
    platform_code: str | None = None,
) -> tuple[list[QueryTask], int]:
    conditions = [QueryTask.run_id == run_id, QueryTask.is_deleted.is_(False)]
    if status:
        conditions.append(QueryTask.status == status)
    if platform_code:
        conditions.append(QueryTask.platform_code == platform_code)
    total = db.execute(
        select(func.count()).select_from(QueryTask).where(*conditions)
    ).scalar_one()
    items = list(
        db.execute(
            select(QueryTask)
            .where(*conditions)
            .order_by(QueryTask.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


# 统计监测运行总数量
def count_runs(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(MonitorRun)) or 0
