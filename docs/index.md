---
title: sinan-captcha
mkdocs:
  home_access: public
  nav:
    - title: 入门说明
      children:
        - title: 概览
          path: 01-getting-started/index.md
          access: public
    - title: 用户指南
      children:
        - title: 概览
          path: 02-user-guide/index.md
          access: public
        - title: 使用者：Solver 包使用指南
          path: 02-user-guide/solver-package-usage-guide.md
          access: public
        - title: 使用者：Solver 包函数参考
          path: 02-user-guide/solver-package-function-reference.md
          access: public
        - title: 训练者：完整训练操作指南
          path: 02-user-guide/complete-training-operations-guide.md
          access: public
        - title: 训练者：生成器 CLI 全量参考
          path: 02-user-guide/generator-cli-reference.md
          access: public
        - title: 训练者：训练器 CLI 全量参考
          path: 02-user-guide/trainer-cli-reference.md
          access: public
        - title: 训练者：Solver Bundle CLI 参考
          path: 02-user-guide/solver-bundle-cli-reference.md
          access: public
    - title: 开发者指南
      children:
        - title: 概览
          path: 03-developer-guide/index.md
          access: public
        - title: sinanz 集成与资产 staging
          path: 03-developer-guide/solver-bundle-and-integration.md
          access: private
        - title: 接手与冷启动
          path: 03-developer-guide/maintainer-quickstart.md
          access: private
        - title: 仓库结构与边界
          path: 03-developer-guide/repository-structure-and-boundaries.md
          access: private
        - title: 日常开发与验证
          path: 03-developer-guide/local-development-workflow.md
          access: private
        - title: 构建、发版与交付
          path: 03-developer-guide/release-and-delivery-workflow.md
          access: private
    - title: 项目开发文档（内）
      children:
        - title: 概览
          path: 04-project-development/index.md
          access: private
        - title: 项目治理
          children:
            - title: 概览
              path: 04-project-development/01-governance/index.md
              access: private
            - title: 项目章程
              path: 04-project-development/01-governance/project-charter.md
              access: private
        - title: 调研与决策
          children:
            - title: 概览
              path: 04-project-development/02-discovery/index.md
              access: private
            - title: 项目输入
              path: 04-project-development/02-discovery/input.md
              access: private
            - title: 当前状态分析
              path: 04-project-development/02-discovery/current-state-analysis.md
              access: private
            - title: 头脑风暴记录
              path: 04-project-development/02-discovery/brainstorm-record.md
              access: private
        - title: 需求
          children:
            - title: 概览
              path: 04-project-development/03-requirements/index.md
              access: private
            - title: 产品需求文档
              path: 04-project-development/03-requirements/prd.md
              access: private
            - title: 需求分析文档
              path: 04-project-development/03-requirements/requirements-analysis.md
              access: private
            - title: 需求一致性校验
              path: 04-project-development/03-requirements/requirements-verification.md
              access: private
        - title: 设计文档
          children:
            - title: 概览
              path: 04-project-development/04-design/index.md
              access: private
            - title: 技术选型与工程规则
              path: 04-project-development/04-design/technical-selection.md
              access: private
            - title: 系统架构基线
              path: 04-project-development/04-design/system-architecture.md
              access: private
            - title: 背景素材扩充设计
              path: 04-project-development/04-design/background-material-expansion-design.md
              access: private
            - title: 模块边界基线
              path: 04-project-development/04-design/module-boundaries.md
              access: private
            - title: group1 实例匹配重构设计
              path: 04-project-development/04-design/group1-instance-matching-refactor.md
              access: private
            - title: 接口与入口基线
              path: 04-project-development/04-design/api-design.md
              access: private
            - title: Solver 资产导出合同
              path: 04-project-development/04-design/solver-asset-export-contract.md
              access: private
            - title: 多模式验证码样本生成器设计
              path: 04-project-development/04-design/graphic-click-generator-design.md
              access: private
            - title: 模块结构与构建交付设计
              path: 04-project-development/04-design/module-structure-and-delivery.md
              access: private
            - title: 自主训练控制器与 OpenCode 接入设计
              path: 04-project-development/04-design/autonomous-training-and-opencode-design.md
              access: private
        - title: 开发过程文档
          children:
            - title: 概览
              path: 04-project-development/05-development-process/index.md
              access: private
            - title: 零基础落地实施方案
              path: 04-project-development/05-development-process/implementation-plan.md
              access: private
            - title: Windows 训练环境 Checklist
              path: 04-project-development/05-development-process/windows-environment-checklist.md
              access: private
            - title: 样本导出与自动标注 Checklist
              path: 04-project-development/05-development-process/data-export-auto-labeling-checklist.md
              access: private
            - title: 背景素材扩充任务拆解
              path: 04-project-development/05-development-process/background-material-expansion-task-breakdown.md
              access: private
            - title: 多模式验证码生成器任务拆解
              path: 04-project-development/05-development-process/generator-task-breakdown.md
              access: private
            - title: 自主训练任务拆解
              path: 04-project-development/05-development-process/autonomous-training-task-breakdown.md
              access: private
            - title: group1 实例匹配重构任务拆解
              path: 04-project-development/05-development-process/group1-instance-matching-refactor-task-breakdown.md
              access: private
            - title: 独立 solver 迁移任务拆解
              path: 04-project-development/05-development-process/standalone-solver-migration-task-breakdown.md
              access: private
            - title: 自主训练实施准入结论
              path: 04-project-development/05-development-process/autonomous-training-implementation-readiness.md
              access: private
        - title: 测试与验证
          children:
            - title: 概览
              path: 04-project-development/06-testing-verification/index.md
              access: private
        - title: 发布与交付
          children:
            - title: 概览
              path: 04-project-development/07-release-delivery/index.md
              access: private
            - title: 发布说明
              path: 04-project-development/07-release-delivery/release-notes.md
              access: private
            - title: 交付包说明
              path: 04-project-development/07-release-delivery/delivery-package.md
              access: private
            - title: 发布检查清单
              path: 04-project-development/07-release-delivery/release-checklist.md
              access: private
        - title: 运维与维护
          children:
            - title: 概览
              path: 04-project-development/08-operations-maintenance/index.md
              access: private
            - title: 部署说明
              path: 04-project-development/08-operations-maintenance/deployment-guide.md
              access: private
            - title: 维护运行手册
              path: 04-project-development/08-operations-maintenance/operations-runbook.md
              access: private
        - title: 演进复盘
          children:
            - title: 概览
              path: 04-project-development/09-evolution/index.md
              access: private
            - title: 纳管复盘与后续演进
              path: 04-project-development/09-evolution/retrospective.md
              access: private
        - title: 追踪矩阵
          children:
            - title: 概览
              path: 04-project-development/10-traceability/index.md
              access: private
            - title: 需求追踪矩阵
              path: 04-project-development/10-traceability/requirements-matrix.md
              access: private
---
# sinan-captcha

这是 `sinan-captcha` 的正式项目文档源。AI 软件工厂在项目仓库内直接维护这些文档，`docs-stratego` 通过 Git 子模块或等价的仓级挂载方式聚合展示，但不反向改写源文档。

## 适用范围

- 根 `docs/index.md` 的 front matter 是目录树、页面路径和访问级别的唯一事实源。
- Markdown 页面、OpenAPI 契约和 MCP tools 快照统一作为正式页面资产维护。
- 契约文件必须放在真实文档目录下，并与所在目录的 `index.md` 配套。

## 维护规则

- 只有根 `docs/index.md` 声明全站 `mkdocs.nav`、页面路径和页面权限。
- 子目录 `index.md` 只作为正文首页和资源权限锚点，不再承担导航声明职责。
- 页面、图片和附件跟随所属目录维护；资源文件放在当前目录或当前目录的 `assets/` 下，`assets/` 不承载 Markdown 页面或契约文件。
- 仓内链接统一使用相对路径，不写机器绝对路径。
- 新增、删除或移动 Markdown 页面或契约文件后，同步刷新根 `docs/index.md` 的目录树；子目录 `index.md` 只保留正文概览。
