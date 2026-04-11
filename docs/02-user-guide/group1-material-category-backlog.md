# 训练者角色：`group1` 素材类别补齐清单

这页只服务一件事：

- 围绕生成器素材包，把 `group1` 需要支持的类别补齐。

这里**不以当前某一轮训练数据集为准**，而是以素材类别体系为准。

也就是说：

- 这页先决定“素材包里应该有哪些 `group1` 类别”。
- 这页不讨论当前 `firstpass`、`v1`、`round2` 有没有启用某个类。
- 预训练模型只用来帮你发现缺口，不负责决定最终素材类别合同。

## 1. 使用原则

这份 backlog 只记录两类条目：

1. 素材包里已经存在，确认继续保留的类别
2. 人工审核过程中发现、当前素材包里还没有，但业务上需要新增的类别

这里的工作顺序固定为：

1. 先人工审核图片
2. 发现无法精确归类的图标，先记到这份 backlog
3. 我们一起确认类别名称、中文名、描述和边界
4. 再补 `group1.classes.yaml` 和 `group1/icons/<class_name>/`
5. 最后再生成新数据版本并重训

## 2. 当前素材包已存在的 `group1` 类别

当前素材包清单来源：

- [materials/incoming/group1_icon_pack/manifests/group1.classes.yaml](../../materials/incoming/group1_icon_pack/manifests/group1.classes.yaml)
- [materials/incoming/group1_icon_pack/group1/icons](../../materials/incoming/group1_icon_pack/group1/icons)

当前已存在的素材类别如下：

| 类别名                    | 中文名    | 素材目录已存在 |
| ---------------------- | ------ | ------- |
| `icon_smile`           | 笑脸     | 是       |
| `icon_mail`            | 信封     | 是       |
| `icon_check_circle`    | 勾选圆章   | 是       |
| `icon_flag`            | 旗帜     | 是       |
| `icon_briefcase`       | 公文包    | 是       |
| `icon_remote_screen`   | 遥控器与屏幕 | 是       |
| `icon_inbox`           | 收件箱    | 是       |
| `icon_bell`            | 铃铛     | 是       |
| `icon_heart`           | 心形     | 是       |
| `icon_bolt`            | 闪电     | 是       |
| `icon_train`           | 列车     | 是       |
| `icon_shopping_cart`   | 购物车    | 是       |
| `icon_yen_shield`      | 日元盾牌   | 是       |
| `icon_letter_a_circle` | 圆形字母A  | 是       |
| `icon_cloud_download`  | 云下载    | 是       |
| `icon_anchor`          | 锚      | 是       |
| `icon_lantern`         | 灯笼     | 是       |
| `icon_knot`            | 结饰     | 是       |
| `icon_star`            | 星星     | 是       |
| `icon_seated_person`   | 坐姿人物   | 是       |
| `icon_compass`         | 指南针    | 是       |
| `icon_key`             | 钥匙     | 是       |
| `icon_christmas_tree`  | 松树     | 是       |
| `icon_climbing`        | 攀岩人物   | 是       |
| `icon_headset`         | 耳机     | 是       |
| `icon_speedboat`       | 快艇     | 是       |
| `icon_luggage`         | 行李箱    | 是       |
| `icon_flame`           | 火焰     | 是       |
| `icon_microphone`      | 麦克风    | 是       |
| `icon_shield_plus`     | 十字盾牌   | 是       |
| `icon_hiking`          | 徒步人物   | 是       |
| `icon_plane`           | 飞机     | 是       |
| `icon_users`           | 多人     | 是       |
| `icon_bicycle`         | 自行车    | 是       |
| `icon_camera`          | 相机     | 是       |
| `icon_car`             | 汽车     | 是       |
| `icon_flower`          | 花朵     | 是       |
| `icon_gift`            | 礼物     | 是       |
| `icon_globe`           | 地球     | 是       |
| `icon_house`           | 房子     | 是       |
| `icon_leaf`            | 叶子     | 是       |
| `icon_lock`            | 锁      | 是       |
| `icon_music`           | 音乐     | 是       |
| `icon_paw`             | 爪印     | 是       |
| `icon_ship`            | 轮船     | 是       |
| `icon_tree`            | 树      | 是       |
| `icon_umbrella`        | 雨伞     | 是       |

## 3. 待补齐的新类别

这一节留给人工审核时持续追加。

填写规则：

- `建议类别名`
  - 统一使用 `icon_<english_name>` 形式
- `中文名`
  - 用于人工审核和沟通
- `图形描述`
  - 用一句话描述视觉特征
- `不要混到哪些旧类`
  - 避免把近似图标错误并类
- `样本状态`
  - `待收集`
  - `已有截图`
  - `已有素材`
  - `已补到素材包`
- `备注`
  - 填当前争议点、边界说明或示例来源

