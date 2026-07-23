#!/usr/bin/env python3
"""
SMT Auto Call - LLM 驱动的 AI 自动拨入知识库进行对话的脚本

用户只需描述场景/目标，LLM 会自主与 SMT AI 进行多轮对话，
并根据对话进展自行判断何时结束会话。

用法:
    python smt_call.py --scenario "模拟一个顾客想下单买奶茶"

首次使用请先配置 .env 文件（参考 .env.example），填入你的 API Key。
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime


# ============================================================
# 加载 .env 配置
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
RESULT_DIR = os.path.join(PROJECT_DIR, "result")
ENV_PATH = os.path.join(PROJECT_DIR, ".env")


def load_env(env_path: str) -> dict:
    config = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    config[key.strip()] = value.strip()
    return config


env_config = load_env(ENV_PATH)

SMT_BASE_URL = env_config.get("SMT_BASE_URL", "https://smarttalk-asia-test.yamimeal.ca")
SMT_API_KEY = env_config.get("SMT_API_KEY", "Hvcav176asb")
ASSISTANT_ID = int(env_config.get("ASSISTANT_ID", "357"))
REGION = env_config.get("REGION", "US")
TIMEOUT_MS = int(env_config.get("TIMEOUT_MS", "30000"))
MAX_ROUNDS = int(env_config.get("MAX_ROUNDS", "20"))

LLM_BASE_URL = env_config.get("LLM_BASE_URL", "https://apihub.agnes-ai.com/v1")
LLM_API_KEY = env_config.get("LLM_API_KEY", "sk-HgbOgK3QZv6JKRCr54SjpF6OCLu5unV4plFdh3He3DcVZzbr")
LLM_MODEL = env_config.get("LLM_MODEL", "agnes-2.0-flash")


# ============================================================
# 通用 HTTP 请求
# ============================================================

def _build_headers(api_key: str) -> dict:
    return {
        "Content-Type": "application/json",
        "X-API-KEY": api_key,
    }


def _request(method: str, url: str, headers: dict, body: dict | None = None, timeout: int = 60) -> dict:
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"[错误] HTTP {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[错误] 网络请求失败: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[错误] 响应解析失败: {e}", file=sys.stderr)
        sys.exit(1)


# ============================================================
# LLM 调用
# ============================================================

def llm_chat(messages: list[dict], llm_base_url: str, llm_api_key: str, llm_model: str) -> str:
    url = f"{llm_base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {llm_api_key}",
    }
    body = {
        "model": llm_model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    try:
        import requests as _req
        resp = _req.post(url, headers=headers, json=body, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as e:
        print(f"[错误] LLM 调用失败: {e}", file=sys.stderr)
        sys.exit(1)


# ============================================================
# SMT API 操作
# ============================================================

def create_session(base_url: str, api_key: str, assistant_id: int, region: str) -> str:
    url = f"{base_url}/api/RealtimeHttpGateway/sessions"
    headers = _build_headers(api_key)
    body = {"assistantId": assistant_id, "region": region}

    print(f"[创建会话] 正在创建会话 (assistantId={assistant_id}, region={region})...")
    resp = _request("POST", url, headers, body)
    session_id = resp.get("sessionId", "")
    if not session_id:
        print(f"[错误] 创建会话失败: 响应中缺少 sessionId\n{json.dumps(resp, indent=2)}", file=sys.stderr)
        sys.exit(1)
    print(f"[创建会话] 成功 → sessionId: {session_id}")
    print(f"           状态: {resp.get('status', 'N/A')}")
    return session_id


def send_message(base_url: str, api_key: str, session_id: str, text: str, timeout_ms: int = TIMEOUT_MS) -> dict:
    url = f"{base_url}/api/RealtimeHttpGateway/sessions/{session_id}/messages"
    headers = _build_headers(api_key)
    body = {"text": text, "timeoutMs": timeout_ms}

    print(f"[SMT 用户] \"{text}\"")
    resp = _request("POST", url, headers, body)
    output_text = resp.get("outputText", "")
    completion_reason = resp.get("completionReason", "N/A")
    print(f"[SMT AI]   \"{output_text}\"")
    print(f"           完成原因: {completion_reason}")
    return resp


def end_session(base_url: str, api_key: str, session_id: str, reason: str = "http_client_disconnect"):
    url = f"{base_url}/api/RealtimeHttpGateway/sessions/{session_id}?reason={reason}"
    headers = _build_headers(api_key)

    print(f"[结束会话] 正在结束会话 (reason={reason})...")
    resp = _request("DELETE", url, headers)
    closed = resp.get("closed", False)
    status = "成功" if closed else "未能"
    print(f"[结束会话] 会话已{status}关闭")
    return resp


# ============================================================
# 日志记录
# ============================================================

def save_log(result_dir: str, scenario: str, history: list, llm_model: str, session_id: str) -> str:
    os.makedirs(result_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_scenario = "".join(c for c in scenario if c.isalnum() or c in " _-")[:20].strip()
    filename = f"{timestamp}_{short_scenario}.log"
    filepath = os.path.join(result_dir, filename)

    lines = []
    lines.append("=" * 60)
    lines.append("  SMT 自动呼叫 - 对话记录")
    lines.append(f"  时间:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  场景:    {scenario}")
    lines.append(f"  LLM 模型: {llm_model}")
    lines.append(f"  Session: {session_id}")
    lines.append("=" * 60)
    lines.append("")

    for i, (user_msg, smt_reply, llm_raw) in enumerate(history, 1):
        lines.append(f"----- 第 {i} 轮 -----")
        lines.append(f"[LLM 决策] {llm_raw}")
        lines.append(f"[SMT 用户] \"{user_msg}\"")
        lines.append(f"[SMT AI]   \"{smt_reply}\"")
        lines.append("")

    empty_count = sum(1 for _, s, _ in history if not s)
    lines.append("-" * 60)
    lines.append(f"  共 {len(history)} 轮对话" + (f"（{empty_count} 轮为空回复）" if empty_count else ""))
    lines.append("")
    lines.append("如需评分请运行: python scripts/evaluate.py \"{}\"".format(filename))
    lines.append("=" * 60)

    content = "\n".join(lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n[日志] 对话记录已保存: {filepath}")
    print(f"[提示] 如需对本次对话评分，请运行: python scripts/evaluate.py {filename}")
    return filepath


# ============================================================
# LLM 驱动对话
# ============================================================

SYSTEM_PROMPT = """你是一个模拟用户，正在与一个客服 AI 进行对话。你的任务是：

