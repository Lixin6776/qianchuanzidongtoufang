# macOS 使用指南

> 适用版本：当前 main 分支。macOS 使用 **后端直接托管前端**，日常地址是
> <http://127.0.0.1:8000>，不需要单独启动 Vite。

## 1. 前置条件

| 依赖 | 要求 | 检查命令 |
| --- | --- | --- |
| macOS | 建议 macOS 12+ | 「关于本机」 |
| Google Chrome | 正式版，安装在「应用程序」 | 打开 Chrome 能正常使用 |
| Python | 3.11 或更高 | `python3 --version` |
| Node.js | 20 或更高 | `node --version` |
| pnpm | 可通过 pnpm 或 corepack 提供 | `pnpm --version` |
| Git | 用 Git 克隆时需要 | `git --version` |

如果电脑没有 Homebrew，可先按 <https://brew.sh/zh-cn/> 的方式安装，然后执行：

```bash
brew install python@3.12 node@22
```

Chrome 请从官网安装：<https://www.google.com/chrome/>。

## 2. 第一次安装

### 方式 A：Git 克隆

```bash
git clone https://github.com/Lixin6776/qianchuanzidongtoufang.git qianchuan-ai-assistant
cd qianchuan-ai-assistant
chmod +x 安装依赖-macOS.command 启动直播运营助手-macOS.command
./安装依赖-macOS.command
```

### 方式 B：GitHub 下载 ZIP

1. 打开 <https://github.com/Lixin6776/qianchuanzidongtoufang>。
2. 点 `Code` → `Download ZIP`，解压到任意目录。
3. 在 Finder 里右键 `安装依赖-macOS.command` → **打开**。
   如果 macOS 拦截，去「系统设置 → 隐私与安全性」允许打开一次。

安装脚本会完成：

- 创建 `backend/.venv`
- 安装 Python 依赖
- 安装前端依赖
- 构建 `frontend/dist`
- 从 `backend/.env.example` 生成 `backend/.env`

## 3. 启动

双击：

```text
启动直播运营助手-macOS.command
```

也可以在终端执行：

```bash
./启动直播运营助手-macOS.command
```

脚本会：

1. 在后台启动后端 `127.0.0.1:8000`
2. 等待 `/health` 就绪
3. 检查 Chrome 调试端口 `9222`
4. 自动打开 <http://127.0.0.1:8000>

如果 Chrome 弹出千川登录页，**登录一次即可**。助手使用独立 Chrome 配置，不会改动你日常
Chrome 的书签和登录状态。配置目录：

```text
~/Library/Application Support/QianchuanAssistantChrome
```

## 4. 第一次进入工具后要填什么

1. 在「数据源」里填写千川账户 ID（`aavid`）。
2. 填写要盯的直播间名称。
3. 点「连接数据源」。
4. 登录千川后点「立即读取」或按页面提示恢复盯盘。

工具默认只读。任何预算、出价、计划、素材相关的账户写操作，都必须人工确认。

## 5. 从 Windows 搬到 Mac

只复制业务数据，不要复制 Windows 的虚拟环境和 `node_modules`。

| 需要复制 | 新电脑位置 | 作用 |
| --- | --- | --- |
| `.local/` | 项目根目录 | 盯盘记录、复盘、对话、飞书授权、页面 URL |
| `backend/.env` | `backend/.env` | 账户、直播间、大模型等本地配置 |
| `backend/qianchuan.db` | `backend/qianchuan.db` | 策略、学习和数据资产相关数据库 |

迁移后重新运行：

```bash
./安装依赖-macOS.command
```

Windows 上的 Chrome 登录态 **不能直接复制**。到 Mac 后重新登录一次千川即可。

> 不同千川账户不要复用同一份历史基线。切换账户时应使用独立的数据库与 `.local/`
> 目录，避免把旧账户的消耗、ROI 和操作历史误当成新账户基线。

## 6. 数据来源与口径

- 优先使用已配置的开放平台 API。
- 否则通过本机 Chrome 调试端口读取千川页面。
- 操作日志来自千川平台，包含人工操作；没有读到日志时要显示“没读到”，不能伪造因果。
- ROI 页面会明确标出口径；分析时不得把综合 ROI、素材 ROI 混用。

## 7. 常见问题

### 提示找不到 Chrome

确认 Chrome 在：

```text
/Applications/Google Chrome.app
```

如果装在当前用户的 Applications 目录，也支持：

```text
~/Applications/Google Chrome.app
```

### Chrome 正在运行，9222 连不上

普通 Chrome 启动后再加调试端口通常无效。工具会自动改用独立配置的助手浏览器。
如果仍失败，完全退出 Chrome 后重新点「连接数据源」。

### 8000 端口被占用

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

先退出占用端口的程序，再重新启动。

### 后端没起来

查看：

```text
.local/logs/backend.out.log
.local/logs/backend.err.log
```

### 页面能打开，但数据不更新

1. 看「数据源」是否显示已连接。
2. 确认千川页面没有退出登录。
3. 点「连接数据源」重试。
4. 检查 `.local/logs/backend.err.log` 是否有 CDP 读取错误。
5. 数据没读到时要按失败处理，不能沿用上一场数据。

### 安装脚本没有执行权限

```bash
chmod +x 安装依赖-macOS.command 启动直播运营助手-macOS.command
```

## 8. 验收边界

当前仓库已完成 macOS 分支的自动化测试，包括：

- macOS Chrome 可执行文件路径
- macOS 默认 Chrome / 助手专用 profile 路径
- macOS Chrome 进程检测
- 后端托管 `frontend/dist` 与 SPA fallback
- 未构建前端时的纯 API 模式

但本次开发验证环境是 Windows。**真实 Mac 首次安装、Chrome 启动和千川登录仍需在 Mac
设备上按本指南做一次验收。** 验收通过标准：

1. `./安装依赖-macOS.command` 无错误完成。
2. `./启动直播运营助手-macOS.command` 能打开 `http://127.0.0.1:8000`。
3. 页面不是空白，API 请求正常。
4. 点「连接数据源」后 Chrome 打开并可登录千川。
5. 读取成功后能看到当前场次数据，而不是上一场缓存。