| 建议类别名               | 中文名    | 图形描述              | 不要混到哪些旧类                                         | 样本状态 | 备注                                                 |
| ------------------- | ------ | ----------------- | ------------------------------------------------ | ---- | -------------------------------------------------- |
| `icon_map_marker`   | 地图定位点  | 地图底座上方带空心定位针的图标   | `icon_compass`、`icon_globe`、`icon_remote_screen` | 已有截图 | 来自人工审核截图，当前素材包里无精确对应类                              |
| `icon_broken_image` | 破损图片   | 方框图片中间带裂缝或折线断裂的图标 | `icon_camera`、`icon_remote_screen`、`icon_mail`   | 已有截图 | 来自人工审核截图，当前素材包里无精确对应类                              |
| `icon_beach_chair`  | 沙滩椅遮阳伞 | 躺椅上方有遮阳伞的度假图标     | `icon_umbrella`、`icon_seated_person`             | 已有截图 | 不建议硬并到 `icon_umbrella`                             |
| `icon_island`       | 海岛棕榈树  | 小岛地形上带棕榈树的图标      | `icon_tree`、`icon_umbrella`、`icon_beach_chair`   | 已有截图 | 来自人工审核截图，当前素材包里无精确对应类                              |
| `icon_pavilion`     | 亭子门楼   | 对称屋顶和立柱结构的亭台或门楼图标 | `icon_house`、`icon_remote_screen`、`icon_anchor`  | 已有截图 | 来自人工审核截图，当前素材包里无精确对应类；后续也可评估是否更适合命名为 `icon_temple` |
| `icon_letter_c_keycap` | 字母 C 键帽 | 带底托或边框的字母 C 按键图标   | `icon_letter_a_circle`、`icon_inbox`、`icon_mail`  | 已有截图 | 来自人工审核截图，当前素材包里无精确对应类；不建议硬并到 `icon_letter_a_circle` |
| `icon_skier`        | 滑雪人物   | 斜坡上带双滑雪板的人物运动图标   | `icon_hiking`、`icon_climbing`、`icon_seated_person` | 已有截图 | 来自人工审核截图，当前素材包里无精确对应类；不建议硬并到 `icon_hiking` |
| `icon_map_navigation` | 地图导航 | 带有定位针和路径虚线的地图图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409001414_1.jpg |
| `icon_beach` | 沙滩 | 包含遮阳伞和海浪的沙滩场景图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409001414_1.jpg |
| `icon_beach_vacation` | 海滩度假 | 包含遮阳伞、躺椅和鱼的组合图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_10.jpg |
| `icon_clock` | 时钟 | 圆形的钟表或计时器图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_10.jpg |
| `icon_tshirt` | T恤 | T恤或衬衫的轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_10.jpg |
| `icon_paintbrush` | 画笔 | 一只画笔的轮廓 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_11.jpg |
| `icon_paper_plane` | 纸飞机 | 纸飞机的三角形轮廓 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_11.jpg |
| `icon_trend_up` | 趋势上升 | 圆形背景下的上升折线图 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_11.jpg |
| `icon_steaming_bowl` | 热气腾腾的碗 | 一个冒着热气的碗的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_12.jpg |
| `icon_map_pin` | 地图标记 | 带有定位图钉的地图图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_12.jpg |
| `icon_building` | 建筑物 | 带有窗户的高层建筑图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_13.jpg |
| `icon_bag` | 包包 | 带扣的包袋或手提包图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_13.jpg |
| `icon_hot_air_balloon` | 热气球 | 热气球轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_14.jpg |
| `icon_crown` | 皇冠 | 皇冠形状的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_15.jpg |
| `icon_gas_pump` | 加油泵 | 加油站泵油枪图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_16.jpg |
| `icon_telephone` | 电话 | 电话听筒与圆弧及省略号图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_16.jpg |
| `icon_elephant` | 大象 | 大象轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_17.jpg |
| `icon_helicopter` | 直升机 | 直升机轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_17.jpg |
| `icon_rocket` | 火箭 | 火箭或航天器的轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_18.jpg |
| `icon_diamond` | 钻石 | 钻石形状的轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_19.jpg |
| `icon_palm_tree` | 棕榈树 | 两棵棕榈树的图形 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_2.jpg |
| `icon_pagoda` | 宝塔 | 传统的东方宝塔建筑图形 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_2.jpg |
| `icon_armchair` | 扶手椅 | 一把扶手椅的轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_20.jpg |
| `icon_dollar_circle` | 圆圈美元符号 | 圆圈中间包含一个美元符号 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_20.jpg |
| `icon_letter_c_square` | 方框字母C | 一个深色正方形，中心有一个字母C | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_3.jpg |
| `icon_snowboarding` | 单板滑雪 | 一个正在进行单板滑雪的人物图形 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_3.jpg |
| `icon_location_marker` | 定位标记 | 水滴形状的地图定位针图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_4.jpg |
| `icon_detective` | 侦探 | 戴着宽檐帽的人物头像轮廓 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_4.jpg |
| `icon_panda` | 熊猫 | 熊猫头部的轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_5.jpg |
| `icon_handshake` | 握手 | 两只手紧握在一起的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_5.jpg |
| `icon_user_menu` | 用户菜单 | 包含三条横线和一个人头像的矩形图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_7.jpg |
| `icon_thumbs_up` | 点赞 | 大拇指向上伸出的手势图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_8.jpg |
| `icon_cutlery` | 餐具 | 叉子和勺子的组合图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_8.jpg |
| `icon_monitor_d` | 字母D显示器 | 带有一个字母D的方形屏幕或显示器图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_8.jpg |
| `icon_beach_umbrella` | 遮阳伞与躺椅 | 包含遮阳伞和沙滩椅的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_9.jpg |
| `icon_beach_items` | 沙滩用品 | 包含沙滩球和防晒霜瓶子的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409002228_9.jpg |
| `icon_share` | 分享 | 三个圆形节点通过线条连接的分享图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_1.jpg |
| `icon_lightning_tree` | 闪电树 | 闪电与松树结合的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_12.jpg |
| `icon_helmet` | 头盔 | 带有护目镜的飞行员头盔图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_13.jpg |
| `icon_parachute` | 降落伞 | 带有悬挂人物的降落伞图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_13.jpg |
| `icon_running_person` | 跑步人物 | 正在奔跑的人物剪影 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_14.jpg |
| `icon_arrow` | 箭头 | 箭头形状的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_16.jpg |
| `icon_castle` | 城堡 | 带有尖顶和城墙的城堡或塔楼图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_17.jpg |
| `icon_diamond_drop` | 钻石与水滴 | 一个倾斜的菱形几何图形，旁边带有一个小水滴 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_17.jpg |
| `icon_mountain_waves` | 山脉与波浪 | 山峰轮廓图标，底部带有波浪线条 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_17.jpg |
| `icon_price_tag` | 价格标签 | 带有百分号的价格标签图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_18.jpg |
| `icon_image` | 图片 | 包含山脉和圆圈（太阳）的图片占位图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_18.jpg |
| `icon_torii_gate` | 鸟居 | 具有传统日式风格的鸟居或牌坊结构图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_19.jpg |
| `icon_bus` | 巴士 | 巴士或大型客车的前脸轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_19.jpg |
| `icon_film` | 胶片 | 由两个带有圆形孔洞图案的矩形叠加而成的胶片图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_2.jpg |
| `icon_diver` | 潜水员 | 戴着潜水面罩或飞行头盔的人物剪影 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_20.jpg |
| `icon_refresh` | 刷新 | 由两个循环方向的箭头组成的同步或刷新图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_20.jpg |
| `icon_gear_percent` | 百分比齿轮 | 一个齿轮图标，中心包含一个百分号 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_22.jpg |
| `icon_sun` | 太阳 | 一个圆形核心并带有放射状线条的太阳图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_22.jpg |
| `icon_percentage_gear` | 百分比齿轮 | 一个齿轮形状，中间带有百分比符号 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_23.jpg |
| `icon_yen_arrow` | 日元箭头 | 带有向右箭头的日元符号图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_24.jpg |
| `icon_eye_off` | 眼睛禁用 | 一个带有斜杠穿过的眼睛图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_28.jpg |
| `icon_leafy_smile` | 叶片笑脸 | 头部带有三片叶子装饰的笑脸图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_28.jpg |
| `icon_beach_leisure` | 海滩休闲 | 包含遮阳伞、躺椅和鱼的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_30.jpg |
| `icon_bed` | 床 | 床的轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_4.jpg |
| `icon_food_bowl` | 热碗 | 一个冒着热气的碗 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_6.jpg |
| `icon_open_box` | 开口盒子 | 一个开口的盒子图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_8.jpg |
| `icon_book` | 书本 | 一本打开的书或笔记本的轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_9.jpg |
| `icon_target` | 靶心 | 一个带有十字准星的圆形靶心图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409003258_9.jpg |
| `icon_panda_head` | 熊猫头 | 熊猫脸部的轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_1.jpg |
| `icon_bar_chart` | 柱状图 | 三个高度不一的垂直条形图图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_10.jpg |
| `icon_hot_spring` | 温泉 | 冒着蒸汽的温泉图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_11.jpg |
| `icon_moon` | 月亮 | 圆圈内的月牙图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_11.jpg |
| `icon_expand` | 展开 | 一个正方形框内包含四个向外指的箭头，表示放大或全屏。 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_13.jpg |
| `icon_wallet` | 钱包 | 一个带有闭合扣的简约钱包或小包图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_14.jpg |
| `icon_landscape` | 风景 | 包含山峰和圆形（太阳或月亮）的风景图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_14.jpg |
| `icon_scooter` | 踏板车 | 踏板车或小摩托车的轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_16.jpg |
| `icon_gear` | 齿轮 | 一个带有辐条的轮子或齿轮轮廓 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_16.jpg |
| `icon_gas_station` | 加油站 | 加油站加油机图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_18.jpg |
| `icon_tent` | 帐篷 | 帐篷轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_19.jpg |
| `icon_landscape_picture` | 风景画 | 带框的风景画，包含山脉和太阳/月亮 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_2.jpg |
| `icon_horse_rider` | 骑马人 | 一个人骑在马上的剪影图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_2.jpg |
| `icon_growth_graph` | 增长图表 | 圆形背景下的上升折线图 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_3.jpg |
| `icon_ship_wheel` | 舵轮 | 船只使用的舵轮或方向盘图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_4.jpg |
| `icon_swirl` | 旋转旋涡 | 由螺旋线和波浪线组成的旋转图形图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_5.jpg |
| `icon_map_location` | 地图定位 | 带有定位大头针的折叠地图图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409103848_7.jpg |
| `icon_beach_scene` | 海滩场景 | 包含遮阳伞、躺椅和一条鱼的组合图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_1.jpg |
| `icon_info` | 信息 | 圆圈内的字母i图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_13.jpg |
| `icon_package` | 包裹 | 纸箱或包裹图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_13.jpg |
| `icon_phone_call` | 电话通话 | 圆圈环绕着电话听筒和三个省略点的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_17.jpg |
| `icon_bowl` | 碗 | 一个冒着热气的碗 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_18.jpg |
| `icon_list` | 列表 | 包含水平线条的矩形列表图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_19.jpg |
| `icon_cd_disk` | 光盘 | 带有光盘和笔的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_2.jpg |
| `icon_calendar_clock` | 日历时钟 | 一个日历图标，其右下角叠加了一个时钟图标。 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_20.jpg |
| `icon_sync` | 同步 | 两个相互循环连接的箭头图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_3.jpg |
| `icon_rocking_horse` | 摇摇马 | 摇摇马轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_4.jpg |
| `icon_heartbeat` | 心跳 | 带有心电图脉搏波纹的心形图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_5.jpg |
| `icon_hexagon_nut` | 六角螺母 | 一个中心带有圆孔的六边形图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_5.jpg |
| `icon_bow_arrow` | 弓箭 | 弓与箭头的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_7.jpg |
| `icon_growth_trend` | 增长趋势 | 一个向右上方升起的折线箭头 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_8.jpg |
| `icon_network_nodes` | 网络节点 | 由线条连接的多个圆形节点结构 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409104448_8.jpg |
| `icon_bowling` | 保龄球 | 保龄球与球瓶的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_1.jpg |
| `icon_eiffel_tower` | 埃菲尔铁塔 | 埃菲尔铁塔的轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_1.jpg |
| `icon_chart` | 图表 | 包含折线和柱状图的统计图表 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_12.jpg |
| `icon_eye` | 眼睛 | 椭圆形的眼睛图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_12.jpg |
| `icon_mountain_location` | 山脉位置 | 山峰与地图定位针的组合图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_12.jpg |
| `icon_location_pin` | 定位针 | 地图上的位置定位针图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_13.jpg |
| `icon_wizard` | 巫师 | 手持法杖或火炬的巫师角色图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_13.jpg |
| `icon_warning` | 警告 | 三角形内包含感叹号的警告标志 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_16.jpg |
| `icon_torii` | 鸟居 | 日本传统的鸟居门结构 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_2.jpg |
| `icon_users_star` | 带星星的人物 | 两个人物与一颗星星组成的组合图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_2.jpg |
| `icon_trash` | 垃圾桶 | 一个垃圾桶形状的轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_20.jpg |
| `icon_sail` | 帆 | 帆船的帆状图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_22.jpg |
| `icon_info_circle` | 信息圆圈 | 圆圈内包含字母i的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_24.jpg |
| `icon_magic_hand` | 魔法手 | 一只手及其上方飘出的烟雾或魔法效果 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_26.jpg |
| `icon_cross_pattern` | 十字图案 | 由四个圆角矩形组成的十字形几何图案 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_26.jpg |
| `icon_menu` | 菜单 | 由三条水平线组成的矩形图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_29.jpg |
| `icon_trash_bin` | 垃圾桶 | 一个带有盖子和两条垂直条纹的垃圾桶图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_30.jpg |
| `icon_barbell` | 杠铃 | 杠铃形状图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_5.jpg |
| `icon_smartphone` | 智能手机 | 智能手机形状图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_5.jpg |
| `icon_growth_chart` | 增长图表 | 带有上升箭头的折线图图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_7.jpg |
| `icon_beach_lounger` | 沙滩躺椅 | 带有遮阳伞的沙滩躺椅图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_7.jpg |
| `icon_windsurfing` | 风帆冲浪 | 一个人在风帆冲浪板上冲浪的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409105429_8.jpg |
| `icon_whale` | 鲸鱼 | 鲸鱼的轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_1.jpg |
| `icon_teapot` | 茶壶 | 茶壶轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_10.jpg |
| `icon_horse_riding` | 骑马 | 一个人骑在马上的剪影图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_11.jpg |
| `icon_settings` | 设置 | 圆形的齿轮或设置图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_11.jpg |
| `icon_bolt_tree` | 闪电树 | 由闪电和树木组成的组合图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_12.jpg |
| `icon_stopwatch` | 秒表 | 一个带有按钮和指针的圆形秒表图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_14.jpg |
| `icon_letter_tray` | 字母托盘 | 带有字母A的方块放置在托盘中 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_15.jpg |
| `icon_letter_d_square` | 带字母D的正方形 | 一个带有字母D的正方形图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_17.jpg |
| `icon_trophy` | 奖杯 | 奖杯轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_21.jpg |
| `icon_key_b` | 键盘按键B | 带有字母B的方形键盘按键图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_22.jpg |
| `icon_tropical_island` | 热带岛屿 | 包含棕榈树和沙滩的小岛图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_24.jpg |
| `icon_cards` | 卡片 | 两张重叠的矩形卡片图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_6.jpg |
| `icon_yen_exchange` | 日元汇率/转换 | 包含日元符号及左右方向箭头的图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_7.jpg |
| `icon_map_route` | 地图路径 | 带有地图定位针和虚线路径的地图图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_7.jpg |
| `icon_user` | 用户 | 人的头部与肩膀轮廓 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_8.jpg |
| `icon_landmark` | 地标 | 埃菲尔铁塔的轮廓图标 | 待人工确认 | 已有截图 | 自动审计发现；示例图片：materials/test/group1/query/20260409110342_8.jpg |

