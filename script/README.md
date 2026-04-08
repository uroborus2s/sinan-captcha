# script

当前目录按仓库现状使用 `script/` 命名。

- 这里只放开发阶段使用的辅助脚本。
- 不作为 `sinan`、`sinan-generator` 或 `sinanz` 的正式入口。
- 不应从 `core/`、`generator/` 或 `solver/` 的运行时代码里 import 这里的脚本。
- 依赖浏览器、Playwright、人工输入或外部站点的脚本，应优先放在这里而不是 `core/`。
- `script/crawl/ctrip_login.py` 当前用于开发阶段采集携程验证码素材：
  - 点选模式输出到 `materials/group1/`
  - 滑块模式输出到 `materials/result/`
  - `两者都保存` 模式会连续保存滑块组，直到切到点选后再保存一组点选图并结束当前浏览器会话
