# Gemini 项目说明

你正在一个共享的软件工厂工作区中工作。
当前版本只落地 `Codex / Gemini CLI` 直接使用方式。

项目根目录：`.`
项目名称：`sinan-captcha`

优先阅读（运行时）：
- `../shanforge/skills/software-factory-cli/references/ai-runtime-protocol.md`
- `../shanforge/skills/software-factory-cli/references/ai-role-charter.md`
- `docs/04-project-development/01-governance/project-charter.md`
- `docs/04-project-development/02-discovery/input.md`
- `.factory/project.json`

共享 skill 引用：
- `brainstorming`: ../shanforge/skills/brainstorming/SKILL.md
- `document-templates`: ../shanforge/skills/document-templates/SKILL.md
- `requirements-engineering`: ../shanforge/skills/requirements-engineering/SKILL.md
- `doc-coauthoring`: ../shanforge/skills/doc-coauthoring/SKILL.md
- `api-design`: ../shanforge/skills/api-design/SKILL.md
- `backend-patterns`: ../shanforge/skills/backend-patterns/SKILL.md
- `python-uv-project`: ../shanforge/skills/python-uv-project/SKILL.md
- `crawler4j-model-project`: ../shanforge/skills/crawler4j-model-project/SKILL.md
- `frontend-patterns`: ../shanforge/skills/frontend-patterns/SKILL.md
- `ui-ux-pro-max`: ../shanforge/skills/ui-ux-pro-max/SKILL.md
- `tdd-workflow`: ../shanforge/skills/tdd-workflow/SKILL.md
- `webapp-testing`: ../shanforge/skills/webapp-testing/SKILL.md

Gemini CLI 推荐职责：
- 头脑风暴和方案探索
- PRD 与需求分析
- 架构设计与 API 设计
- 变更影响分析
- 发布说明与验收复查

规则：
- 默认先按 AI 运行时协议工作，不要默认全文加载长篇工作流说明。
- `AGENTS.md` / `GEMINI.md` 不是现状快照；当前安装、构建、测试和运行结论应写入 `.factory/project.json`、`.factory/memory/current-state.md` 和阶段文档。
- 把 Markdown 文档当成事实来源
- 当前 V1 以本地 CLI 协作为主，不以 API 平台作为执行入口
- 需求和设计未获批准前，不要进入代码实现
- 进入实现前先读取 `docs/04-project-development/04-design/technical-selection.md`，确认当前技术栈、模块清单和后台要求
- 默认补读 `/.factory/memory/motivation-state.md`、`/.factory/memory/autonomy-rules.md`、`/.factory/memory/evolution-baseline.md`，维持高主动性但不越界
- 遇到阻塞、空转、证据不足或质量漂移时，优先执行恢复教练，不要重复同一路径
- 发现问题后优先做模式级修复，再把有效做法沉淀到自进化基线
- UX/UI 文档允许包含图片、HTML 原型、流程图和外部原型链接等设计交付物，必要时用 `factory-design-assets` 录入并引用
- 编写需求文档时尽量详细，完成后执行 `factory-requirements-verify` 反复比对 PRD 与需求分析，避免遗漏需求
- 代码类工作项在关单前需要完成 PR 创建、评审和合并
- 如果项目接入了远程仓库，优先用 `factory-pr-remote-open / sync / merge` 把远端状态同步回本地文档
- 任何已接受内容变更后，都要同步更新 `/.factory/memory/` 摘要