## 3.1 已确认可直接归到现有素材类的案例

这一节只记录“乍看像新图标，但最终确认可归到现有素材类”的案例，避免重复开新类。

| 截图批次 | 图标描述 | 归属现有类 | 备注 |
| --- | --- | --- | --- |
| 已判定样例 A | 坐姿人物剪影 | `icon_seated_person` | 可直接按现有素材类标注 |
| 已判定样例 A | 枫叶形叶片 | `icon_leaf` | 作为叶子类变体处理，不单独扩类 |
| 已判定样例 A | 遥控器与屏幕组合 | `icon_remote_screen` | 可直接按现有素材类标注 |
| 已判定样例 B | 礼物盒圆形徽章 | `icon_gift` | 可直接按现有素材类标注 |
| 已判定样例 C | 耳麦轮廓图标 | `icon_headset` | 可直接按现有素材类标注 |

## 3.2 自动审计图片与分类映射（脚本生成）

历史说明：旧版 `uv run sinan materials audit-group1-query ...` 曾自动更新这一区。当前命令已改为直接生成 `tpl_* / var_*` 的 `group1` 素材包，这一节不再自动回写。
当前行为说明：即使本轮审计存在失败图片，命令也会先把成功图片对应的模板素材落到 `output_root`；后续可使用 `--retry-from-report <旧的 group1-query-audit.jsonl>` 复用成功项并只重试失败图片，无需全量重做。

