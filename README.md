# 招标信息监控自动化（物码 / 即时零售 / 到店）

每周二上午 9:30（北京时间）自动收集三类主题的招标信息，用 **DeepSeek 大模型**解析为结构化字段，
按类别分别写入**4 张腾讯在线表格**（总表 + 物码 + 即时零售 + 到店），生成**4 个关联看板**，
并**按数据权限分层推送企微群**（Ken 全部 / Mon 物码 / Benny 即时零售 / David 到店）。
全流程托管在 **GitHub Actions**，每周二自动执行。

```
搜索(博查/Serper) ──► DeepSeek 解析&过滤 ──► 去重 ──► 按类别写入 4 张在线表格
                                                    │
                                    ┌───────────────┴────────────────┐
                               生成 4 个看板(GitHub Pages)    企微群机器人 4 条分层消息
```

## 一、监控主题与关键词

| 类别 | 跟进团队 | 推送对象 | 关键词（节选） |
|------|---------|---------|---------------|
| 物码 | SCD | Mon | 一物一码、二维码营销、开盖扫码、瓶盖码/箱码/垛码、赋码、追溯码、防伪码、BC联动、渠道数字化、导购激励、开箱有礼… |
| 即时零售 | ODM | Benny | 即时零售、O2O、到家、闪电仓、美团闪购、淘宝闪购、京东秒送、代运营、竞品监测、价格监测… |
| 到店 | SDM | David | 到店营销、券服务、门店数字化、微信支付、支付宝、碰一碰、美团团购、抖音本地生活、灯火投放… |

> Ken 接收全量数据（物码 + 即时零售 + 到店）。

> 关键词与团队分配规则集中在 [`tender_monitor/keywords.py`](tender_monitor/keywords.py)，可自由增改。

## 二、数据收集规则

- **不再采集 AI 类**招标信息。
- 仅采集 **发布时间 ≥ 2026-06-01** 的招标（含当日）。
- 仅采集 **投标截止时间尚未过期** 的招标（截止日期 ≥ 执行当日）。
- 日期无法解析的条目遵循宽松策略，默认保留，避免漏掉有效招标。

> 截止日期阈值由 [`tender_monitor/config.py`](tender_monitor/config.py) 中的
> `PUBLISH_DATE_CUTOFF`（默认 `2026-06-01`）控制，可在环境变量中调整。

## 三、在线表格（4 张，按类别拆分）

