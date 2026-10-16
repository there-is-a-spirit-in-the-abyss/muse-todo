# Muse 个人任务 V1

[English](README.md) | 简体中文

**在 Muse 中通过对话管理个人任务和原生提醒。**

这是一个基于技能的 Muse 插件，使用本地 SQLite 数据库。
可以用自然语言添加任务、修改截止时间、完成任务或取消提醒。
应用默认使用英文，支持切换西班牙语和葡萄牙语。
本页是中文项目说明，不代表插件已经支持中文回复。

## 在 Muse 中部署

将完整项目压缩包附加到 Muse，然后发送以下指令：

> 请解压这个套件，阅读并执行套件根目录的 MUSE_PROMPT.md，直接开始安装、加载技能，并完成提醒功能验收。

也可以直接提供完整部署提示词：

1. 将完整仓库或当前发布的 `muse-todo-v1.tar.gz` 交给 Muse。
   私有仓库需要授权访问；直接附加压缩包无需分享 GitHub 凭据。
2. 打开 **[部署提示词](MUSE_PROMPT.md)**，将其中完整的英文内容复制给 Muse。
3. Muse 会按照部署流程加载技能，连接原生定时任务与通知工具，并执行实际验收。
   最终报告会说明是否就绪、验证证据以及平台限制。

部署后可以使用以下英文指令：

```text
Add a task to buy groceries tomorrow at 6 PM and remind me 30 minutes before.
Show my open tasks.
Move the grocery task to Friday at 7 PM.
Mark the grocery task as complete.
Use Spanish.
```

上述示例依次表示添加买菜任务并提前提醒、查看未完成任务、修改时间、完成任务和切换语言。
Muse 会使用已确认的时区，时间含义不明确时会询问。
重复部署会保留已有安装数据。插件需要 Python 3.11 及以上版本、SQLite，
以及能够为智能体安排任务并提供 Python 执行和通知权限的 Muse 工具。
提醒能否实际使用，需要在部署时完成验证。

## 工作原理

项目由 Muse 技能、Python 标准库、SQLite 和原生定时任务组成，
支持任务的创建、查询、修改、删除，以及事务发件箱、幂等请求、版本检查、
持久化同步、状态核对、提醒发送前校验和旧版概念验证数据的可逆备份。

## 语言设置

使用 `{"command":"init","timezone":"UTC"}` 初始化，可以添加
`"locale":"es"` 或 `"locale":"pt"`，分别使用西班牙语或葡萄牙语。
已有安装可通过普通命令行接口发送：

```json
{"command":"settings.get"}
{"command":"settings.set","locale":"es"}
```

每行代表一条独立命令。将命令保存为 UTF-8 文件后执行：

```sh
python bin/todo.py --db /absolute/path/to/todos.db --input language.json
```

使用 `en-US` 恢复英文，使用 `pt` 切换葡萄牙语。
设置保存在数据库中，控制技能回复、命令行信息、帮助和提醒文字。
没有语言设置的旧版 V1 安装默认使用英文。
不支持的语言值会被拒绝，不修改数据。重复初始化不会改变已保存语言，
修改语言应使用 `settings.set`。

在 Muse 中明确要求使用英文、西班牙语或葡萄牙语即可。
任务标题保留原始语言。西班牙语采用通用表达，葡萄牙语采用现代拼写，
并尽量使用不限定地区的表达。语言切换不改变时区、日期解析、
命令字段、状态值、标记或标识。

切换语言后，技能会通过正常的状态核对流程更新后续原生提醒文字；
更新完成前，发送校验也会使用当前语言。操作恢复和发送认领的现有保护机制保持不变。
旧版概念验证管理工具没有安装数据库，需要将 `--locale es` 或 `--locale pt`
放在子命令之前，例如：

```sh
python bin/poc.py --locale pt inspect --workspace /absolute/path/to/workspace
```

详见[语言设计](docs/DESIGN_LANGUAGES.md)和[语言实现计划](docs/PLAN_LANGUAGES.md)。

## 本地运行

```sh
python -m unittest discover -s tests -v
python bin/todo.py --db /absolute/path/to/new-v1.db --input init.json
```

在 `init.json` 中填写 `{"command":"init","timezone":"UTC"}`。
其他操作参见[命令参考](references/COMMANDS.md)。
无需通过 pip 安装第三方依赖，也不需要服务器或飞书凭据。
程序接受标准输入，并使用 UTF-8 处理文本输入与输出。

## 文件说明

| 路径 | 用途 |
|---|---|
| `MUSE_PROMPT.md` | 可直接复制给 Muse 的英文部署提示词 |
| `SKILL.md` | 自然语言操作规则与 Muse 工具协调 |
| `muse_todo/service.py`、`store.py` | 参数校验、任务操作、事务和数据结构 |
| `muse_todo/sync.py` | 发件箱协调、恢复、状态核对和发送校验 |
| `bin/todo.py` | 不依赖当前工作目录的命令行入口 |
| `bin/poc.py`、`muse_todo/poc.py` | 旧版数据备份、哈希校验和可逆隔离 |
| `tests/` | 真实 SQLite、命令行子进程和模拟外部调度测试 |
| `docs/DEPLOYMENT.md` | Muse 安装、旧版移除和回退说明 |
| `docs/ACCEPTANCE.md` | 真实对话、定时任务和通知验收 |
| `references/CRON_BRIDGE.md` | 原生定时任务工具的智能体协议 |
| `evidence/` | 本地验证输出与测试分类 |

## 验证边界

本地测试验证 Python、SQLite 和协调协议。原生工具来自独立的 Muse 环境。
本地验证不涉及 SSH 连接，也不修改现有 Muse 安装。
正式使用前，Muse 智能体必须核对实际工具结构，绑定执行与通知目标，
创建唯一的维护任务，并完成真实的端到端验收。
本地模拟不能证明上述操作已经通过。

原生工具返回未知结果时，系统会保留记录并阻止重试，
直到确认上一次调用已经停止，且新的状态快照支持恢复。
同步采用最终一致性，不承诺 SQLite、定时任务和通知之间的全局恰好执行一次。

请将完整发布包和[交接说明](docs/MUSE_HANDOFF.md)交给 Muse。
当前结果见[语言验证报告](docs/LANGUAGES_VERIFICATION.md)，
历史检查见[原始测试报告](evidence/TEST_REPORT.md)。
源码发布包不包含已安装数据库或真实任务。
仓库当前为私有，仅获得访问权限的用户可以查看。