<!-- AUTO-GENERATED:GROUP1-QUERY-AUDIT:START -->
已扫描 `150` 张 query 图片。

| 图片文件 | 左到右类别序列 | 新类别候选 | 状态 / 备注 |
| --- | --- | --- | --- |
| `materials/test/group1/query/20260409001414_1.jpg` | 1:`icon_map_navigation`；2:`icon_broken_image`；3:`icon_beach` | `icon_map_navigation`，`icon_broken_image`，`icon_beach` | ok |
| `materials/test/group1/query/20260409002228_1.jpg` | 1:`icon_climbing`；2:`icon_leaf`；3:`icon_remote_screen` | 无 | ok |
| `materials/test/group1/query/20260409002228_10.jpg` | 1:`icon_beach_vacation`；2:`icon_clock`；3:`icon_tshirt` | `icon_beach_vacation`，`icon_clock`，`icon_tshirt` | ok |
| `materials/test/group1/query/20260409002228_11.jpg` | 1:`icon_paintbrush`；2:`icon_paper_plane`；3:`icon_trend_up` | `icon_paintbrush`，`icon_paper_plane`，`icon_trend_up` | ok |
| `materials/test/group1/query/20260409002228_12.jpg` | 1:`icon_steaming_bowl`；2:`icon_map_pin`；3:`icon_inbox` | `icon_steaming_bowl`，`icon_map_pin` | ok |
| `materials/test/group1/query/20260409002228_13.jpg` | 1:`icon_flower`；2:`icon_building`；3:`icon_bag` | `icon_building`，`icon_bag` | ok |
| `materials/test/group1/query/20260409002228_14.jpg` | 1:`icon_car`；2:`icon_star`；3:`icon_hot_air_balloon` | `icon_hot_air_balloon` | ok |
| `materials/test/group1/query/20260409002228_15.jpg` | 1:`icon_crown`；2:`icon_headset`；3:`icon_remote_screen` | `icon_crown` | ok |
| `materials/test/group1/query/20260409002228_16.jpg` | 1:`icon_gas_pump`；2:`icon_plane`；3:`icon_telephone` | `icon_gas_pump`，`icon_telephone` | ok |
| `materials/test/group1/query/20260409002228_17.jpg` | 1:`icon_elephant`；2:`icon_heart`；3:`icon_helicopter` | `icon_elephant`，`icon_helicopter` | ok |
| `materials/test/group1/query/20260409002228_18.jpg` | 1:`icon_rocket`；2:`icon_speedboat`；3:`icon_bell` | `icon_rocket` | ok |
| `materials/test/group1/query/20260409002228_19.jpg` | 1:`icon_heart`；2:`icon_hiking`；3:`icon_diamond` | `icon_diamond` | ok |
| `materials/test/group1/query/20260409002228_2.jpg` | 1:`icon_palm_tree`；2:`icon_pagoda`；3:`icon_gift` | `icon_palm_tree`，`icon_pagoda` | ok |
| `materials/test/group1/query/20260409002228_20.jpg` | 1:`icon_armchair`；2:`icon_dollar_circle`；3:`icon_shopping_cart` | `icon_armchair`，`icon_dollar_circle` | ok |
| `materials/test/group1/query/20260409002228_3.jpg` | 1:`icon_letter_c_square`；2:`icon_headset`；3:`icon_snowboarding` | `icon_letter_c_square`，`icon_snowboarding` | ok |
| `materials/test/group1/query/20260409002228_4.jpg` | 1:`icon_train`；2:`icon_location_marker`；3:`icon_detective` | `icon_location_marker`，`icon_detective` | ok |
| `materials/test/group1/query/20260409002228_5.jpg` | 1:`icon_panda`；2:`icon_compass`；3:`icon_handshake` | `icon_panda`，`icon_handshake` | ok |
| `materials/test/group1/query/20260409002228_6.jpg` | 1:`icon_flame`；2:`icon_plane`；3:`icon_climbing` | 无 | ok |
| `materials/test/group1/query/20260409002228_7.jpg` | 1:`icon_user_menu`；2:`icon_paw`；3:`icon_star` | `icon_user_menu` | ok |
| `materials/test/group1/query/20260409002228_8.jpg` | 1:`icon_thumbs_up`；2:`icon_cutlery`；3:`icon_monitor_d` | `icon_thumbs_up`，`icon_cutlery`，`icon_monitor_d` | ok |
| `materials/test/group1/query/20260409002228_9.jpg` | 1:`icon_paw`；2:`icon_beach_umbrella`；3:`icon_beach_items` | `icon_beach_umbrella`，`icon_beach_items` | ok |
| `materials/test/group1/query/20260409003258_1.jpg` | 1:`icon_share`；2:`icon_microphone`；3:`icon_speedboat` | `icon_share` | ok |
| `materials/test/group1/query/20260409003258_10.jpg` | 1:`icon_users`；2:`icon_heart`；3:`icon_trend_up` | `icon_trend_up` | ok |
| `materials/test/group1/query/20260409003258_11.jpg` | 1:`icon_gift`；2:`icon_lantern`；3:`icon_clock` | `icon_clock` | ok |
| `materials/test/group1/query/20260409003258_12.jpg` | 1:`icon_headset`；2:`icon_palm_tree`；3:`icon_lightning_tree` | `icon_palm_tree`，`icon_lightning_tree` | ok |
| `materials/test/group1/query/20260409003258_13.jpg` | 1:`icon_helmet`；2:`icon_panda`；3:`icon_parachute` | `icon_helmet`，`icon_panda`，`icon_parachute` | ok |
| `materials/test/group1/query/20260409003258_14.jpg` | 1:`icon_yen_shield`；2:`icon_star`；3:`icon_running_person` | `icon_running_person` | ok |
| `materials/test/group1/query/20260409003258_15.jpg` | 无 | 无 | timed out |
| `materials/test/group1/query/20260409003258_16.jpg` | 1:`icon_thumbs_up`；2:`icon_inbox`；3:`icon_arrow` | `icon_thumbs_up`，`icon_arrow` | ok |
| `materials/test/group1/query/20260409003258_17.jpg` | 1:`icon_castle`；2:`icon_diamond_drop`；3:`icon_mountain_waves` | `icon_castle`，`icon_diamond_drop`，`icon_mountain_waves` | ok |
| `materials/test/group1/query/20260409003258_18.jpg` | 1:`icon_price_tag`；2:`icon_umbrella`；3:`icon_image` | `icon_price_tag`，`icon_image` | ok |
| `materials/test/group1/query/20260409003258_19.jpg` | 1:`icon_torii_gate`；2:`icon_snowboarding`；3:`icon_bus` | `icon_torii_gate`，`icon_snowboarding`，`icon_bus` | ok |
| `materials/test/group1/query/20260409003258_2.jpg` | 1:`icon_film`；2:`icon_bus`；3:`icon_climbing` | `icon_film`，`icon_bus` | ok |
| `materials/test/group1/query/20260409003258_20.jpg` | 1:`icon_diver`；2:`icon_refresh`；3:`icon_elephant` | `icon_diver`，`icon_refresh`，`icon_elephant` | ok |
| `materials/test/group1/query/20260409003258_21.jpg` | 1:`icon_shield_plus`；2:`icon_camera`；3:`icon_gift` | 无 | ok |
| `materials/test/group1/query/20260409003258_22.jpg` | 1:`icon_share`；2:`icon_gear_percent`；3:`icon_sun` | `icon_share`，`icon_gear_percent`，`icon_sun` | ok |
| `materials/test/group1/query/20260409003258_23.jpg` | 1:`icon_star`；2:`icon_percentage_gear`；3:`icon_flame` | `icon_percentage_gear` | ok |
| `materials/test/group1/query/20260409003258_24.jpg` | 1:`icon_yen_arrow`；2:`icon_umbrella`；3:`icon_yen_shield` | `icon_yen_arrow` | ok |
| `materials/test/group1/query/20260409003258_25.jpg` | 1:`icon_bolt`；2:`icon_broken_image`；3:`icon_gift` | `icon_broken_image` | ok |
| `materials/test/group1/query/20260409003258_26.jpg` | 1:`icon_paintbrush`；2:`icon_ship`；3:`icon_climbing` | `icon_paintbrush` | ok |
| `materials/test/group1/query/20260409003258_27.jpg` | 1:`icon_shopping_cart`；2:`icon_luggage`；3:`icon_heart` | 无 | ok |
| `materials/test/group1/query/20260409003258_28.jpg` | 1:`icon_train`；2:`icon_eye_off`；3:`icon_leafy_smile` | `icon_eye_off`，`icon_leafy_smile` | ok |
| `materials/test/group1/query/20260409003258_29.jpg` | 1:`icon_inbox`；2:`icon_letter_a_circle`；3:`icon_smile` | 无 | ok |
| `materials/test/group1/query/20260409003258_3.jpg` | 1:`icon_flag`；2:`icon_train`；3:`icon_ship` | 无 | ok |
| `materials/test/group1/query/20260409003258_30.jpg` | 1:`icon_lightning_tree`；2:`icon_bolt`；3:`icon_beach_leisure` | `icon_lightning_tree`，`icon_beach_leisure` | ok |
| `materials/test/group1/query/20260409003258_4.jpg` | 1:`icon_key`；2:`icon_heart`；3:`icon_bed` | `icon_bed` | ok |
| `materials/test/group1/query/20260409003258_5.jpg` | 1:`icon_remote_screen`；2:`icon_shield_plus`；3:`icon_check_circle` | 无 | ok |
| `materials/test/group1/query/20260409003258_6.jpg` | 1:`icon_food_bowl`；2:`icon_cutlery`；3:`icon_train` | `icon_food_bowl`，`icon_cutlery` | ok |
| `materials/test/group1/query/20260409003258_7.jpg` | 1:`icon_castle`；2:`icon_beach_umbrella`；3:`icon_flag` | `icon_castle`，`icon_beach_umbrella` | ok |
| `materials/test/group1/query/20260409003258_8.jpg` | 1:`icon_open_box`；2:`icon_gift`；3:`icon_users` | `icon_open_box` | ok |
| `materials/test/group1/query/20260409003258_9.jpg` | 1:`icon_book`；2:`icon_remote_screen`；3:`icon_target` | `icon_book`，`icon_target` | ok |
| `materials/test/group1/query/20260409103848_1.jpg` | 1:`icon_remote_screen`；2:`icon_leaf`；3:`icon_panda_head` | `icon_panda_head` | ok |
| `materials/test/group1/query/20260409103848_10.jpg` | 1:`icon_building`；2:`icon_key`；3:`icon_bar_chart` | `icon_building`，`icon_bar_chart` | ok |
| `materials/test/group1/query/20260409103848_11.jpg` | 1:`icon_hot_spring`；2:`icon_moon`；3:`icon_train` | `icon_hot_spring`，`icon_moon` | ok |
| `materials/test/group1/query/20260409103848_12.jpg` | 1:`icon_bar_chart`；2:`icon_plane`；3:`icon_smile` | `icon_bar_chart` | ok |
| `materials/test/group1/query/20260409103848_13.jpg` | 1:`icon_expand`；2:`icon_inbox`；3:`icon_check_circle` | `icon_expand` | ok |
| `materials/test/group1/query/20260409103848_14.jpg` | 1:`icon_heart`；2:`icon_wallet`；3:`icon_landscape` | `icon_wallet`，`icon_landscape` | ok |
| `materials/test/group1/query/20260409103848_15.jpg` | 1:`icon_briefcase`；2:`icon_globe`；3:`icon_compass` | 无 | ok |
| `materials/test/group1/query/20260409103848_16.jpg` | 1:`icon_letter_a_circle`；2:`icon_scooter`；3:`icon_gear` | `icon_scooter`，`icon_gear` | ok |
| `materials/test/group1/query/20260409103848_17.jpg` | 1:`icon_smile`；2:`icon_umbrella`；3:`icon_yen_shield` | 无 | ok |
| `materials/test/group1/query/20260409103848_18.jpg` | 1:`icon_gas_station`；2:`icon_smile`；3:`icon_flame` | `icon_gas_station` | ok |
| `materials/test/group1/query/20260409103848_19.jpg` | 1:`icon_tent`；2:`icon_hiking`；3:`icon_hot_air_balloon` | `icon_tent`，`icon_hot_air_balloon` | ok |
| `materials/test/group1/query/20260409103848_2.jpg` | 1:`icon_bolt`；2:`icon_landscape_picture`；3:`icon_horse_rider` | `icon_landscape_picture`，`icon_horse_rider` | ok |
| `materials/test/group1/query/20260409103848_3.jpg` | 1:`icon_users`；2:`icon_growth_graph`；3:`icon_smile` | `icon_growth_graph` | ok |
| `materials/test/group1/query/20260409103848_4.jpg` | 1:`icon_beach`；2:`icon_ship_wheel`；3:`icon_ship` | `icon_beach`，`icon_ship_wheel` | ok |
| `materials/test/group1/query/20260409103848_5.jpg` | 1:`icon_swirl`；2:`icon_briefcase`；3:`icon_inbox` | `icon_swirl` | ok |
| `materials/test/group1/query/20260409103848_6.jpg` | 1:`icon_check_circle`；2:`icon_house`；3:`icon_flag` | 无 | ok |
| `materials/test/group1/query/20260409103848_7.jpg` | 1:`icon_bell`；2:`icon_inbox`；3:`icon_map_location` | `icon_map_location` | ok |
| `materials/test/group1/query/20260409103848_8.jpg` | 1:`icon_paw`；2:`icon_hot_air_balloon`；3:`icon_rocket` | `icon_hot_air_balloon`，`icon_rocket` | ok |
| `materials/test/group1/query/20260409103848_9.jpg` | 1:`icon_helicopter`；2:`icon_pagoda`；3:`icon_paw` | `icon_helicopter`，`icon_pagoda` | ok |
| `materials/test/group1/query/20260409104448_1.jpg` | 1:`icon_christmas_tree`；2:`icon_beach_scene`；3:`icon_compass` | `icon_beach_scene` | ok |
| `materials/test/group1/query/20260409104448_10.jpg` | 1:`icon_gift`；2:`icon_lantern`；3:`icon_remote_screen` | 无 | ok |
| `materials/test/group1/query/20260409104448_11.jpg` | 1:`icon_armchair`；2:`icon_handshake`；3:`icon_shopping_cart` | `icon_armchair`，`icon_handshake` | ok |
| `materials/test/group1/query/20260409104448_12.jpg` | 1:`icon_shield_plus`；2:`icon_climbing`；3:`icon_bus` | `icon_bus` | ok |
| `materials/test/group1/query/20260409104448_13.jpg` | 1:`icon_compass`；2:`icon_info`；3:`icon_package` | `icon_info`，`icon_package` | ok |
| `materials/test/group1/query/20260409104448_14.jpg` | 1:`icon_check_circle`；2:`icon_microphone`；3:`icon_speedboat` | 无 | ok |
| `materials/test/group1/query/20260409104448_15.jpg` | 1:`icon_plane`；2:`icon_plane`；3:`icon_climbing` | 无 | ok |
| `materials/test/group1/query/20260409104448_16.jpg` | 1:`icon_car`；2:`icon_paper_plane`；3:`icon_camera` | `icon_paper_plane` | ok |
| `materials/test/group1/query/20260409104448_17.jpg` | 1:`icon_sun`；2:`icon_phone_call`；3:`icon_leaf` | `icon_sun`，`icon_phone_call` | ok |
| `materials/test/group1/query/20260409104448_18.jpg` | 1:`icon_bowl`；2:`icon_key`；3:`icon_sun` | `icon_bowl`，`icon_sun` | ok |
| `materials/test/group1/query/20260409104448_19.jpg` | 1:`icon_umbrella`；2:`icon_climbing`；3:`icon_list` | `icon_list` | ok |
| `materials/test/group1/query/20260409104448_2.jpg` | 1:`icon_cd_disk`；2:`icon_car`；3:`icon_speedboat` | `icon_cd_disk` | ok |
| `materials/test/group1/query/20260409104448_20.jpg` | 1:`icon_calendar_clock`；2:`icon_speedboat`；3:`icon_flag` | `icon_calendar_clock` | ok |
| `materials/test/group1/query/20260409104448_3.jpg` | 1:`icon_broken_image`；2:`icon_sync`；3:`icon_inbox` | `icon_broken_image`，`icon_sync` | ok |
| `materials/test/group1/query/20260409104448_4.jpg` | 1:`icon_bell`；2:`icon_leaf`；3:`icon_rocking_horse` | `icon_rocking_horse` | ok |
| `materials/test/group1/query/20260409104448_5.jpg` | 1:`icon_heartbeat`；2:`icon_hexagon_nut`；3:`icon_info` | `icon_heartbeat`，`icon_hexagon_nut`，`icon_info` | ok |
| `materials/test/group1/query/20260409104448_6.jpg` | 1:`icon_remote_screen`；2:`icon_hot_air_balloon`；3:`icon_train` | `icon_hot_air_balloon` | ok |
| `materials/test/group1/query/20260409104448_7.jpg` | 1:`icon_map_pin`；2:`icon_knot`；3:`icon_bow_arrow` | `icon_map_pin`，`icon_bow_arrow` | ok |
| `materials/test/group1/query/20260409104448_8.jpg` | 1:`icon_growth_trend`；2:`icon_compass`；3:`icon_network_nodes` | `icon_growth_trend`，`icon_network_nodes` | ok |
| `materials/test/group1/query/20260409104448_9.jpg` | 1:`icon_umbrella`；2:`icon_cutlery`；3:`icon_plane` | `icon_cutlery` | ok |
| `materials/test/group1/query/20260409105429_1.jpg` | 1:`icon_speedboat`；2:`icon_bowling`；3:`icon_eiffel_tower` | `icon_bowling`，`icon_eiffel_tower` | ok |
| `materials/test/group1/query/20260409105429_10.jpg` | 1:`icon_rocking_horse`；2:`icon_rocket`；3:`icon_steaming_bowl` | `icon_rocking_horse`，`icon_rocket`，`icon_steaming_bowl` | ok |
| `materials/test/group1/query/20260409105429_11.jpg` | 1:`icon_panda`；2:`icon_globe`；3:`icon_headset` | `icon_panda` | ok |
| `materials/test/group1/query/20260409105429_12.jpg` | 1:`icon_chart`；2:`icon_eye`；3:`icon_mountain_location` | `icon_chart`，`icon_eye`，`icon_mountain_location` | ok |
| `materials/test/group1/query/20260409105429_13.jpg` | 1:`icon_location_pin`；2:`icon_running_person`；3:`icon_wizard` | `icon_location_pin`，`icon_running_person`，`icon_wizard` | ok |
| `materials/test/group1/query/20260409105429_14.jpg` | 1:`icon_briefcase`；2:`icon_star`；3:`icon_scooter` | `icon_scooter` | ok |
| `materials/test/group1/query/20260409105429_15.jpg` | 1:`icon_bus`；2:`icon_castle`；3:`icon_users` | `icon_bus`，`icon_castle` | ok |
| `materials/test/group1/query/20260409105429_16.jpg` | 1:`icon_diamond`；2:`icon_flame`；3:`icon_warning` | `icon_diamond`，`icon_warning` | ok |
| `materials/test/group1/query/20260409105429_17.jpg` | 1:`icon_elephant`；2:`icon_speedboat`；3:`icon_flower` | `icon_elephant` | ok |
| `materials/test/group1/query/20260409105429_18.jpg` | 1:`icon_image`；2:`icon_bolt`；3:`icon_share` | `icon_image`，`icon_share` | ok |
| `materials/test/group1/query/20260409105429_19.jpg` | 1:`icon_letter_a_circle`；2:`icon_hiking`；3:`icon_bell` | 无 | ok |
| `materials/test/group1/query/20260409105429_2.jpg` | 1:`icon_leaf`；2:`icon_torii`；3:`icon_users_star` | `icon_torii`，`icon_users_star` | ok |
| `materials/test/group1/query/20260409105429_20.jpg` | 1:`icon_eye`；2:`icon_train`；3:`icon_trash` | `icon_eye`，`icon_trash` | ok |
| `materials/test/group1/query/20260409105429_21.jpg` | 1:`icon_compass`；2:`icon_heart`；3:`icon_shopping_cart` | 无 | ok |
| `materials/test/group1/query/20260409105429_22.jpg` | 1:`icon_sail`；2:`icon_gear`；3:`icon_check_circle` | `icon_sail`，`icon_gear` | ok |
| `materials/test/group1/query/20260409105429_23.jpg` | 1:`icon_horse_rider`；2:`icon_cloud_download`；3:`icon_eye` | `icon_horse_rider`，`icon_eye` | ok |
| `materials/test/group1/query/20260409105429_24.jpg` | 1:`icon_yen_shield`；2:`icon_bolt`；3:`icon_info_circle` | `icon_info_circle` | ok |
| `materials/test/group1/query/20260409105429_25.jpg` | 1:`icon_smile`；2:`icon_target`；3:`icon_bolt` | `icon_target` | ok |
| `materials/test/group1/query/20260409105429_26.jpg` | 1:`icon_users`；2:`icon_magic_hand`；3:`icon_cross_pattern` | `icon_magic_hand`，`icon_cross_pattern` | ok |
| `materials/test/group1/query/20260409105429_27.jpg` | 1:`icon_key`；2:`icon_location_pin`；3:`icon_mail` | `icon_location_pin` | ok |
| `materials/test/group1/query/20260409105429_28.jpg` | 1:`icon_smile`；2:`icon_book`；3:`icon_compass` | `icon_book` | ok |
| `materials/test/group1/query/20260409105429_29.jpg` | 1:`icon_shield_plus`；2:`icon_speedboat`；3:`icon_menu` | `icon_menu` | ok |
| `materials/test/group1/query/20260409105429_3.jpg` | 1:`icon_microphone`；2:`icon_lightning_tree`；3:`icon_cutlery` | `icon_lightning_tree`，`icon_cutlery` | ok |
| `materials/test/group1/query/20260409105429_30.jpg` | 1:`icon_trash_bin`；2:`icon_headset`；3:`icon_check_circle` | `icon_trash_bin` | ok |
| `materials/test/group1/query/20260409105429_4.jpg` | 1:`icon_share`；2:`icon_climbing`；3:`icon_moon` | `icon_share`，`icon_moon` | ok |
| `materials/test/group1/query/20260409105429_5.jpg` | 1:`icon_barbell`；2:`icon_flame`；3:`icon_smartphone` | `icon_barbell`，`icon_smartphone` | ok |
| `materials/test/group1/query/20260409105429_6.jpg` | 1:`icon_heart`；2:`icon_landscape`；3:`icon_flag` | `icon_landscape` | ok |
| `materials/test/group1/query/20260409105429_7.jpg` | 1:`icon_anchor`；2:`icon_growth_chart`；3:`icon_beach_lounger` | `icon_growth_chart`，`icon_beach_lounger` | ok |
| `materials/test/group1/query/20260409105429_8.jpg` | 1:`icon_cutlery`；2:`icon_windsurfing`；3:`icon_tent` | `icon_cutlery`，`icon_windsurfing`，`icon_tent` | ok |
| `materials/test/group1/query/20260409105429_9.jpg` | 1:`icon_mail`；2:`icon_remote_screen`；3:`icon_briefcase` | 无 | ok |
| `materials/test/group1/query/20260409110342_1.jpg` | 1:`icon_shopping_cart`；2:`icon_users`；3:`icon_whale` | `icon_whale` | ok |
| `materials/test/group1/query/20260409110342_10.jpg` | 1:`icon_teapot`；2:`icon_flag`；3:`icon_flag` | `icon_teapot` | ok |
| `materials/test/group1/query/20260409110342_11.jpg` | 1:`icon_horse_riding`；2:`icon_image`；3:`icon_settings` | `icon_horse_riding`，`icon_image`，`icon_settings` | ok |
| `materials/test/group1/query/20260409110342_12.jpg` | 1:`icon_bolt_tree`；2:`icon_expand`；3:`icon_ship` | `icon_bolt_tree`，`icon_expand` | ok |
| `materials/test/group1/query/20260409110342_13.jpg` | 1:`icon_headset`；2:`icon_car`；3:`icon_diamond` | `icon_diamond` | ok |
| `materials/test/group1/query/20260409110342_14.jpg` | 1:`icon_stopwatch`；2:`icon_smile`；3:`icon_plane` | `icon_stopwatch` | ok |
| `materials/test/group1/query/20260409110342_15.jpg` | 1:`icon_remote_screen`；2:`icon_letter_tray`；3:`icon_price_tag` | `icon_letter_tray`，`icon_price_tag` | ok |
| `materials/test/group1/query/20260409110342_16.jpg` | 1:`icon_bell`；2:`icon_book`；3:`icon_bolt` | `icon_book` | ok |
| `materials/test/group1/query/20260409110342_17.jpg` | 1:`icon_crown`；2:`icon_letter_d_square`；3:`icon_car` | `icon_crown`，`icon_letter_d_square` | ok |
| `materials/test/group1/query/20260409110342_18.jpg` | 1:`icon_palm_tree`；2:`icon_bolt`；3:`icon_shopping_cart` | `icon_palm_tree` | ok |
| `materials/test/group1/query/20260409110342_19.jpg` | 1:`icon_train`；2:`icon_location_marker`；3:`icon_briefcase` | `icon_location_marker` | ok |
| `materials/test/group1/query/20260409110342_2.jpg` | 1:`icon_microphone`；2:`icon_temple`；3:`icon_dollar_circle` | `icon_temple`，`icon_dollar_circle` | ok |
| `materials/test/group1/query/20260409110342_20.jpg` | 1:`icon_flame`；2:`icon_inbox`；3:`icon_compass` | 无 | ok |
| `materials/test/group1/query/20260409110342_21.jpg` | 1:`icon_trophy`；2:`icon_briefcase`；3:`icon_bowling` | `icon_trophy`，`icon_bowling` | ok |
| `materials/test/group1/query/20260409110342_22.jpg` | 1:`icon_thumbs_up`；2:`icon_eye`；3:`icon_key_b` | `icon_thumbs_up`，`icon_eye`，`icon_key_b` | ok |
| `materials/test/group1/query/20260409110342_23.jpg` | 1:`icon_key`；2:`icon_microphone`；3:`icon_chart` | `icon_chart` | ok |
| `materials/test/group1/query/20260409110342_24.jpg` | 1:`icon_leaf`；2:`icon_tropical_island`；3:`icon_mountain_location` | `icon_tropical_island`，`icon_mountain_location` | ok |
| `materials/test/group1/query/20260409110342_25.jpg` | 1:`icon_castle`；2:`icon_microphone`；3:`icon_climbing` | `icon_castle` | ok |
| `materials/test/group1/query/20260409110342_26.jpg` | 1:`icon_island`；2:`icon_horse_riding`；3:`icon_gift` | `icon_island`，`icon_horse_riding` | ok |
| `materials/test/group1/query/20260409110342_27.jpg` | 无 | 无 | timed out |
| `materials/test/group1/query/20260409110342_28.jpg` | 1:`icon_climbing`；2:`icon_ship`；3:`icon_bar_chart` | `icon_bar_chart` | ok |
| `materials/test/group1/query/20260409110342_29.jpg` | 1:`icon_network_nodes`；2:`icon_trophy`；3:`icon_handshake` | `icon_network_nodes`，`icon_trophy`，`icon_handshake` | ok |
| `materials/test/group1/query/20260409110342_3.jpg` | 1:`icon_paw`；2:`icon_palm_tree`；3:`icon_expand` | `icon_palm_tree`，`icon_expand` | ok |
| `materials/test/group1/query/20260409110342_30.jpg` | 1:`icon_hiking`；2:`icon_microphone`；3:`icon_plane` | 无 | ok |
| `materials/test/group1/query/20260409110342_4.jpg` | 1:`icon_target`；2:`icon_cutlery`；3:`icon_plane` | `icon_target`，`icon_cutlery` | ok |
| `materials/test/group1/query/20260409110342_5.jpg` | 1:`icon_smile`；2:`icon_armchair`；3:`icon_gift` | `icon_armchair` | ok |
| `materials/test/group1/query/20260409110342_6.jpg` | 1:`icon_rocking_horse`；2:`icon_bell`；3:`icon_cards` | `icon_rocking_horse`，`icon_cards` | ok |
| `materials/test/group1/query/20260409110342_7.jpg` | 1:`icon_sun`；2:`icon_yen_exchange`；3:`icon_map_route` | `icon_sun`，`icon_yen_exchange`，`icon_map_route` | ok |
| `materials/test/group1/query/20260409110342_8.jpg` | 1:`icon_user`；2:`icon_landmark`；3:`icon_tent` | `icon_user`，`icon_landmark`，`icon_tent` | ok |
| `materials/test/group1/query/20260409110342_9.jpg` | 1:`icon_microphone`；2:`icon_bolt`；3:`icon_cloud_download` | 无 | ok |
<!-- AUTO-GENERATED:GROUP1-QUERY-AUDIT:END -->

## 4. 类别判定边界

新增类别前，先按下面标准判断要不要单独扩类。

应该新增为独立类别：

- 图形语义和现有类别明显不同
- 视觉轮廓稳定，能形成单独素材池
- 如果硬并到旧类，会长期污染标注和训练

不应该急着新增：

- 只是同一类图标的描边 / 实心 / 圆角变体
- 只是同一物体的轻微视角变化
- 只是低清晰度或压缩导致的局部变形

## 5. 补齐素材时要改哪些地方

一旦 backlog 某个新类别确认要纳入素材包，正式动作是：

1. 追加 `materials/.../manifests/group1.classes.yaml`
2. 新建 `materials/.../group1/icons/<class_name>/`
3. 补至少一批可区分的图标 PNG
4. 复核该类与相邻类别的边界
5. 再进入新的数据集生成和训练轮次

## 6. 协作规则

你现在人工审核时，建议这样用这份文档：

1. 能精确归到现有素材类的，直接按现有类标
2. 不能精确归类的，先截图或记 `sample_id`
3. 把候选新类加到“待补齐的新类别”
4. 我再根据你补的条目去整理名称、描述和边界
5. 等条目冻结后，再统一补素材，不在审核中途反复改类名
