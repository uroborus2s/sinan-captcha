# scripts

当前目录按仓库现状使用 `scripts/` 命名。

- 这里只放开发阶段使用的辅助脚本。
- 不作为 `sinan`、`sinan-generator` 或 `sinanz` 的正式入口。
- 不应从 `core/`、`generator/` 或 `solver/` 的运行时代码里 import 这里的脚本。
- 依赖浏览器、Playwright、人工输入或外部站点的脚本，应优先放在这里而不是 `core/`。
- `scripts/crawl/ctrip_login.py` 当前用于开发阶段采集携程验证码素材：
  - 点选模式输出到 `materials/group1/`
  - 滑块模式输出到 `materials/result/`
  - 滑块图片当前保存为 `bg.jpg` 和 `gap.jpg`
  - `两者都保存` 模式会连续保存滑块组，直到切到点选后再保存一组点选图并结束当前浏览器会话
- `scripts/organize_group2_gap_shapes.py` 当前用于整理 `materials/result/*/gap.jpg`：
  - 按轮廓特征自动去重
  - 文件名按“短家族名 + 短特征码”生成
  - 基名当前控制在 `20` 个字符以内，且不含数字
  - 例如会输出 `heart_abcdwxyz.png`、`badge_abcdwxyz.png`
  - 输出到 `materials/incoming/group2/`
- `scripts/organize_group1_query_icons.py` 当前用于整理 `materials/business_exams/group1/reviewed-v1/import/query/*`：
  - 自动切分 query 条里的单个小图标
  - 按二值形状相似度聚类
  - 输出代表图、总览图和 `manifest.json`
  - 当前输出到 `materials/incoming/group1_query_clusters/`
  - 用于后续人工命名 query 图标类型，并补齐生成器 `group1/icons/<class>/` 素材池
- `scripts/download_group1_candidate_icons.py` 当前用于根据
  `materials/incoming/group1_query_clusters/semantic_candidates.json`
  下载首批官方开源相近图标：
  - 当前支持从 Tabler 图标页提取 SVG
  - 会按 `class_name` 落盘到 `materials/incoming/group1_icon_candidates/`
  - 会同时拷贝 cluster 代表图，方便人工比对“真实 query 图标 vs 外部候选图标”
- `scripts/build_group1_generator_icon_pack.py` 当前用于把
  `materials/incoming/group1_icon_candidates/` 扩展并转换为 generator 可直接导入的 `group1` 素材包：
  - 会为高置信类追加一批 Lucide 官方 raw SVG
  - 会合并 `materials/incoming/old/` 中的旧图标目录
  - 会通过 `qlmanage` 把 SVG 光栅化为 PNG
  - 会把白底转透明、裁切主体并补透明留白
  - 最终输出到 `materials/incoming/group1_icon_pack/`
  - 会同步生成 `manifests/materials.yaml` 与 `manifests/group1.classes.yaml`
