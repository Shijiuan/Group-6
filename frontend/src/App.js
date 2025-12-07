import React, { useEffect, useMemo, useState, useCallback } from 'react';
import axios from 'axios';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import './App.css';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

const statusLabels = {
  TODO: 'Todo',
  IN_PROGRESS: 'In Progress',
  CODE_REVIEW: 'Code Review',
  DONE: 'Done'
};

const statusHints = {
  TODO: '待开发',
  IN_PROGRESS: '开发中',
  CODE_REVIEW: '等待评审',
  DONE: '已完成'
};

marked.use({ breaks: true });

const renderMarkdown = (value) => ({
  __html: DOMPurify.sanitize(marked.parse(value || '_尚无描述_'))
});

function App() {
  const [tasks, setTasks] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newPoints, setNewPoints] = useState('3');
  const [newAssignee, setNewAssignee] = useState('');
  const [newTechDebt, setNewTechDebt] = useState(false);
  const handleCopyTask = (task) => {
    if (navigator?.clipboard) {
      navigator.clipboard
        .writeText(`[Task #${task.id}] ${task.title}`)
        .catch(() => {});
    }
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [taskRes, dashboardRes] = await Promise.all([
        axios.get(`${API_BASE}/api/tasks`),
        axios.get(`${API_BASE}/api/dashboard`)
      ]);
      setTasks(taskRes.data);
      setDashboard(dashboardRes.data);
      setError('');
    } catch (err) {
      console.error(err);
      setError('无法加载数据，请检查后端服务。');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleEditStoryMarkdown = async (story) => {
    const nextMarkdown = window.prompt('更新此用户故事的 Markdown 描述：', story?.description || '');
    if (nextMarkdown === null) return;
    setBusy(true);
    try {
      await axios.patch(`${API_BASE}/api/stories/${story.id}`, { description: nextMarkdown });
      await fetchData();
    } catch (err) {
      console.error(err);
      setError('更新描述失败，请稍后重试。');
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteTask = async (task) => {
    const ok = window.confirm(`确定删除任务 #${task.id} 吗？此操作不可恢复。`);
    if (!ok) return;
    setBusy(true);
    try {
      await axios.delete(`${API_BASE}/api/tasks/${task.id}`);
      await fetchData();
    } catch (err) {
      console.error(err);
      setError('删除任务失败，请稍后重试。');
    } finally {
      setBusy(false);
    }
  };

  const handleSimulateDay = async (count = 1) => {
    setSimulating(true);
    try {
      await axios.post(`${API_BASE}/api/simulate/advance_days`, { days: count });
      await fetchData();
    } catch (err) {
      console.error(err);
      setError('模拟天数失败，请检查后端服务。');
    } finally {
      setSimulating(false);
    }
  };

  const handleSimulateCustom = () => {
    const input = window.prompt('请输入要模拟的天数（正整数）：', '1');
    if (!input) return;
    const parsed = parseInt(input, 10);
    if (Number.isNaN(parsed) || parsed <= 0) {
      setError('请输入有效的正整数天数。');
      return;
    }
    handleSimulateDay(parsed);
  };

  const handleSetRemainingDays = async () => {
    const input = window.prompt('设置自定义剩余天数（>=0）：', '5');
    if (input === null) return;
    const parsed = parseInt(input, 10);
    if (Number.isNaN(parsed) || parsed < 0) {
      setError('请输入有效的非负整数天数。');
      return;
    }
    setSimulating(true);
    try {
      await axios.post(`${API_BASE}/api/simulate/set_remaining_days`, {
        remaining_days: parsed
      });
      await fetchData();
    } catch (err) {
      console.error(err);
      setError('设置剩余天数失败，请检查后端服务。');
    } finally {
      setSimulating(false);
    }
  };


  const handleCreateTodo = async () => {
    const sprint = dashboard?.sprint;
    if (!sprint) {
      setError('请先创建一个 Sprint。');
      return;
    }
    if (!newTitle.trim()) {
      setError('请输入任务标题。');
      return;
    }
    const points = parseInt(newPoints, 10);
    if (Number.isNaN(points) || points <= 0) {
      setError('Story Points 需为正整数。');
      return;
    }
    setBusy(true);
    try {
      const storyRes = await axios.post(`${API_BASE}/api/stories`, {
        title: newTitle,
        description: newDescription,
        story_points: points,
        priority: 3,
        sprint_id: sprint.id,
        is_tech_debt: newTechDebt
      });
      await axios.post(`${API_BASE}/api/tasks`, {
        title: newTitle,
        story_id: storyRes.data.id,
        story_points: points,
        status: 'TODO',
        assignee: newAssignee || null,
        is_tech_debt: newTechDebt
      });
      setNewTitle('');
      setNewDescription('');
      setNewPoints('3');
      setNewAssignee('');
      setNewTechDebt(false);
      await fetchData();
      setError('');
    } catch (err) {
      console.error(err);
      setError('创建 TODO 失败，请稍后重试。');
    } finally {
      setBusy(false);
    }
  };


  const storyLookup = useMemo(() => {
    const lookup = {};
    dashboard?.sprint?.stories?.forEach((story) => {
      lookup[story.id] = story;
    });
    return lookup;
  }, [dashboard]);

  const columns = useMemo(() => {
    const result = {
      TODO: [],
      IN_PROGRESS: [],
      CODE_REVIEW: [],
      DONE: []
    };
    tasks.forEach((task) => {
      const column = result[task.status] || result.TODO;
      column.push(task);
    });
    return result;
  }, [tasks]);

  const burndownData = dashboard?.burndown || [];
  const reviewQueue = dashboard?.review_queue || [];
  const sprint = dashboard?.sprint;
  const totalPoints =
    sprint?.stories?.reduce((sum, story) => sum + story.story_points, 0) || 0;
  const remainingPoints =
    burndownData.length > 0
      ? burndownData[burndownData.length - 1].actual
      : totalPoints;
  const progress =
    totalPoints === 0
      ? 0
      : Math.max(
          0,
          Math.min(100, Math.round(((totalPoints - remainingPoints) / totalPoints) * 100))
        );
  const techDebtPoints = dashboard?.tech_debt_points || 0;
  const countdown = dashboard?.sprint_countdown_days;

  if (loading) {
    return (
      <div className="app loading-state">
        <div className="spinner" />
        <p>正在加载 DevSprint 数据...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app error-state">
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <p className="eyebrow">DevSprint · Sprint Control Center</p>
          <h1>冲刺规划 & 实时追踪</h1>
          <p className="subtitle">
            聚焦开发者体验：故事点、燃尽图、Code Review 队列一个面板搞定。
          </p>
        </div>
        <div className="header-meta">
          <span className="status-dot" />
          {sprint ? sprint.name : '尚未创建 Sprint'}
        </div>
      </header>

      <section className="summary-grid">
        <div className="summary-card">
          <p className="label">Sprint 目标</p>
          <h2>{sprint?.goal || '为下一次发布交付核心能力'}</h2>
          <div className="meta-row">
            <span>
              点数完成度 <strong>{progress}%</strong>
            </span>
            {typeof countdown === 'number' && (
              <span className={countdown >= 0 ? 'countdown' : 'countdown overdue'}>
                {countdown >= 0 ? `剩余 ${countdown} 天` : `超时 ${Math.abs(countdown)} 天`}
              </span>
            )}
          </div>
        </div>

        <div className="summary-card">
          <p className="label">技术债务 (Story Points)</p>
          <h2 className="tech-debt">{techDebtPoints}</h2>
          <p className="muted">在 Sprint 中应尽快优先处理</p>
        </div>

        <div className="summary-card">
          <p className="label">Code Review 队列</p>
          <h2>{reviewQueue.length}</h2>
          <p className="muted">开发者等待审查的任务数</p>
        </div>
      </section>

      <section className="main-grid">
        <div className="kanban-panel">
          <div className="panel-header">
            <div>
              <p className="label">当前冲刺</p>
              <h2>看板视图</h2>
            </div>
            <p className="muted">支持 Markdown 的任务说明，双击卡片即可复制，点击“编辑”可修改描述</p>
          </div>
          <div className="create-form">
            <div className="form-row">
              <input
                type="text"
                placeholder="Todo 标题（必填）"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                disabled={busy}
              />
              <input
                type="number"
                min="1"
                placeholder="Story Points"
                value={newPoints}
                onChange={(e) => setNewPoints(e.target.value)}
                disabled={busy}
              />
              <input
                type="text"
                placeholder="Assignee（可选）"
                value={newAssignee}
                onChange={(e) => setNewAssignee(e.target.value)}
                disabled={busy}
              />
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={newTechDebt}
                  onChange={(e) => setNewTechDebt(e.target.checked)}
                  disabled={busy}
                />
                技术债务
              </label>
            </div>
            <textarea
              placeholder="用户故事描述（支持 Markdown，可选）"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              disabled={busy}
            />
            <button className="ghost-btn primary" onClick={handleCreateTodo} disabled={busy}>
              创建 TODO
            </button>
          </div>
          <div className="kanban-columns">
            {Object.keys(columns).map((status) => (
              <div className="kanban-column" key={status}>
                <div className="column-header">
                  <span>{statusLabels[status]}</span>
                  <span className="hint">{statusHints[status]}</span>
                  <span className="count-badge">{columns[status].length}</span>
                </div>
                <div className="column-body">
                  {columns[status].map((task) => {
                    const story = storyLookup[task.story_id];
                    const buildLinkUrl = (link) => {
                      if (link.pr_url) return link.pr_url;
                      if (link.repo_name && link.commit_hash) {
                        return `https://github.com/${link.repo_name}/commit/${link.commit_hash}`;
                      }
                      return '#';
                    };
                    return (
                      <article
                        className={`task-card ${
                          task.is_tech_debt ? 'tech-debt-card' : ''
                        }`}
                        key={task.id}
                        title={`Task #${task.id}`}
                        onDoubleClick={() => handleCopyTask(task)}
                      >
                        <div className="task-head">
                          <p className="task-title">{task.title}</p>
                          <span className={`status-pill status-${status.toLowerCase()}`}>
                            {statusLabels[status]}
                          </span>
                        </div>
                        <div className="task-meta">
                          <span>SP {task.story_points}</span>
                          {task.assignee && <span>@{task.assignee}</span>}
                          {task.is_tech_debt && <span>Tech Debt</span>}
                        </div>
                        {story && (
                          <div
                            className="task-markdown"
                            dangerouslySetInnerHTML={renderMarkdown(story.description)}
                          />
                        )}
                        <div className="task-actions">
                          {story && (
                            <button
                              className="ghost-btn"
                              onClick={() => handleEditStoryMarkdown(story)}
                              disabled={busy}
                            >
                              编辑描述
                            </button>
                          )}
                          <button
                            className="ghost-btn danger"
                            onClick={() => handleDeleteTask(task)}
                            disabled={busy}
                          >
                            删除
                          </button>
                        </div>
                        {task.github_links?.length > 0 && (
                          <div className="task-links">
                            {task.github_links.map((link) => (
                              <a
                                key={link.id}
                                href={buildLinkUrl(link)}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {link.pr_url ? 'PR' : 'Commit'}
                              </a>
                            ))}
                          </div>
                        )}
                      </article>
                    );
                  })}
                  {columns[status].length === 0 && (
                    <div className="empty-column">暂无任务</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="analytics-panel">
          <div className="chart-card">
            <div className="panel-header">
              <div>
                <p className="label">燃尽图</p>
                <h2>Ideal vs Actual</h2>
              </div>
              <div className="chart-actions">
                <p className="muted">每日凌晨自动快照</p>
                <button
                  className="ghost-btn"
                  onClick={() => handleSimulateDay(1)}
                  disabled={simulating}
                >
                  模拟 +1 天
                </button>
                <button
                  className="ghost-btn"
                  onClick={() => handleSimulateDay(3)}
                  disabled={simulating}
                >
                  模拟 +3 天
                </button>
                <button
                  className="ghost-btn"
                  onClick={handleSimulateCustom}
                  disabled={simulating}
                >
                  自定义天数
                </button>
                <button
                  className="ghost-btn"
                  onClick={handleSetRemainingDays}
                  disabled={simulating}
                >
                  设置剩余天数
                </button>
              </div>
            </div>
            <div className="chart-wrapper">
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={burndownData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2d3848" />
                  <XAxis dataKey="day" stroke="#9fb4d9" />
                  <YAxis stroke="#9fb4d9" />
                  <Tooltip
                    contentStyle={{ background: '#111827', border: '1px solid #374151' }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="ideal"
                    stroke="#38bdf8"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="actual"
                    stroke="#f472b6"
                    strokeWidth={3}
                    dot
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="review-card">
            <div className="panel-header">
              <div>
                <p className="label">Code Review Queue</p>
                <h2>待审查任务</h2>
              </div>
              <p className="muted">GitHub PR 创建后自动转入</p>
            </div>
            <ul className="review-list">
              {reviewQueue.length === 0 && <li className="empty-column">暂无排队任务</li>}
              {reviewQueue.map((task) => (
                <li key={task.id}>
                  <div>
                    <p className="task-title">{task.title}</p>
                    <p className="muted">
                      {storyLookup[task.story_id]?.title || '未关联用户故事'}
                    </p>
                  </div>
                  <div className="task-meta">
                    {task.assignee ? `@${task.assignee}` : '未指派'}
                    <span>SP {task.story_points}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}

export default App;
