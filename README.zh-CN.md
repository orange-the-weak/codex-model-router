# Codex Auto Model Router

一个面向 OpenAI Codex 的任务级模型路由 Skill：根据项目和任务难度，在 GPT-5.6 Sol、Terra、Luna 之间分配工作，自动选择 `low`、`medium`、`high` 或 `xhigh` 推理强度，并通过真实使用记录持续微调。

[English README](README.md)

## 主要能力

- 分析项目结构，为不同任务推荐最小够用的模型和推理强度。
- Apply 模式为整次请求只选择一条路由；当前 Codex 界面提供同任务 `model` 与 `thinking` 覆盖时才执行切换，并在可靠元数据可用时恢复原路由。
- 报告缺失或过期时不再额外插入 Assess 回合；边界明确的任务使用确定性默认路由，以减少延迟。
- 单文件机械小改在切换与恢复成本高于任务本身时保持当前模型；用户明确指定模型时仍严格遵循指定值。
- 通过 `CODEX_THREAD_ID` 与本地 `turn_context` 或 `thread_settings_applied` 设置元数据识别当前任务和原路由，不读取提示词正文。
- 默认使用 Sol / medium 完成首次分析，也允许用户指定任意 Sol、Terra、Luna 和推理强度组合。
- 每次路由请求开始前，在 Codex 对话框显示一次模型、推理强度和任务目的。
- Query 和 Record 使用本地脚本快速完成，不启动分析 Agent。
- 分开统计实际执行比例、分析调用比例和最新建议比例。
- 根据成功、失败、升级、返工和耗时证据微调任务分配。
- GPT-5.6 不可用时回退到当前可用 Codex 模型，并如实记录。
- 完整报告写入 Markdown，对话框只显示简短结论和预计增效。
- 不需要 API Key，也不接入外部模型 API。

## 安装

### 在 Codex 对话框安装纯 Skill

直接在 Codex 对话框发送：

```text
$skill-installer 从 GitHub 安装 https://github.com/orange-the-weak/codex-auto-model-router
```

Skill 安装器会把 Skill 放到 `~/.codex/skills/codex-auto-model-router`，但不会运行仓库的 `install.sh`、安装可选的 24 个自定义 Agent 预设，也不会清理旧 Skill 名称。首次只安装 Skill 时已够用；完整安装或名称迁移请使用下面的终端方式。安装后重启 Codex。

### 终端手动安装

```bash
git clone https://github.com/orange-the-weak/codex-auto-model-router.git
cd codex-auto-model-router
./install.sh
```

安装后重新启动 Codex，使 Skill 和自定义 Agent 生效。
从旧名称升级时，安装脚本只会清理旧的 `codex-model-router` Skill 目录和 `project-model-*` 预设，避免 Codex 同时显示新旧两个名称。

## 使用示例

```text
$codex-auto-model-router 分析当前项目并优化模型分配
$codex-auto-model-router 查询各模型实际使用比例
$codex-auto-model-router 记录：Terra low 完成 UI 调整，耗时 90 秒
$codex-auto-model-router 根据历史成功率、返工和耗时微调任务分配
$codex-auto-model-router 用 Terra high 分析当前项目
$codex-auto-model-router 按照已保存的路由规划实现这个功能
```

路由任务开始前会显示一条简洁提示；命令、文件、验证和恢复阶段不重复显示：

```text
Codex 自动路由｜任务段：项目分析｜模型：GPT-5.6 Sol｜推理：medium｜Codex 根据项目范围自动选择
```

当当前 Codex 界面提供带模型和推理字段的同任务续接能力时，任务会在当前任务内切换，并在原路由可验证时完成后恢复；否则依次尝试显式可选模型的子智能体和当前模型。不会新开顶层任务，也不能把普通子任务名称当成模型已经切换的证据。以后另开的独立任务需要再次调用 Skill，或明确要求沿用已保存的路由报告。

## 输出文件

- 完整报告：`docs/codex-model-routing-report.md`
- 使用账本：`.codex/model-routing-history.jsonl`

实际执行、Skill 分析调用和建议分配会分开统计。建议不会被伪装成真实使用记录，账本也不会保存提示词、源码、密钥或对话内容。

## 调整阈值

- 同类任务至少 5 次，失败、升级或返工压力达到 40%，才建议升档。
- 同类任务至少 10 次、成功率达到 90%、没有压力事件且可确定性验证，才建议降档。
- 样本不足时保持原分配。

## 许可证

MIT。详见 [LICENSE](LICENSE)。

这是独立社区项目，与 OpenAI 无隶属或官方背书关系。
