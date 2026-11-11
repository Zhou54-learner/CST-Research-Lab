# CST Research Lab

从独立设计、操作和解释物理，走向算法优化与可复用的自动化研究系统。

**日常入口：[学习仪表盘](index.html)**（下载后双击，在浏览器中打开）。GitHub 文件页展示 HTML 源码；本项目暂不发布网站。

首页直接显示当前项目、下一步、项目完成情况、待回访问题与能力状态。侧栏进入项目任务、能力依据、实验记录和学习记忆。学习实验与环境测试分别显示，未开展的学习如实留空；完整路线作为查阅资料。

- [学习路线](CST学习路线.md)：已审定的目标、项目顺序和教学尺度。
- [协作与数据协议](docs/协作与数据协议.md)：文件如何组织、不同 agent 如何接续、实验如何追溯。
- [环境与验证](docs/环境与验证.md)：本机检查、闭环测试和已知限制。
- [学习状态](learning-state.json)：进度、能力依据与可纠正的学习记忆。概览由它及运行记录生成。

## 日常用法

和 AI 说明当前任务、已经尝试的内容与观察即可。AI 在阶段结束时更新学习状态和概览。能力状态依据你的实际表现更新；自动测试通过不代表你已掌握对应知识。

在项目目录的 PowerShell 中运行：

```powershell
# 首次准备，已有 .venv 时跳过
py -3.11 -m venv .venv

# 检查设备与 CST Python 接口
.\.venv\Scripts\python.exe tools\lab.py doctor --cst-install 'F:\CST Studio Suite 2025'

# 无 CST 的最小数据闭环
.\.venv\Scripts\python.exe tools\lab.py smoke --backend analytic

# 真实 CST 小型波导算例：仅基础设施测试，不是 P1 学习任务
.\.venv\Scripts\python.exe tools\lab.py smoke --backend cst --length-mm 10

# 更新学习概览并检查文件关联
.\.venv\Scripts\python.exe tools\lab.py refresh
.\.venv\Scripts\python.exe tools\lab.py check
```

当前工具只依赖 Python 标准库与本机 CST 自带接口，不需要 OpenAI API 密钥、MCP 服务或常驻进程。数值分析库在项目需要时再加入。迁移设备后重新创建虚拟环境并执行 `doctor`。

## 目录

```text
CST学习路线.md              核心路线
AGENTS.md                   AI 协作入口
learning-state.json         唯一学习状态源
index.html                  可离线打开的学习概览
docs/                       简明协议与环境验证说明
tools/                      检查、运行、更新页面的小工具
ui/dashboard.html           页面模板
runs/<运行编号>/             每次实验的输入、摘要、原始数据与证据
.local/                     本机路径、临时求解工作区、浏览器检查缓存（不入库）
```

首个真实项目展开时才建立 `projects/P1/`，不预先创建整套空目录。

## 版本与备份

仓库：[Zhou54-learner/CST-Research-Lab](https://github.com/Zhou54-learner/CST-Research-Lab)。本项目的路线、协议、状态、工具、页面和有用实验成果均进入 Git。虚拟环境、机器路径配置、临时缓存、凭据和软件安装文件不进入仓库；这些不是研究成果。CST 小型模型及对应原始数据随实验保留。后续如出现超过 GitHub 单文件限制的大模型，再配置 Git LFS 或独立数据备份，不把大结果静默丢弃。

每个有意义的阶段提交并推送；当前没有后台同步服务。仓库目前为公开可见，初次同步只包含本学习项目内容，不采集组内文件或桌面记录。

本次从原 `F:\CST-Learning-Lab` 迁入路线；此目录为后续主副本，原位置不继续并行更新。
