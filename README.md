# 校园活动管理系统 V1.0

> 实验一：基于工程意图的软件迭代开发
> 技术栈：Python Flask + SQLite（运行依赖仅 flask，无 ORM）

为校园活动的组织与学生参与提供信息化支持：**教师发布并管理活动，学生浏览并报名参与**，报名规则（身份 / 截止时间 / 名额 / 去重 / 归属）全部由服务端强制执行。

## 快速开始

```bash
pip install -r requirements.txt   # 仅 flask
python seed.py                    # 生成演示数据（首次）
python run.py                     # 启动 → http://127.0.0.1:5000
```

运行自动化测试：

```bash
python -m unittest discover -s tests -v
```

### 演示账号（密码均为 123456，密码哈希存储）

| 账号 | 身份 | 说明 |
|---|---|---|
| teacher01 / teacher02 | 教师 | 发布与管理活动（含 7 个覆盖五种状态的样例活动） |
| student01 / student02 / student03 | 学生 | 浏览与报名 |

> 重新生成演示数据：先删除 `instance/campus.db` 再运行 `python seed.py`。
> 数据库与运行时文件均在 `instance/`（已 gitignore，不入库）。

## 目录结构

```
run.py                启动入口
seed.py               演示数据（相对当天生成，覆盖全部活动状态）
app/
  __init__.py         应用工厂：配置/建库/蓝图/模板注入
  config.py           配置（SECRET_KEY 可用环境变量覆盖）
  models.py           数据访问层：三张表 DDL 与全部 SQL
  auth/               账号蓝图（注册/登录/登出/角色装饰器）
  activities/         活动蓝图 ★ 活动业务核心
  templates/  static/ 页面与样式
tests/test_auth.py         账号模块测试（FR-1 注册/登录/权限矩阵）
tests/test_activities.py   活动模块测试（FR-2~FR-11 规则分支）
docs/                 01 需求分析 · 02 工程意图 · 03 软件设计 · 04 验证
```

## 功能一览（V1.0）

| 角色 | 功能 |
|---|---|
| 公开 | 活动列表（动态状态：报名中/报名截止/进行中/已结束/已取消）、活动详情 |
| 学生 | 报名（截止前/未满员/去重）、截止前取消报名、列表"已报名"标识 |
| 教师 | 发布活动（服务端校验时间与容量）、我发布的活动、报名名单、结束/取消活动（仅限本人发布，名单保留） |

业务规则与"候选但未纳入"清单见 [docs/01-需求分析.md](docs/01-需求分析.md)。

## 模块划分

系统按业务切成两个蓝图，互不掺入对方的视图逻辑，全部 SQL 集中在数据访问层：

| 模块 | 目录 | 职责 | 对应需求 |
|---|---|---|---|
| 账号业务 | `app/auth/` | 注册（选身份）、登录/登出、角色权限装饰器 | FR-1 |
| 活动业务 | `app/activities/` | 发布、浏览、报名/取消、名单、结束/取消 | FR-2 ~ FR-11 |
| 数据访问 | `app/models.py` | 三张表 DDL 与全部 SQL | — |

两模块通过两处约定协作，替换任一模块都不影响另一个：`session['user_id']` / `session['role']` 会话键（见 `app/auth/decorators.py`），以及 `users` 表被 `activities.teacher_id`、`registrations.student_id` 外键引用。详见 [docs/03-软件设计.md](docs/03-软件设计.md) §1。

## 文档

- [01 需求分析](docs/01-需求分析.md) — 用户/目标/需求清单/取舍理由
- [02 工程意图](docs/02-工程意图.md) — 版本目标/范围/约束/完成判据
- [03 软件设计](docs/03-软件设计.md) — 模块结构/表 DDL/业务流程图/设计调整记录
- [04 验证](docs/04-验证.md) — 完成标准/自动化测试映射/手工走查清单/验证与确认/已知限制

## Git 说明

仓库本地初始化，按“需求→设计→功能→验证”分阶段逐步提交（提交历史即开发过程记录），已同步双远程：

```bash
git push origin   # GitHub: git@github.com:akauncle/campus_activity_v1.git
git push gitee    # Gitee:  git@gitee.com:akapioggia/campus_activity_v1.git
```

⚠ 提交规范：不提交 `*.db`、`instance/`、密钥 Token；演示密码属业务数据且以哈希存储。

### 软件基线与版本标识

V1.0 满足 [docs/04-验证.md](docs/04-验证.md) §1 全部完成标准的稳定节点，以标签 **`v1.0`** 标识：

```bash
git tag -l          # 查看版本标签
git checkout v1.0   # 回到该基线（只读查看）
```

标签的作用是把此后的反馈、缺陷与修改对应到确定的软件状态，并作为出严重问题时的回退参照。
