import logging
import os
import re
from datetime import date, timedelta
from enum import Enum
from typing import Dict, List, Optional, Union

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

logging.basicConfig(level=logging.INFO)

# 1. 数据库配置
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:cx315926@localhost:3306/devsprint_db",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 模拟天数偏移（用于前端“模拟天数”按钮，单位：天）
SIMULATION_OFFSET_DAYS = 0


def get_today() -> date:
    return date.today() + timedelta(days=SIMULATION_OFFSET_DAYS)


class SprintStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    CODE_REVIEW = "CODE_REVIEW"
    DONE = "DONE"


class UserStoryStatus(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    DONE = "DONE"


# 2. 定义数据库模型
class SprintModel(Base):
    __tablename__ = "sprints"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    goal = Column(String(500), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(20), default=SprintStatus.ACTIVE.value)

    stories = relationship(
        "UserStoryModel",
        back_populates="sprint",
        cascade="all, delete-orphan",
    )
    snapshots = relationship(
        "BurndownSnapshotModel",
        back_populates="sprint",
        cascade="all, delete-orphan",
    )


class UserStoryModel(Base):
    __tablename__ = "user_stories"

    id = Column(Integer, primary_key=True, index=True)
    sprint_id = Column(Integer, ForeignKey("sprints.id", ondelete="SET NULL"))
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    story_points = Column(Integer, nullable=False)
    priority = Column(Integer, default=3)
    is_tech_debt = Column(Boolean, default=False)
    status = Column(String(20), default=UserStoryStatus.PLANNED.value)

    sprint = relationship("SprintModel", back_populates="stories")
    tasks = relationship(
        "TaskModel",
        back_populates="story",
        cascade="all, delete-orphan",
    )


class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("user_stories.id", ondelete="CASCADE"))
    title = Column(String(255), nullable=False)
    status = Column(String(20), default=TaskStatus.TODO.value)
    story_points = Column(Integer, nullable=False)
    is_tech_debt = Column(Boolean, default=False)
    assignee = Column(String(255), nullable=True)

    story = relationship("UserStoryModel", back_populates="tasks")
    github_links = relationship(
        "GitHubLinkModel",
        back_populates="task",
        cascade="all, delete-orphan",
    )


class GitHubLinkModel(Base):
    __tablename__ = "github_links"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"))
    commit_hash = Column(String(100), nullable=True)
    pr_url = Column(String(500), nullable=True)
    repo_name = Column(String(255), nullable=True)

    task = relationship("TaskModel", back_populates="github_links")


class BurndownSnapshotModel(Base):
    __tablename__ = "burndown_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    sprint_id = Column(Integer, ForeignKey("sprints.id", ondelete="CASCADE"))
    snapshot_date = Column(Date, default=date.today)
    remaining_points = Column(Integer, default=0)

    sprint = relationship("SprintModel", back_populates="snapshots")


Base.metadata.create_all(bind=engine)


# 3. Pydantic 模型
class GitHubLinkResponse(BaseModel):
    id: int
    commit_hash: Optional[str]
    pr_url: Optional[str]
    repo_name: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class TaskBase(BaseModel):
    title: str
    story_id: int
    story_points: int = Field(..., ge=1)
    status: TaskStatus = TaskStatus.TODO
    is_tech_debt: bool = False
    assignee: Optional[str] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[TaskStatus] = None
    story_points: Optional[int] = Field(None, ge=1)
    is_tech_debt: Optional[bool] = None
    assignee: Optional[str] = None


