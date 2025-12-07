import argparse
import json
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(base_url: str, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    url = base_url.rstrip("/") + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req) as resp:  # nosec - only called against locally running API
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except HTTPError as exc:  # pragma: no cover - helper for manual seeding
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{method} {url} failed ({exc.code}): {body}") from exc


def ensure_active_sprint(base_url: str) -> Dict[str, Any]:
    active = request(base_url, "GET", "/api/sprints/active")
    if active:
        return active

    today = date.today()
    payload = {
        "name": f"Sprint {today.isoformat()}",
        "goal": "交付核心功能并完成技术债务收敛",
        "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=7)).isoformat(),
        "status": "ACTIVE",
    }
    return request(base_url, "POST", "/api/sprints", payload)


def create_story(base_url: str, sprint_id: int, story: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "title": story["title"],
        "description": story["description"],
        "story_points": story["story_points"],
        "priority": story.get("priority", 3),
        "is_tech_debt": story.get("is_tech_debt", False),
        "sprint_id": sprint_id,
        "status": story.get("status", "PLANNED"),
    }
    return request(base_url, "POST", "/api/stories", payload)


def create_task(base_url: str, story_id: int, task: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "title": task["title"],
        "story_id": story_id,
        "story_points": task["story_points"],
        "status": task.get("status", "TODO"),
        "is_tech_debt": task.get("is_tech_debt", False),
        "assignee": task.get("assignee"),
    }
    return request(base_url, "POST", "/api/tasks", payload)


def send_demo_webhook(base_url: str, linked_task_ids: List[int]) -> Any:
    if not linked_task_ids:
        return None

    demo_repo = os.getenv("DEVSPRINT_DEMO_REPO", "octocat/Hello-World")
    demo_pr_url = os.getenv(
        "DEVSPRINT_DEMO_PR_URL", "https://github.com/octocat/Hello-World/pull/1"
    )
    demo_commit_hash = os.getenv(
        "DEVSPRINT_DEMO_COMMIT", "7fd1a60b01f91b314f59955a4e4d4f5a5d5f90a3"
    )

    commit_target = linked_task_ids[0]
    pr_target = linked_task_ids[-1]
    payload = {
        "repository": {"full_name": demo_repo},
        "commits": [
            {
                "id": demo_commit_hash,
                "message": f"Optimize pipeline cache Ref #{commit_target}",
            }
        ],
        "pull_request": {
            "title": f"Ref #{pr_target} Improve deployment readiness",
            "body": f"Ref #{pr_target} Adds smoke checks before deploy",
            "html_url": demo_pr_url,
        },
    }
    return request(base_url, "POST", "/api/github/webhook", payload)


def has_existing_tasks(base_url: str) -> bool:
    tasks = request(base_url, "GET", "/api/tasks")
    return bool(tasks)


def seed(base_url: str, force: bool = False) -> None:
    if not force and has_existing_tasks(base_url):
        print("⚠️  检测到已有任务数据，跳过灌入。使用 --force 可以重复生成 demo 数据。")
        return

    sprint = ensure_active_sprint(base_url)
    print(f"✅ Sprint 就绪：{sprint['name']} (ID: {sprint['id']})")

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
                    "status": "IN_PROGRESS",
                    "assignee": "alice",
                },
                {
                    "title": "接入 OAuth2 SSO",
                    "story_points": 3,
                    "status": "TODO",
                    "assignee": "bob",
                },
                {
                    "title": "安全扫描遗留项修复",
                    "story_points": 2,
                    "status": "TODO",
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
                    "status": "DONE",
                    "assignee": "carol",
                },
                {
                    "title": "看板列内拖拽排序",
                    "story_points": 3,
                    "status": "TODO",
                    "assignee": "dave",
                },
                {
                    "title": "为技术债务卡片增加高亮",
                    "story_points": 2,
                    "status": "CODE_REVIEW",
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
                    "status": "IN_PROGRESS",
                    "assignee": "erin",
                },
                {
                    "title": "部署前烟囱检查",
                    "story_points": 3,
                    "status": "CODE_REVIEW",
                    "assignee": "frank",
                },
                {
                    "title": "回滚脚本与演练手册",
                    "story_points": 2,
                    "status": "TODO",
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
                    "status": "DONE",
                    "assignee": "grace",
                },
                {
                    "title": "告警抑制与值班转派规则",
                    "story_points": 3,
                    "status": "TODO",
                    "assignee": "heidi",
                },
            ],
        },
    ]

    created_tasks: List[int] = []
    for story_def in story_defs:
        story = create_story(base_url, sprint["id"], story_def)
        print(f" → Story #{story['id']} 创建完成：{story['title']}")
        for task_def in story_def["tasks"]:
            task = create_task(base_url, story["id"], task_def)
            created_tasks.append(task["id"])
            print(f"    · Task #{task['id']} [{task['status']}] {task['title']}")

    webhook = send_demo_webhook(base_url, created_tasks)
    if webhook:
        print(f"🔗 GitHub webhook 关联成功，任务列表：{webhook.get('linked_tasks')}")

    print("🎉 Demo 数据灌入完成，刷新前端即可看到看板、燃尽图与 Code Review 队列。")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo Sprint/Story/Task data via API.")
    parser.add_argument(
        "--base",
        default="http://localhost:8000",
        help="后端 API 基础地址，默认 http://localhost:8000",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使已有任务数据也强制生成 demo 数据",
    )
    args = parser.parse_args()

    seed(args.base, args.force)


if __name__ == "__main__":
    main()
