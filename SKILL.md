---
name: smt-auto-call
description: This skill should be used when the user wants to simulate an AI automatically calling into the SMT knowledge base system to conduct a conversation and generate recordings. It handles the complete flow of creating a session, sending messages, and ending the session via three HTTP APIs.
---

# SMT Auto Call Skill

## 适用场景

适用于两个场景：

1. **QC 测试** — 需要生成对话录音数据进行测试，传统方式依赖人工拨打电话，耗时长、重复劳动多，且容易受环境噪音干扰。通过脚本调用接口完成对话流程，可大幅提升测试效率。
2. **AI 效果验证** — 需要反复测试客服 AI 在不同场景下的应答情况、验证对话流程是否顺畅。通过 LLM 驱动可快速覆盖多种对话场景，减少人工介入。对话结束后可用评分脚本对客服回复进行多维度评分（准确性、流程合理性、答案相关性、幻觉检测），便于量化评估和追踪优化效果。

## 前置准备

- **需要准备**：LLM API Key（兼容 OpenAI API 格式），SMT API Key（通常使用内置 Key 即可）
- **输入格式**：一句自然语言描述的场景，如"模拟一个顾客想下单买一杯珍珠奶茶，自提"
- **额外依赖**：评分功能需要安装 `deepeval`（`pip install deepeval`）

## 核心 Prompt 模板

脚本 `scripts/smt_call.py` 中内置了以下 System Prompt，由 LLM 扮演用户与 SMT AI 对话：

```
你是一个模拟用户，正在与一个客服 AI 进行对话。

## 角色
- 你扮演一个真实的用户，根据用户描述的场景和目标进行对话。
- 你的回复要自然、口语化，像真人一样。
- 不要暴露你是 AI，不要提及"模拟"、"测试"等词。

## 行为规则
1. 第一轮：只打招呼和说明大概来意，不要一次性把所有信息都说出来。
2. 后续轮次：根据 SMT AI 的回复，逐步提供信息，它问什么你答什么。
3. 当目标达成时，主动结束对话。
4. 当 SMT AI 明确表示无法处理你的需求时，礼貌结束对话。
5. 不要编造 SMT AI 没有提供的信息。

## 输出格式
你必须严格按以下 JSON 格式输出，不要包含其他内容：
{"action": "send" 或 "end", "message": "你要发送的消息内容"}

- 当 `action` 为 "send" 时，`message` 是你下一轮要发送的消息，**不能为空**（脚本遇到空消息会直接终止对话）。
- 当 `action` 为 "end" 时，表示对话已完成，`message` 可以留空或写告别语（内容不会发送给 SMT AI，仅用于控制台展示）。
- 每次只输出一行纯 JSON，不要添加 Markdown 代码块、多余文字或注释。
```

## 操作步骤

1. **配置环境** — 确认 `.env` 文件已配置好 LLM API Key 和 SMT API Key
2. **询问场景** — 向用户确认本次要测试的对话场景和目标
3. **执行对话** — 运行 `python scripts/smt_call.py --scenario "用户描述的场景"`
4. **查看结果** — 观察控制台输出的对话流程，确认 LLM 是否正常驱动对话
5. **评分（可选）** — 运行 `python scripts/evaluate.py` 对最新对话进行 DeepEval 评分，或 `python scripts/evaluate.py --all` 评分所有日志
6. **检查日志** — 到 `result/` 目录下查看对话记录和评分结果

## 输出范例

### 对话输出

```
============================================================
  SMT 自动呼叫
============================================================
  场景: 我要自提，帮我下2份虾炒饭和2杯港式鸳鸯...
  LLM:  agnes-2.0-flash
------------------------------------------------------------
[第 1 轮] LLM 思考中...
[SMT 用户] "你好，我想点个外卖。"
[SMT AI]   "好的，您想要自提还是配送呢？"

[第 2 轮] LLM 思考中...
[SMT 用户] "我要自提。"
[SMT AI]   "好的，那请您先提供一下您的姓名。"

...（多轮逐步对话后）

[日志] 对话记录已保存: result/20260719_201206_xxx.log
[提示] 如需对本次对话评分，请运行: python scripts/evaluate.py 20260719_201206_xxx.log
```

### 评分输出

```
============================================================
  文件: 20260719_201206_xxx.log
  场景: 我要自提，帮我下2份虾炒饭和2杯港式鸳鸯...
  轮次: 5 轮（2 轮为空）
  — 满分 10 分 —
------------------------------------------------------------
  准确性     ☆☆☆☆☆  0分
  流程合理性  ★☆☆☆☆  3分
  答案相关性  ★★★★★  10分
  幻觉检测   ★★★★★  10分
  ── 信息准确性不足；流程中断较多；回复紧扣用户问题；无幻觉内容
============================================================
```

## 脚本说明

| 脚本 | 功能 | 用法 |
|------|------|------|
| `scripts/smt_call.py` | LLM 驱动对话，生成录音数据 | `python smt_call.py --scenario "..."` |
| `scripts/evaluate.py` | DeepEval 多维度评分 | `python evaluate.py`（评分最新日志） |

### evaluate.py 用法

```bash
# 评分最新的日志文件
python scripts/evaluate.py

# 评分指定日志文件
python scripts/evaluate.py 20260719_201206_xxx.log

# 评分所有日志文件
python scripts/evaluate.py --all
```

## 注意事项

- **AI 容易出错的地方**：LLM 可能输出非 JSON 格式（带多余文字），脚本有容错处理但仍需留意控制台输出是否正常
- **建议人工修正的情况**：如果 LLM 生成的对话方向偏离了用户描述的场景，或 SMT AI 回复异常（如空回复），应终止并重新调整场景描述重试
- **API Key 安全**：`.env` 文件包含敏感信息，务必加入 `.gitignore`
- **多轮对话上限**：默认 20 轮兜底，正常对话通常在 5-8 轮内完成，若超过 15 轮仍未结束建议检查场景描述是否合理
- **评分独立运行**：评分脚本需要安装 `deepeval`，且评分结果不会影响对话流程