class TaskResponse(TaskBase):
    id: int
    github_links: List[GitHubLinkResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class UserStoryBase(BaseModel):
    title: str
    description: Optional[str] = None
    story_points: int = Field(..., ge=1)
    priority: int = Field(ge=1, le=5, default=3)
    is_tech_debt: bool = False
    sprint_id: Optional[int] = None
    status: UserStoryStatus = UserStoryStatus.PLANNED


class UserStoryCreate(UserStoryBase):
    pass


class UserStoryUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    story_points: Optional[int] = Field(None, ge=1)
    priority: Optional[int] = Field(None, ge=1, le=5)
    is_tech_debt: Optional[bool] = None
    sprint_id: Optional[int] = None
    status: Optional[UserStoryStatus] = None


class UserStoryResponse(UserStoryBase):
    id: int
    tasks: List[TaskResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SprintBase(BaseModel):
    name: str
    goal: Optional[str] = None
    start_date: date
    end_date: date
    status: SprintStatus = SprintStatus.ACTIVE


class SprintCreate(SprintBase):
    pass


class SprintUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[SprintStatus] = None


class SprintResponse(SprintBase):
    id: int
    stories: List[UserStoryResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class BurndownPoint(BaseModel):
    day: str
    ideal: float
    actual: float


class DashboardResponse(BaseModel):
    sprint: Optional[SprintResponse] = None
    burndown: List[BurndownPoint] = Field(default_factory=list)
    review_queue: List[TaskResponse] = Field(default_factory=list)
    tech_debt_points: int = 0
    sprint_countdown_days: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# 4. FastAPI 初始化
app = FastAPI(title="DevSprint API", description="Agile Task Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def calculate_remaining_points(db: Session, sprint_id: int) -> int:
    remaining = (
        db.query(func.coalesce(func.sum(UserStoryModel.story_points), 0))
        .filter(
            UserStoryModel.sprint_id == sprint_id,
            UserStoryModel.status != UserStoryStatus.DONE.value,
        )
        .scalar()
    )
    return remaining or 0


def build_burndown_payload(
    db: Session, sprint: SprintModel
) -> List[BurndownPoint]:
    if not sprint.start_date or not sprint.end_date:
        return []

    total_days = (sprint.end_date - sprint.start_date).days + 1
    total_days = max(total_days, 1)
    total_points = sum(story.story_points for story in sprint.stories)
    total_points = max(total_points, 0)

    snapshots = (
        db.query(BurndownSnapshotModel)
        .filter(BurndownSnapshotModel.sprint_id == sprint.id)
        .order_by(BurndownSnapshotModel.snapshot_date)
        .all()
    )
    snapshot_map: Dict[date, int] = {
        snap.snapshot_date: snap.remaining_points for snap in snapshots
    }

    current_day = sprint.start_date
    last_actual = total_points
    burndown_points: List[BurndownPoint] = []

    for index in range(total_days):
        ideal_remaining = total_points - (
            index * total_points / max(total_days - 1, 1)
        )
        if current_day in snapshot_map:
            last_actual = snapshot_map[current_day]
        burndown_points.append(
            BurndownPoint(
                day=f"Day {index + 1}",
                ideal=max(ideal_remaining, 0),
                actual=max(last_actual, 0),
            )
        )
        current_day = current_day + timedelta(days=1)

    if burndown_points and not snapshots:
        # 如果尚未生成快照，则使用实时剩余点数填充最终点
        burndown_points[-1].actual = calculate_remaining_points(db, sprint.id)

    return burndown_points


def sync_story_status(db: Session, story: UserStoryModel) -> None:
    if not story.tasks:
        return
    if all(task.status == TaskStatus.DONE.value for task in story.tasks):
        story.status = UserStoryStatus.DONE.value
    elif any(task.status in (TaskStatus.IN_PROGRESS.value, TaskStatus.CODE_REVIEW.value) for task in story.tasks):
        story.status = UserStoryStatus.ACTIVE.value
    else:
        story.status = UserStoryStatus.PLANNED.value


def link_commit_to_task(
    db: Session, task: TaskModel, commit_hash: str, repo_name: Optional[str]
):
    link = GitHubLinkModel(
        task_id=task.id,
        commit_hash=commit_hash,
        repo_name=repo_name,
    )
    db.add(link)


def link_pr_to_task(
    db: Session, task: TaskModel, pr_url: str, repo_name: Optional[str]
):
    link = GitHubLinkModel(
        task_id=task.id,
        pr_url=pr_url,
        repo_name=repo_name,
    )
    task.status = TaskStatus.CODE_REVIEW.value
    db.add(link)


# 5. API - Sprint & Story
@app.post("/api/sprints", response_model=SprintResponse)
def create_sprint(payload: SprintCreate, db: Session = Depends(get_db)):
    sprint = SprintModel(**payload.dict())
    if sprint.end_date < sprint.start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    return sprint


@app.get("/api/sprints", response_model=List[SprintResponse])
def list_sprints(db: Session = Depends(get_db)):
    return db.query(SprintModel).all()


@app.get("/api/sprints/active", response_model=Optional[SprintResponse])
def get_active_sprint(db: Session = Depends(get_db)):
    return (
        db.query(SprintModel)
        .filter(SprintModel.status == SprintStatus.ACTIVE.value)
        .order_by(SprintModel.start_date)
        .first()
    )


@app.patch("/api/sprints/{sprint_id}", response_model=SprintResponse)
def update_sprint(
    sprint_id: int, payload: SprintUpdate, db: Session = Depends(get_db)
):
    sprint = db.get(SprintModel, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(sprint, key, value)
    if sprint.end_date < sprint.start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    db.commit()
    db.refresh(sprint)
    return sprint


@app.post("/api/stories", response_model=UserStoryResponse)
def create_story(payload: UserStoryCreate, db: Session = Depends(get_db)):
    if payload.sprint_id:
        sprint = db.get(SprintModel, payload.sprint_id)
        if not sprint:
            raise HTTPException(status_code=404, detail="Sprint not found")
    story = UserStoryModel(**payload.dict())
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


@app.patch("/api/stories/{story_id}", response_model=UserStoryResponse)
def update_story(
    story_id: int, payload: UserStoryUpdate, db: Session = Depends(get_db)
):
    story = db.get(UserStoryModel, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    update_data = payload.dict(exclude_unset=True)
    if "sprint_id" in update_data and update_data["sprint_id"]:
        sprint = db.get(SprintModel, update_data["sprint_id"])
        if not sprint:
            raise HTTPException(status_code=404, detail="Sprint not found")
    for key, value in update_data.items():
        setattr(story, key, value)
    db.commit()
    db.refresh(story)
    return story


@app.get("/api/stories/{story_id}", response_model=UserStoryResponse)
def get_story(story_id: int, db: Session = Depends(get_db)):
    story = db.get(UserStoryModel, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return story


# 6. API - Task
@app.get("/api/tasks", response_model=List[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    return db.query(TaskModel).all()


@app.post("/api/tasks", response_model=TaskResponse)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    story = db.get(UserStoryModel, payload.story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    task = TaskModel(**payload.dict())
    db.add(task)
    db.commit()
    db.refresh(task)
    sync_story_status(db, story)
    db.commit()
    db.refresh(task)
    return task


@app.patch("/api/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(TaskModel, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    if task.story:
        sync_story_status(db, task.story)
        db.commit()
        db.refresh(task)
    return task


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(TaskModel, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    story = task.story
    db.delete(task)
    db.commit()
    if story:
        sync_story_status(db, story)
        db.commit()
    return None


# 7. API - GitHub 集成
commit_ref_pattern = re.compile(r"ref\s+#(\d+)", re.IGNORECASE)


@app.post("/api/github/webhook")
def github_webhook(payload: dict = Body(...), db: Session = Depends(get_db)):
    repo_name = payload.get("repository", {}).get("full_name")
    processed_tasks: List[int] = []

    for commit in payload.get("commits", []):
        message = commit.get("message", "")
        for match in commit_ref_pattern.findall(message):
            task = db.get(TaskModel, int(match))
            if task:
                link_commit_to_task(db, task, commit.get("id"), repo_name)
                processed_tasks.append(task.id)

    pull_request = payload.get("pull_request")
    if pull_request:
        text = f"{pull_request.get('title', '')}\n{pull_request.get('body', '')}"
        pr_url = pull_request.get("html_url")
        for match in commit_ref_pattern.findall(text):
            task = db.get(TaskModel, int(match))
            if task:
                link_pr_to_task(db, task, pr_url, repo_name)
                processed_tasks.append(task.id)

    db.commit()

    return {"linked_tasks": processed_tasks}


# 8. API - 燃尽图与仪表盘
@app.get("/api/burndown/{sprint_id}", response_model=List[BurndownPoint])
def get_burndown(sprint_id: int, db: Session = Depends(get_db)):
    sprint = db.get(SprintModel, sprint_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return build_burndown_payload(db, sprint)


@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    sprint = (
        db.query(SprintModel)
        .filter(SprintModel.status == SprintStatus.ACTIVE.value)
        .order_by(SprintModel.start_date)
        .first()
    )
    burndown: List[BurndownPoint] = []
    tech_debt_points = 0
    countdown = None
    if sprint:
        burndown = build_burndown_payload(db, sprint)
        tech_debt_points = sum(
            story.story_points for story in sprint.stories if story.is_tech_debt
        )
        countdown = (sprint.end_date - get_today()).days

    review_queue = (
        db.query(TaskModel)
        .filter(TaskModel.status == TaskStatus.CODE_REVIEW.value)
        .all()
    )

    return DashboardResponse(
        sprint=sprint,
        burndown=burndown,
        review_queue=review_queue,
        tech_debt_points=tech_debt_points,
        sprint_countdown_days=countdown,
    )


# 9. 轮询任务：GitHub 同步 & 燃尽记录
def capture_burndown_snapshots(for_date: Optional[date] = None):
    db = SessionLocal()
    try:
        target_date = for_date or get_today()
        active_sprints = (
            db.query(SprintModel)
            .filter(SprintModel.status == SprintStatus.ACTIVE.value)
            .all()
        )
        for sprint in active_sprints:
            remaining = calculate_remaining_points(db, sprint.id)
            snapshot = (
                db.query(BurndownSnapshotModel)
                .filter(
                    BurndownSnapshotModel.sprint_id == sprint.id,
                    BurndownSnapshotModel.snapshot_date == target_date,
                )
                .first()
            )
            if snapshot:
                snapshot.remaining_points = remaining
            else:
                db.add(
                    BurndownSnapshotModel(
                        sprint_id=sprint.id,
                        snapshot_date=target_date,
                        remaining_points=remaining,
                    )
                )
        db.commit()
    except Exception as exc:
        logging.exception("Failed to capture burndown snapshots: %s", exc)
        db.rollback()
    finally:
        db.close()


def poll_github_updates():
    # 这里可以扩展调用 GitHub API，同步最新 commit/PR
    logging.info("GitHub polling executed - integrate with GitHub API here.")


def simulate_progress(db: Session) -> None:
    sprint = (
        db.query(SprintModel)
        .filter(SprintModel.status == SprintStatus.ACTIVE.value)
        .order_by(SprintModel.start_date)
        .first()
    )
    if not sprint:
        return

    def pick_task(status: TaskStatus):
        return (
            db.query(TaskModel)
            .join(UserStoryModel)
            .filter(
                TaskModel.status == status.value,
                UserStoryModel.sprint_id == sprint.id,
            )
            .order_by(TaskModel.is_tech_debt.desc(), TaskModel.id)
            .first()
        )

    def ensure_tech_debt_task():
        story = (
            db.query(UserStoryModel)
            .filter(UserStoryModel.sprint_id == sprint.id)
            .order_by(UserStoryModel.priority, UserStoryModel.id)
            .first()
        )
        if not story:
            story = UserStoryModel(
                sprint_id=sprint.id,
                title="Tech Debt Fixes",
                description="- 自动生成的技术债务故事\n- 清理告警与代码异味",
                story_points=5,
                priority=1,
                is_tech_debt=True,
            )
            db.add(story)
            db.flush()
        task = TaskModel(
            story_id=story.id,
            title="处理技术债务项",
            status=TaskStatus.TODO.value,
            story_points=2,
            is_tech_debt=True,
            assignee=None,
        )
        db.add(task)
        db.flush()
        return task

    code_review_task = pick_task(TaskStatus.CODE_REVIEW)
    in_progress_task = pick_task(TaskStatus.IN_PROGRESS)
    todo_task = pick_task(TaskStatus.TODO)

    if code_review_task:
        code_review_task.status = TaskStatus.DONE.value
        if code_review_task.story:
            sync_story_status(db, code_review_task.story)
        logging.info("Simulated progress: Task #%s -> DONE", code_review_task.id)
    elif in_progress_task:
        in_progress_task.status = TaskStatus.CODE_REVIEW.value
        if in_progress_task.story:
            sync_story_status(db, in_progress_task.story)
        logging.info("Simulated progress: Task #%s -> CODE_REVIEW", in_progress_task.id)
    elif todo_task:
        todo_task.status = TaskStatus.IN_PROGRESS.value
        if todo_task.story:
            sync_story_status(db, todo_task.story)
        logging.info("Simulated progress: Task #%s -> IN_PROGRESS", todo_task.id)
    else:
        # 没有未完成任务时自动生成一条技术债务任务，确保燃尽与列变化
        new_td = ensure_tech_debt_task()
        logging.info("Simulated progress: created tech debt Task #%s", new_td.id)
    db.commit()


scheduler = BackgroundScheduler(timezone=os.getenv("TZ", "UTC"))
scheduler.add_job(capture_burndown_snapshots, "cron", hour=0, minute=0)
scheduler.add_job(poll_github_updates, "interval", minutes=10)


def _env_flag(name: str, default: str = "1") -> bool:
    value = os.getenv(name, default)
    return value is not None and value.lower() in {"1", "true", "yes", "y", "on"}


def seed_demo_data(db: Session) -> None:
    if db.query(TaskModel).count() > 0:
        logging.info("Demo data seeding skipped: tasks already exist.")
        return

    demo_repo = os.getenv("DEVSPRINT_DEMO_REPO", "octocat/Hello-World")
    demo_pr_url = os.getenv(
        "DEVSPRINT_DEMO_PR_URL", "https://github.com/octocat/Hello-World/pull/1"
    )
    demo_commit_hash = os.getenv(
        "DEVSPRINT_DEMO_COMMIT", "7fd1a60b01f91b314f59955a4e4d4f5a5d5f90a3"
    )

    today = get_today()
    sprint = SprintModel(
        name=f"Sprint {today.isoformat()}",
        goal="交付核心功能并完成技术债务收敛",
        start_date=today,
        end_date=today + timedelta(days=7),
        status=SprintStatus.ACTIVE.value,
    )
    db.add(sprint)
    db.flush()

    story_defs = [
        {
            "title": "登录与权限收敛",
            "description": "- 支持企业 SSO\n- 登录失败时记录审计日志\n- 梳理角色权限矩阵",
            "story_points": 8,
            "priority": 1,
            "tasks": [
                {
                    "title": "实现基础登录接口",
                    "story_points": 3,
                    "status": TaskStatus.IN_PROGRESS.value,
                    "assignee": "alice",
                },
                {
                    "title": "接入 OAuth2 SSO",
                    "story_points": 3,
                    "status": TaskStatus.TODO.value,
                    "assignee": "bob",
                },
                {
                    "title": "安全扫描遗留项修复",
                    "story_points": 2,
                    "status": TaskStatus.TODO.value,
                    "is_tech_debt": True,
                    "assignee": "alice",
                },
            ],
        },
        {
            "title": "团队看板体验提升",
            "description": "- Story 支持 Markdown 展示\n- 优化列内排序与快捷操作\n- 可见性分组与筛选",
            "story_points": 7,
            "priority": 2,
            "tasks": [
                {
                    "title": "支持 Story Markdown 渲染",
                    "story_points": 2,
                    "status": TaskStatus.DONE.value,
                    "assignee": "carol",
                },
                {
                    "title": "看板列内拖拽排序",
                    "story_points": 3,
                    "status": TaskStatus.TODO.value,
                    "assignee": "dave",
                },
                {
                    "title": "为技术债务卡片增加高亮",
                    "story_points": 2,
                    "status": TaskStatus.CODE_REVIEW.value,
                    "is_tech_debt": True,
                    "assignee": "carol",
                },
            ],
        },
        {
            "title": "持续交付与发布安全",
            "description": "- 部署前置健康检查\n- 增加缓存与并行策略\n- 回滚脚本自动化",
            "story_points": 9,
            "priority": 1,
            "tasks": [
                {
                    "title": "流水线缓存与并行优化",
                    "story_points": 4,
                    "status": TaskStatus.IN_PROGRESS.value,
                    "assignee": "erin",
                },
                {
                    "title": "部署前烟囱检查",
                    "story_points": 3,
                    "status": TaskStatus.CODE_REVIEW.value,
                    "assignee": "frank",
                },
                {
                    "title": "回滚脚本与演练手册",
                    "story_points": 2,
                    "status": TaskStatus.TODO.value,
                    "assignee": "erin",
                },
            ],
        },
        {
            "title": "监控告警闭环",
            "description": "- 建立关键 SLI/SLO\n- 引入告警抑制策略\n- 报警可观测性面板",
            "story_points": 6,
            "priority": 3,
            "tasks": [
                {
                    "title": "核心 API SLO 定义与仪表盘",
                    "story_points": 3,
                    "status": TaskStatus.DONE.value,
                    "assignee": "grace",
                },
                {
                    "title": "告警抑制与值班转派规则",
                    "story_points": 3,
                    "status": TaskStatus.TODO.value,
                    "assignee": "heidi",
                },
            ],
        },
    ]

    for story_def in story_defs:
        story = UserStoryModel(
            sprint_id=sprint.id,
            title=story_def["title"],
            description=story_def["description"],
            story_points=story_def["story_points"],
            priority=story_def.get("priority", 3),
            is_tech_debt=story_def.get("is_tech_debt", False),
        )
        db.add(story)
        db.flush()
        for task_def in story_def["tasks"]:
            task = TaskModel(
                story_id=story.id,
                title=task_def["title"],
                status=task_def["status"],
                story_points=task_def["story_points"],
                is_tech_debt=task_def.get("is_tech_debt", False),
                assignee=task_def.get("assignee"),
            )
            db.add(task)
            if task.status == TaskStatus.CODE_REVIEW.value:
                db.flush()
                db.add(
                    GitHubLinkModel(
                        task_id=task.id,
                        pr_url=demo_pr_url,
                        repo_name=demo_repo,
                        commit_hash=demo_commit_hash,
                    )
                )
        sync_story_status(db, story)

    db.commit()
    capture_burndown_snapshots()
    logging.info("Demo data seeded: sprint=%s, stories=%d", sprint.name, len(story_defs))
    # 生成今天的快照
    capture_burndown_snapshots(get_today())


@app.post("/api/simulate/advance_days")
def simulate_advance_days(days: int = Body(..., embed=True)) -> Dict[str, Union[int, str]]:
    if days <= 0:
        raise HTTPException(status_code=400, detail="Days must be positive")
    global SIMULATION_OFFSET_DAYS
    created = 0
    db = SessionLocal()
    try:
        for _ in range(days):
            SIMULATION_OFFSET_DAYS += 1
            simulate_date = get_today()
            simulate_progress(db)
            capture_burndown_snapshots(simulate_date)
            created += 1
    finally:
        db.close()
    return {
        "created_snapshots": created,
        "last_date": simulate_date.isoformat(),
        "current_day": get_today().isoformat(),
        "offset_days": SIMULATION_OFFSET_DAYS,
    }


@app.post("/api/simulate/set_remaining_days")
def simulate_set_remaining_days(
    remaining_days: int = Body(..., embed=True),
) -> Dict[str, Union[int, str]]:
    if remaining_days < 0:
        raise HTTPException(status_code=400, detail="Remaining days must be non-negative")

    global SIMULATION_OFFSET_DAYS
    db = SessionLocal()
    try:
        sprint = (
            db.query(SprintModel)
            .filter(SprintModel.status == SprintStatus.ACTIVE.value)
            .order_by(SprintModel.start_date)
            .first()
        )
        if not sprint:
            raise HTTPException(status_code=404, detail="No active sprint found")

        base_remaining = (sprint.end_date - date.today()).days
        SIMULATION_OFFSET_DAYS = base_remaining - remaining_days
        snapshot_date = get_today()
        capture_burndown_snapshots(snapshot_date)
        return {
            "current_day": snapshot_date.isoformat(),
            "offset_days": SIMULATION_OFFSET_DAYS,
            "remaining_days": remaining_days,
        }
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    if not scheduler.running:
        scheduler.start()
        logging.info("Background scheduler started.")
    if _env_flag("DEVSPRINT_SEED_DEMO", "1"):
        db = SessionLocal()
        try:
            seed_demo_data(db)
        finally:
            db.close()


@app.on_event("shutdown")
def on_shutdown():
    if scheduler.running:
        scheduler.shutdown(wait=False)
