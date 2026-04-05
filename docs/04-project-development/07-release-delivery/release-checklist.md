# 发布检查清单

- 文档状态：生效
- 当前阶段：IMPLEMENTATION
- 目标读者：项目维护者、发布负责人
- 最近更新：2026-04-05

## 1. Python 包发布前

- `uv run sinan release build --project-dir .` 成功
- 目标 wheel 出现在 `dist/`
- 版本号与文档一致
- Python 测试已回归
- 与发布相关文档已同步

## 2. Go 生成器发布前

- 目标平台二进制构建成功
- `go test ./...` 成功
- 生成器命令口径与公开文档一致
- 工作区与 preset 约定没有漂移

## 3. Windows 训练交付包发布前

- Python wheel 已生成
- Windows 版 `sinan-generator.exe` 已生成
- `uv run sinan release package-windows ...` 成功
- 交付包包含：
  - `python/`
  - `generator/`
  - `README-交付包说明.txt`
- 如需附带数据或素材，目录来源已确认且说明已同步

## 4. solver 交付发布前

以下条件在当前代码完全接通前视为发布门槛：

- solver bundle 已生成
- bundle manifest 校验通过
- 统一求解入口已可稳定加载 bundle
- 调用说明已更新
- 版本映射已记录

当前附加检查：

- 根 `sinan` CLI 是否已注册 `solve`
- `package-windows` 或等价交付流程是否已纳入 bundle

如果上述两项仍未完成：

- 不得把 solver bundle 标记为“正式标准交付包”

## 5. 文档与记忆层同步

- `docs/` 中涉及发布与部署的页面已同步
- `.factory/memory/current-state.md` 已同步
- `.factory/memory/change-summary.md` 已同步
- 需求追踪矩阵已同步

## 6. 发布后复核

- 交付目录可在新路径下复现
- 安装说明与实际交付物一致
- 未把未完成能力写成已完成
- 新旧版本可比较、可回滚、可追溯