| 表格 | 数据范围 | 链接 |
|------|---------|------|
| **总表** | 物码 + 即时零售 + 到店 | [招标信息监控总表](https://docs.qq.com/sheet/DQk9wdmtIbmVTT1Bp) |
| **物码** | 仅物码 | [物码-招标信息监控表](https://docs.qq.com/sheet/DQkpoQ3pqcmd4SUdn) |
| **即时零售** | 仅即时零售 | [即时零售-招标信息监控表](https://docs.qq.com/sheet/DQkxKV01tRVBOeXNp) |
| **到店** | 仅到店 | [到店-招标信息监控表](https://docs.qq.com/sheet/DQmtIdm5Xc0JrRGZZ) |

### 表头（16 列，固定顺序）

```
序号 → 类别 → 信息来源平台 → 招标标题 → 招标单位 → 发布时间
→ 截止时间 → 预算金额 → 原文链接 → 项目地点
→ 采购内容（信息摘要） → 联系人以及联系方式
→ 跟进团队 → 跟进人 → 跟进状态 → 备注
```

- **信息来源平台**：紧跟「类别」列，记录招标公告发布的平台名称（如中国政府采购网、华润守正电子招标平台等）。
- **跟进团队**：按类别自动分配（即时零售-ODM，到店-SDM，物码-SCD）。
- **跟进人 / 备注**：留空，人工填写。
- **跟进状态**：单选下拉 `待跟进 / 跟进中 / 述标中 / 已中标 / 未中标`。
- 每周新增数据**追加到各表格底部**，不覆盖历史；按**原文链接自动去重**。

## 四、看板（4 个，按权限隔离）

| 看板 | 文件 | 数据范围 | 对应人员 |
|------|------|---------|---------|
| 全量看板 | `index.html` | 物码 + 即时零售 + 到店 | Ken |
| 物码看板 | `mon.html` | 仅物码 | Mon |
| 即时零售看板 | `benny.html` | 仅即时零售 | Benny |
| 到店看板 | `david.html` | 仅到店 | David |

每个看板独立托管在 GitHub Pages，链接通过企微推送分别发送给对应人员。

看板特性：
- 每张卡片展示：信息来源平台、招标单位、招标编号、招标方式、采购内容、预算金额、发布时间、截止时间、项目地点、联系方式、跟进团队、跟进人、跟进状态、资料来源
- 按「**类别**」和「**跟进状态**」筛选，支持关键词搜索
- 跟进团队 / 跟进人 / 跟进状态 直接取自在线表格，每次运行回读同步

## 五、企微推送（4 条分层消息）

每周二执行后，通过**企微群机器人 Webhook** 推送 4 条消息（测试阶段统一推送到同一群，后续按人员拆分 Webhook）：

| 序号 | 推送对象 | 数据范围 | 在线表格链接 |
|------|---------|---------|------------|
| 1 | Ken | 全部数据（物码 + 即时零售 + 到店） | 总表 |
| 2 | Mon | 仅物码 | 物码专属表 |
| 3 | Benny | 仅即时零售 | 即时零售专属表 |
| 4 | David | 仅到店 | 到店专属表 |

**消息格式示例（全量 / Ken）：**

```
【招标信息监控周报】2026-07-14
本周新增招标信息：5 条
在线表格（查看全部并填写跟进）：https://docs.qq.com/sheet/...
跟进看板：https://xxx.github.io/.../index.html

新增条目：
[物码] 2 条
  - 一物一码追溯系统采购项目（截止 2026-08-15）
  - 2026年品牌一物一码运营服务（截止 2026-08-20）
[即时零售] 2 条
  - 美团闪购代运营服务招标（截止 2026-07-20）
  - 京东秒送到家业务运营服务（截止 2026-07-18）
[到店] 1 条
  - 门店数字化改造项目招标（截止 2026-07-25）
```

**分类消息格式示例（Mon / 物码）：**

```
【招标信息监控周报】2026-07-14
👤 Mon（仅物码）
本周新增招标信息：2 条
在线表格（查看全部并填写跟进）：https://docs.qq.com/sheet/...
跟进看板：https://xxx.github.io/.../mon.html

新增条目：
[物码] 2 条
  - 一物一码追溯系统采购项目（截止 2026-08-15）
  - 2026年品牌一物一码运营服务（截止 2026-08-20）
```

## 六、快速开始（本地）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env      # 然后填入各项密钥

# 3. 本地跑通（不写在线表格、不推送，仅用现有数据生成看板）
python main.py --dry-run

# 4. 完整执行
python main.py
```

生成的看板在 `dashboard/` 目录，用浏览器打开即可预览。

## 七、部署到 GitHub（自动执行）

### 1. 推送代码到你的 GitHub 仓库（建议设为 Private）

### 2. 在 `Settings → Secrets and variables → Actions` 配置 Secrets

#### 必填 Secrets

| Secret | 说明 | 获取方式 |
|--------|------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | [platform.deepseek.com](https://platform.deepseek.com) |
| `SEARCH_PROVIDER` | 默认 `bocha`（免费 1000次/月） | 可选 `serper`（Google） |
| `BOCHA_API_KEY` | 博查搜索 Key（免费） | [open.bochaai.com](https://open.bochaai.com) |
| `TENCENT_CLIENT_ID` | 腾讯文档应用 Client ID | [docs.qq.com/open](https://docs.qq.com/open) |
| `TENCENT_CLIENT_SECRET` | 腾讯文档应用 Client Secret | 同上 |
| `TENCENT_REFRESH_TOKEN` | OAuth refresh_token | 见下方「获取腾讯文档 Token」 |
| `WECOM_WEBHOOK_URL` | 企微群机器人 Webhook URL | 企微群 → 群设置 → 群机器人 → 添加 → 复制 Webhook 地址 |

#### 在线表格 Secrets（file_id 已内置默认值，可选覆盖）

| Secret | 默认值 | 说明 |
|--------|--------|------|
| `TENCENT_FILE_ID` | `DQk9wdmtIbmVTT1Bp` | 总表 file_id |
| `TENCENT_SHEET_ID` | `000001` | 总表 sheet_id |
| `SHEET_URL` | `https://docs.qq.com/sheet/DQk9wdmtIbmVTT1Bp` | 总表公开链接 |
| `TENCENT_FILE_WM` | `DQkpoQ3pqcmd4SUdn` | 物码表 file_id |
| `TENCENT_SHEET_WM` | `000001` | 物码表 sheet_id |
| `SHEET_URL_WM` | `https://docs.qq.com/sheet/DQkpoQ3pqcmd4SUdn` | 物码表公开链接 |
| `TENCENT_FILE_JS` | `DQkxKV01tRVBOeXNp` | 即时零售表 file_id |
| `TENCENT_SHEET_JS` | `000001` | 即时零售表 sheet_id |
| `SHEET_URL_JS` | `https://docs.qq.com/sheet/DQkxKV01tRVBOeXNp` | 即时零售表公开链接 |
| `TENCENT_FILE_DD` | `DQmtIdm5Xc0JrRGZZ` | 到店表 file_id |
| `TENCENT_SHEET_DD` | `000001` | 到店表 sheet_id |
| `SHEET_URL_DD` | `https://docs.qq.com/sheet/DQmtIdm5Xc0JrRGZZ` | 到店表公开链接 |

#### 可选 Secrets

| Secret | 默认值 | 说明 |
|--------|--------|------|
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | 可自定义 API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型选择 |
| `PUBLISH_DATE_CUTOFF` | `2026-06-01` | 发布时间下限 |
| `DASHBOARD_URL` | — | 看板 GitHub Pages 地址（企微推送用） |

### 3. 开启 GitHub Pages

`Settings → Pages → Build and deployment → Source` 选择 **GitHub Actions**。

首次运行后，看板地址形如 `https://<用户名>.github.io/<仓库名>/`，把它填回 `DASHBOARD_URL`。

### 4. 定时配置（已内置）

`.github/workflows/weekly.yml` 中：

```yaml
on:
  schedule:
    - cron: "30 1 * * 2"   # UTC 01:30 = 北京时间 周二 09:30
  workflow_dispatch: {}    # 也可在 Actions 页手动触发
```

> GitHub Actions 的 cron 使用 **UTC**；北京时间周二 09:30 即 UTC 周二 01:30。

## 八、获取腾讯文档 Token（一次性）

1. 到 [docs.qq.com/open](https://docs.qq.com/open) 注册应用，拿到 `client_id` / `client_secret`，
   并把回调地址填为 `http://localhost:8888/callback`。
2. 本地执行：

   ```bash
   export TENCENT_CLIENT_ID=你的ClientID
   export TENCENT_CLIENT_SECRET=你的ClientSecret
   python scripts/get_refresh_token.py
   ```

3. 浏览器完成授权后，终端会打印 `refresh_token`，填入 GitHub Secret `TENCENT_REFRESH_TOKEN`。

> 腾讯文档的 `refresh_token` 在每次刷新后可能轮换。程序会把最新值写入
> `data/tencent_refresh_token.txt`（默认被 `.gitignore` 忽略）。若你的 token 会频繁轮换，
> 可在私有仓库中放开该忽略项以持久化。

## 九、目录结构

```
tender-monitor/
├── .github/workflows/weekly.yml  # 定时任务（每周二 北京时间 09:30）
├── tender_monitor/
│   ├── config.py                 # 环境变量集中读取（含 4 张表格配置）
│   ├── keywords.py               # 三类主题 & 关键词 & 团队分配
│   ├── search.py                 # 搜索（博查 / Serper）
│   ├── llm.py                    # DeepSeek 解析 & 相关性过滤
│   ├── tencent_docs.py           # 腾讯在线表格 OpenAPI 客户端（支持多表格）
│   ├── store.py                  # 本地数据仓 & 表结构（16列）
│   ├── dashboard.py              # 看板 HTML 生成（支持按类别过滤）
│   ├── wecom.py                  # 企微群机器人推送（4 条分层消息）
│   └── pipeline.py               # 主流程编排
├── scripts/get_refresh_token.py  # 一次性获取腾讯 refresh_token
├── dashboard/                    # 生成的看板（4 个 HTML，Pages 托管）
│   ├── index.html                # 全量看板（Ken）
│   ├── mon.html                  # 物码看板（Mon）
│   ├── benny.html                # 即时零售看板（Benny）
│   └── david.html                # 到店看板（David）
├── data/store.json               # 去重与历史数据仓
├── main.py                       # 入口
├── requirements.txt
├── .env.example
└── README.md
```

## 十、成本与频控

- DeepSeek：仅对**新链接**做解析，单次运行默认上限 `MAX_LLM_CANDIDATES=120`、`MAX_NEW_PER_RUN=60`。
- 腾讯文档 OpenAPI：每应用每月免费 20000 次调用。
- 搜索：博查 / Serper 均按调用计费，可用 `MAX_RESULTS_PER_KEYWORD` 控制。

## 十一、许可

内部工具，按需自用。
