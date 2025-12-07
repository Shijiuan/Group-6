## DevSprint_Project Demo

---

## 技术栈
- 后端: Python, FastAPI, SQLAlchemy, APScheduler
- 前端: React, TypeScript, Ant Design
- 接口文档: Swagger UI (`http://localhost:8000/docs`)
- 数据库: MySQL（默认 `mysql+pymysql://root:password@localhost:3306/devsprint_db`）

---

## 构建数据库
1) 启动本地 MySQL（示例：`net start mysql80`，按本机服务名调整）。
2) 初始化库表：`mysql -u root -p < 2.sql`。

---

## 启动后端
1) 进入 `backend`，安装依赖：`pip install -r requirements.txt`。
2) 如需修改数据库连接，设置环境变量 `DATABASE_URL`。
3) 运行：`uvicorn main:app --reload`。
4) 若不想自动灌入 Demo 数据，启动前设置 `DEVSPRINT_SEED_DEMO=0`。

---

## 启动前端
1) 进入 `frontend`，安装依赖：`npm install`。
2) 启动：`npm start`。
3) 浏览器访问 [http://localhost:3000](http://localhost:3000)。

---

## 初始化示例数据
默认数据库为空时，前端看板是空板。可用以下方式快速填充 Sprint / Story / Task，体验燃尽图、剩余天数、技术债务与 Code Review 队列：

- **一键生成（自动或手动）**
  - 自动：后端启动且任务表为空时，会自动灌入 Demo 数据。若不想自动生成，启动前设置 `DEVSPRINT_SEED_DEMO=0`。
  - 手动：执行 `python backend/seed_demo_data.py --base http://localhost:8000`；需要重置示例时追加 `--force`。
  - Demo 链接默认指向 GitHub 示例仓库 `octocat/Hello-World`，可用 `DEVSPRINT_DEMO_REPO` / `DEVSPRINT_DEMO_PR_URL` / `DEVSPRINT_DEMO_COMMIT` 自定义。

- **手动调用 API 示例**
  - 创建 Sprint  
    `curl -X POST http://localhost:8000/api/sprints -H "Content-Type: application/json" -d "{\"name\":\"Demo Sprint\",\"goal\":\"完成前端看板演示\",\"start_date\":\"2024-11-25\",\"end_date\":\"2024-12-02\",\"status\":\"ACTIVE\"}"`
  - 创建 Story（替换 `sprint_id`）  
    `curl -X POST http://localhost:8000/api/stories -H "Content-Type: application/json" -d "{\"title\":\"看板体验提升\",\"description\":\"- 支持 Markdown\\n- 优化列排序\",\"story_points\":5,\"priority\":2,\"sprint_id\":1}"`
  - 创建 Task  
    `curl -X POST http://localhost:8000/api/tasks -H "Content-Type: application/json" -d "{\"title\":\"实现列内拖拽\",\"story_id\":1,\"story_points\":3,\"status\":\"IN_PROGRESS\",\"assignee\":\"alice\"}"`

- **模拟 GitHub Webhook**
  - 触发 Code Review 队列或 commit 关联（将仓库与链接替换为你的实际项目）：  
    `curl -X POST http://localhost:8000/api/github/webhook -H "Content-Type: application/json" -d "{\"repository\":{\"full_name\":\"demo/devsprint\"},\"commits\":[{\"id\":\"abc123\",\"message\":\"Ref #1 调整登录流程\"}],\"pull_request\":{\"title\":\"Ref #1 修复登录超时\",\"body\":\"Ref #1\",\"html_url\":\"https://github.com/demo/devsprint/pull/1\"}}"`

---

## 模拟进度与剩余天数
- 燃尽图支持“模拟天数”按钮：可模拟 +1/+3 天或输入自定义天数，自动推进任务状态（TODO → IN_PROGRESS → CODE_REVIEW → DONE），并生成对应日期的燃尽快照。
- 可点击“设置剩余天数”直接指定当前 Sprint 的剩余天数（非负整数），系统会调整模拟日期偏移，倒计时和燃尽图随之更新。
- 如果所有任务都已完成，模拟时会自动生成一条技术债务任务，确保燃尽与看板有可见变化。
