# AI 软件工厂规则

这个项目遵循阶段化的软件工厂工作流。
当前版本只落地 `Codex / Gemini CLI` 直接使用方式。

项目根目录：`.`
项目名称：`sinan-captcha`

AI 运行时协议：
- `../shanforge/skills/software-factory-cli/references/ai-runtime-protocol.md`
- `../shanforge/skills/software-factory-cli/references/ai-role-charter.md`

共享全局 skills：
- `brainstorming`: 在实施前探索产品意图、约束条件、备选方案，并完成设计确认。 (../shanforge/skills/brainstorming/SKILL.md)
- `document-templates`: 初始化并维护标准的 docs/ 和 .factory/ 文档结构。 (../shanforge/skills/document-templates/SKILL.md)
- `requirements-engineering`: 用稳定 ID 编写 REQ、NFR、验收标准和需求分析文档。 (../shanforge/skills/requirements-engineering/SKILL.md)
- `doc-coauthoring`: 通过迭代方式共同创作设计文档、提案和决策文档。 (../shanforge/skills/doc-coauthoring/SKILL.md)
- `api-design`: 设计资源导向的 API，包括状态码、校验、分页和错误契约。 (../shanforge/skills/api-design/SKILL.md)
- `backend-patterns`: 设计服务层、仓储层、中间件、校验和数据访问模式。 (../shanforge/skills/backend-patterns/SKILL.md)
- `python-uv-project`: 在 Python 项目中统一使用 uv 管理 Python 版本、虚拟环境、依赖、锁文件与开发工具，并约束 pyproject、pytest、ruff、mypy 工作流。 (../shanforge/skills/python-uv-project/SKILL.md)
- `crawler4j-model-project`: 开发 crawler4j 标准 model/模块项目时，优先使用 crawler4j SDK CLI、module.yaml 契约和 Core 调试链路。 (../shanforge/skills/crawler4j-model-project/SKILL.md)
- `frontend-patterns`: 实现 React 组件、状态管理、数据流和可访问的响应式界面模式。 (../shanforge/skills/frontend-patterns/SKILL.md)
- `ui-ux-pro-max`: 生成 UI 体系、配色、字体和页面结构建议。 (../shanforge/skills/ui-ux-pro-max/SKILL.md)
- `tdd-workflow`: 通过测试、覆盖率和回归验证驱动实施过程。 (../shanforge/skills/tdd-workflow/SKILL.md)
- `webapp-testing`: 在需要界面验证时，用 Playwright 驱动本地 Web 应用测试。 (../shanforge/skills/webapp-testing/SKILL.md)

工作规则：
- 默认先读 AI 运行时协议，再读当前项目事实；不要默认全文加载人类长文档。
- `AGENTS.md` / `GEMINI.md` 只保留稳定协作规则、读取顺序和边界；安装结果、测试结论、当前运行状态写入 `.factory/project.json`、`.factory/memory/current-state.md` 和阶段文档。
- 开始工作前先阅读 `docs/04-project-development/01-governance/project-charter.md` 和 `docs/04-project-development/02-discovery/input.md`。
- 始终保持正式 `docs/` 与隐藏控制面 `/.factory/` 同步。
- 当前 V1 不以 API 平台为执行入口，而是直接在本地 CLI 工具中协作。
- 使用稳定 ID：`REQ-*`、`NFR-*`、`ARCH-*`、`MOD-*`、`API-*`、`DATA-*`、`UI-*`、`TASK-*`、`TC-*`、`CR-*`、`BUG-*`、`REL-*`、`OPS-*`。
- 进入代码开发后，使用 `factory-pr-start / factory-pr-review / factory-pr-merge` 维护 PR 闭环。
- 进入实现前先确认 `docs/04-project-development/04-design/technical-selection.md` 已明确技术选型、必装模块、工程规则和后台范围。
- 默认额外读取 `/.factory/memory/motivation-state.md`、`/.factory/memory/autonomy-rules.md`、`/.factory/memory/evolution-baseline.md`，维持团队高主动性但不越界。
- 遇到阻塞、空转、证据不足或质量漂移时，优先执行 `factory-recovery-coach`，而不是重复施压。
- 发现单点问题时优先做 `factory-pattern-fix` 模式级扫描，再把有效做法沉淀到 `factory-evolution-baseline`。
- 若 UX/UI 需要评审或交接，优先用 `factory-design-assets` 把可直观看到的设计交付物写入 `docs/04-project-development/04-design/ux-ui-design.md`。
- 需求阶段不要只停留在大纲；PRD 和需求分析应尽量详细，并在进入设计前执行 `factory-requirements-verify`。
- 如需和远程仓库协作，使用 `factory-pr-remote-open / factory-pr-remote-sync / factory-pr-remote-merge`。
- 不要跳阶段。需求和设计审批必须先于实施。
- 涉及创意、功能或方案设计时，先使用 `brainstorming`。
- 进入实现阶段后，遵循 `tdd-workflow`。
- 对于需求变更和缺陷修复，除了更新受影响文档，还要同步更新 `.factory/memory/current-state.md` 和 `.factory/memory/change-summary.md`。
