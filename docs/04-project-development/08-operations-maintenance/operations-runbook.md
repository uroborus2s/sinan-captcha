# 维护运行手册

- 项目名称：sinan-captcha
- 当前阶段：IMPLEMENTATION
- 最近更新：2026-04-05

## 1. 本地运行主线

### 训练机主线

- 环境检查：
  - `uv run sinan env check`
- 训练目录初始化：
  - `uvx --from sinan-captcha sinan env setup-train --train-root <train-root>`
- 训练：
  - `uv run sinan train group1 ...`
  - `uv run sinan train group2 ...`
- 测试：
  - `uv run sinan test group1 ...`
  - `uv run sinan test group2 ...`
- 评估：
  - `uv run sinan evaluate ...`
- 自主训练：
  - `uv run sinan auto-train ...`

### 生成器主线

- 工作区初始化：
  - `sinan-generator workspace init --workspace <generator-workspace>`
- 素材导入 / 获取：
  - `sinan-generator materials import ...`
  - `sinan-generator materials fetch ...`
- 数据集导出：
  - `sinan-generator make-dataset ...`

## 2. 当前稳定构建与验证

### Python

- 构建：
  - `uv run sinan release build --project-dir .`
- 测试：
  - `uv run python -m unittest discover -s tests/python -p 'test_*.py'`

### Go

- 构建：
  - `go build -o dist/generator/<platform>/sinan-generator ./cmd/sinan-generator`
- 测试：
  - `go test ./...`

## 3. 当前发布与部署线索

### 已稳定

- Python wheel / sdist
- Go 生成器二进制
- 面向训练机的 Windows 交付包
- 训练目录初始化和训练运行路径

### 仍待继续收口

- solver bundle 纳入正式 `package-windows`
- 根 `sinan` CLI 注册 `solve`
- 面向最终调用方的 solver 部署主线

## 4. 日常维护动作

### 发布前

- 确认 Python 包可构建
- 确认 Go 二进制可构建
- 确认用户文档和开发者文档未漂移
- 确认 `.factory/memory/current-state.md` 与 `change-summary.md` 已同步

### 问题定位时

- 先判断问题属于：
  - 生成器
  - 数据契约
  - 训练与评估
  - 自主训练
  - solver / bundle
- 再判断问题属于：
  - 当前稳定主线
  - 目标态但未完全接通的交付主线

## 5. 常见风险与处理原则

### 训练机环境异常

- 先检查 `uv`、Python、PyTorch、CUDA 和驱动组合
- 先恢复 `env check` 通过，再继续训练

### 生成器样本或素材异常

- 先检查素材完整解码和 QA 结果
- 任何无法证明真值正确的样本不得进入 `gold`

### 自主训练异常

- 先检查 study 状态文件是否完整
- agent 输出异常时，优先确认是否已回退到规则模式

### solver 交付异常

- 先区分是目标态说明还是当前稳定交付物
- 当前若问题来源于“bundle 尚未进入正式交付包”，应按发布差距处理，不要伪装成运维事故

## 6. 维护注意事项

- 先确保当前稳定入口仍然可用，再推进功能变更
- 任何对外行为变化都必须同步到公开文档
- 任何发布与部署变化都必须同步到内部发布文档和 `.factory`
- 任何线上或交付问题先记录 `BUG-*` 或 `CR-*`，再安排修复和回归
