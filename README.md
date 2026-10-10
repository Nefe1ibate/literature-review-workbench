# Literature Review Workbench

中文 | [English](README.en.md)

可在本地配置的 Codex skill，用于创建、更新和审查有来源依据的文献综述。持久保存论文、来源版本、证据、主张、章节、段落和审查意见，并提供只读文献库导入和可选学科核验规则。

这是受 DAS 方法启发的独立实现，不是官方 DAS 生成器，也不声称具有同等基准表现。来源和方法对应关系保存在 skill 的 `references/` 中。辅助程序只检查结构、文件指纹和依赖关系；实际阅读、引用支持和学术判断需要 Codex 或研究者执行。

## 本地安装

需要 Python 3.10+ 和支持本地 skills、文件读写及命令执行的 Codex 环境。辅助程序只用 Python 标准库，不需要 API 密钥或第三方 Python 包。模型访问、外部搜索、PDF 解析及文档导出使用你环境中已有的能力，独立于本仓库；没有固定必需的 MCP 服务。

Windows PowerShell、macOS 和 Linux 都可运行：

```sh
git clone https://github.com/Nefe1ibate/literature-review-workbench.git
cd literature-review-workbench
python -B install.py
```

如果系统使用 `python3`，将 `python` 替换为 `python3`；Windows 也可以用 `py -3`。没有 Git 时可点击 **Code → Download ZIP**，解压后在仓库目录执行安装命令。

默认安装到 `~/.agents/skills/literature-review-workbench`，遵循 [Codex 官方文档](https://learn.chatgpt.com/docs/build-skills)。安装脚本只复制随仓库提供的 skill，不联网，不改 Codex 配置，不覆盖已有安装。

旧版或自定义 skill 目录可使用：

```sh
python -B install.py --skills-dir ~/.codex/skills
```

仅用于某个项目时，从项目目录执行：

```sh
python -B /path/to/literature-review-workbench/install.py --skills-dir .agents/skills
```

手动安装时，把 `skills/literature-review-workbench` 整个文件夹复制到你的 skill 目录，保留 `agents`、`assets`、`references` 和 `scripts`。避免多个发现目录中的同名重复安装；安装后未显示则重启 Codex。

## 使用

附上论文、已有综述或文献库后，在 Codex 输入：

```text
使用 $literature-review-workbench 围绕我的研究问题整理文献综述。
先说明范围、已有来源和检索计划，再建立证据记录、章节与段落计划。
逐项区分原文结果、解释、跨论文综合和拟议研究缺口。
保留阅读状态、来源位置和未知项，并保存检查点供下次继续。
```

只审查已给材料时，可明确要求“封闭语料，不增加外部文献”。开放综述可以使用环境中可用的文献检索能力。请明确研究问题、文献截止日期与交付要求；本 skill 不强制论文数量、年份范围、分类结构或页数上限。

独立复核是可选功能，需要实际独立上下文。没有独立 agent 能力时，仍可维护文献证据和综述状态，但应说明复核限制。

## 检查工具与创建工作目录

从仓库根目录执行：

```sh
python -B tests/test_distribution.py
python -B skills/literature-review-workbench/scripts/workbench.py --help
python -B skills/literature-review-workbench/scripts/import_library.py --help
python -B skills/literature-review-workbench/scripts/workbench.py init --root ../my-literature-review --topic "我的研究主题"
python -B skills/literature-review-workbench/scripts/workbench.py validate --root ../my-literature-review --report ../my-literature-review/checks/validation.json
python -B skills/literature-review-workbench/scripts/workbench.py checkpoint --root ../my-literature-review --label initial
```

工作目录包含 `state.json`、`events.jsonl`、`snapshots/`、`drafts/`、`checks/`。初始化空目录和通过软件测试不代表完成文献阅读或科学核验。空综述可能报告 `needs_review`，表示内容仍待补充；请阅读实际检查结果。

完整命令、记录结构与导入顺序见 [state-contract.md](skills/literature-review-workbench/references/state-contract.md)，长期工作流见 [workflow.md](skills/literature-review-workbench/references/workflow.md)。多写入者可使用 `--expected-revision` 防止用旧版本覆盖新状态。

## 连接本地文献库

复制 [library-config.example.json](skills/literature-review-workbench/assets/library-config.example.json) 到你自己的配置目录，按实际目录、台账格式和字段名修改。相对路径按配置文件所在目录解析；示例中的 `../topic-library` 是占位目录，不随仓库提供。

```sh
python -B skills/literature-review-workbench/scripts/import_library.py --config /path/to/library-config.json --output /path/to/review-output/library-bundle.json
```

导出位置必须在文献库根目录之外；导入只读取文献库，不改原台账。导出的历史证据需要重新核验，不能直接作为新综述中已验证的支持。按状态协议的依赖顺序导入各集合：papers → sources → evidence → searches → claims → sections → paragraphs → reviews → check_results。详情见 [library-adapters.md](skills/literature-review-workbench/references/library-adapters.md)。

## 可选学科规则

仅当规则适合你的学科和研究问题时，复制 [domain-profile.example.json](skills/literature-review-workbench/assets/domain-profile.example.json) 并编辑：

```sh
python -B skills/literature-review-workbench/scripts/workbench.py configure --root ../my-literature-review --domain-profile /path/to/domain-profile.json --reason "启用适用的学科核验规则"
```

规则文件不执行代码，也不替代实际检查。详情见 [domain-profiles.md](skills/literature-review-workbench/references/domain-profiles.md)。

## 更新、卸载与许可

更新下载目录时运行 `git pull --ff-only`，备份已有安装并将备份移出所有 skill 发现目录，然后重新安装。安装脚本会拒绝覆盖目标。卸载时仅移除安装的 `literature-review-workbench` 文件夹，保留你的文献库和综述工作目录。

本地代码与说明采用 [MIT License](LICENSE)。外部论文、网站和上游项目保留其原有许可，本仓库不附带这些第三方材料。公共仓库中不包含个人论文库、综述运行记录或凭据；请将自己的配置和研究数据保存在仓库之外。