## 角色
- 你扮演一个真实的用户，根据用户描述的场景和目标进行对话。
- 你的回复要自然、口语化，像真人一样，就像日常跟人聊天。
- 不要暴露你是 AI，不要提及"模拟"、"测试"等词。

## 行为规则（非常重要）
1. 第一轮：只打招呼和说明大概来意，**不要一次性把所有信息都说出来**。例如："你好，我想点餐"或"你好，我想下单"即可。
2. 后续轮次：根据 SMT AI 的回复，**逐步提供信息**。它问什么你答什么，就像真实对话一样。
3. 当目标达成（如成功下单、获取到所需信息）时，主动结束对话。
4. 当 SMT AI 明确表示无法处理你的需求时，礼貌结束对话。
5. 不要编造 SMT AI 没有提供的信息。

## 输出格式
你必须严格按以下 JSON 格式输出，不要包含其他内容：
{
  "action": "send" 或 "end",
  "message": "你要发送的消息内容"
}

- 当 `action` 为 "send" 时，`message` 是你下一轮要发送的消息。
- 当 `action` 为 "end" 时，表示对话已完成，`message` 可以留空或写告别语。

注意：每次只输出一行 JSON，不要有多余的文字。"""


def build_llm_messages(scenario: str, history: list[tuple[str, str]]) -> list[dict]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"## 场景描述\n{scenario}\n\n请开始对话。"},
    ]
    for user_msg, smt_reply in history:
        messages.append({"role": "assistant", "content": json.dumps({"action": "send", "message": user_msg}, ensure_ascii=False)})
        messages.append({"role": "user", "content": f"SMT AI 回复: {smt_reply}"})
    return messages


def run_dialog(scenario: str, smt_base_url: str, smt_api_key: str, assistant_id: int, region: str,
               timeout_ms: int, max_rounds: int, llm_base_url: str, llm_api_key: str, llm_model: str,
               result_dir: str):
    print("=" * 60)
    print("  SMT 自动呼叫")
    print("=" * 60)
    print(f"  场景: {scenario}")
    print(f"  LLM:  {llm_model}")
    print("-" * 60)

    session_id = create_session(smt_base_url, smt_api_key, assistant_id, region)
    print("-" * 60)

    history: list[tuple[str, str, str]] = []

    for round_num in range(1, max_rounds + 1):
        print(f"\n[第 {round_num} 轮] LLM 思考中...")

        llm_messages = build_llm_messages(scenario, [(u, s) for u, s, _ in history])
        llm_response = llm_chat(llm_messages, llm_base_url, llm_api_key, llm_model)

        try:
            decision = json.loads(llm_response)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{[^{}]+\}', llm_response)
            if match:
                try:
                    decision = json.loads(match.group())
                except json.JSONDecodeError:
                    print(f"[错误] LLM 输出格式异常: {llm_response}", file=sys.stderr)
                    break
            else:
                print(f"[错误] LLM 输出格式异常: {llm_response}", file=sys.stderr)
                break

        action = decision.get("action", "send")
        user_message = decision.get("message", "")

        if action == "end":
            print(f"[LLM 决策] 对话目标已达成，结束对话")
            if user_message:
                print(f"[告别语] \"{user_message}\"")
            break

        if not user_message:
            print(f"[错误] LLM 返回了空消息: {llm_response}", file=sys.stderr)
            break

        smt_resp = send_message(smt_base_url, smt_api_key, session_id, user_message, timeout_ms)
        smt_reply = smt_resp.get("outputText", "")
        history.append((user_message, smt_reply, llm_response))

        if round_num < max_rounds:
            time.sleep(0.5)
    else:
        print(f"\n[提示] 已达到最大对话轮数 ({max_rounds})，自动结束")

    print()
    print("-" * 60)

    end_session(smt_base_url, smt_api_key, session_id)

    print("=" * 60)
    print(f"  对话流程完成（共 {len(history)} 轮）")
    print("=" * 60)

    save_log(result_dir, scenario, history, llm_model, session_id)


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="SMT 自动呼叫 - LLM 驱动的 AI 自动拨入知识库进行对话",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python smt_call.py --scenario "模拟一个顾客想下单买一杯珍珠奶茶"
  python smt_call.py --scenario "查询订单" --llm-model "gpt-4o-mini"
        """,
    )

    parser.add_argument("--scenario", type=str, required=True, help="对话场景描述")

    parser.add_argument("--assistant-id", type=int, default=ASSISTANT_ID, help=f"Assistant ID，默认 {ASSISTANT_ID}")
    parser.add_argument("--region", default=REGION, help=f"地区代码，默认 {REGION}")
    parser.add_argument("--smt-api-key", dest="smt_api_key", default=SMT_API_KEY, help="SMT API Key")
    parser.add_argument("--smt-base-url", dest="smt_base_url", default=SMT_BASE_URL, help=f"SMT 接口基础 URL")
    parser.add_argument("--timeout-ms", type=int, default=TIMEOUT_MS, help=f"消息超时时间（毫秒），默认 {TIMEOUT_MS}")
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS, help=f"最大对话轮数，默认 {MAX_ROUNDS}")

    parser.add_argument("--llm-api-key", default=LLM_API_KEY, help="LLM API Key")
    parser.add_argument("--llm-base-url", default=LLM_BASE_URL, help=f"LLM 接口基础 URL")
    parser.add_argument("--llm-model", default=LLM_MODEL, help=f"LLM 模型名称（默认 {LLM_MODEL}）")
    parser.add_argument("--result-dir", default=RESULT_DIR, help="对话日志保存目录，默认 result/")

    args = parser.parse_args()

    run_dialog(
        scenario=args.scenario,
        smt_base_url=args.smt_base_url,
        smt_api_key=args.smt_api_key,
        assistant_id=args.assistant_id,
        region=args.region,
        timeout_ms=args.timeout_ms,
        max_rounds=args.max_rounds,
        llm_base_url=args.llm_base_url,
        llm_api_key=args.llm_api_key,
        llm_model=args.llm_model,
        result_dir=args.result_dir,
    )


if __name__ == "__main__":
    main()
