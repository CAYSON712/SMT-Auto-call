#!/usr/bin/env python3
"""
SMT Auto Call - 对话评分脚本

读取 result 目录下的对话日志文件，使用 DeepEval 进行多维度评分。

用法:
    # 评分最新的日志文件
    python scripts/evaluate.py

    # 评分指定日志文件
    python scripts/evaluate.py 20260719_195813_我要自提.log

    # 评分指定目录下的所有日志
    python scripts/evaluate.py --all
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

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

LLM_BASE_URL = env_config.get("LLM_BASE_URL", "https://apihub.agnes-ai.com/v1")
LLM_API_KEY = env_config.get("LLM_API_KEY", "sk-HgbOgK3QZv6JKRCr54SjpF6OCLu5unV4plFdh3He3DcVZzbr")
LLM_MODEL = env_config.get("LLM_MODEL", "agnes-2.0-flash")

# ============================================================
# 日志解析
# ============================================================

def parse_log(filepath: str) -> dict | None:
    """解析日志文件，返回 {scenario, history, llm_model, session_id}"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"[错误] 无法读取文件 {filepath}: {e}", file=sys.stderr)
        return None

    # 提取元信息
    scenario_match = re.search(r"场景:\s*(.+)", content)
    llm_match = re.search(r"LLM 模型:\s*(.+)", content)
    session_match = re.search(r"Session:\s*(\S+)", content)

    scenario = scenario_match.group(1).strip() if scenario_match else "未知场景"
    llm_model = llm_match.group(1).strip() if llm_match else "未知模型"
    session_id = session_match.group(1).strip() if session_match else ""

    # 提取对话轮次
    history = []
    blocks = re.split(r"----- 第 \d+ 轮 -----", content)
    for block in blocks[1:]:  # 跳过开头的元信息部分
        llm_raw_match = re.search(r"\[LLM 决策\] (.+)", block)
        user_match = re.search(r'\[SMT 用户\] "(.+)"', block)
        smt_match = re.search(r'\[SMT AI\]   "(.+)"', block)

        llm_raw = llm_raw_match.group(1).strip() if llm_raw_match else ""
        user_msg = user_match.group(1).strip() if user_match else ""
        smt_reply = smt_match.group(1).strip() if smt_match else ""

        history.append((user_msg, smt_reply, llm_raw))

    if not history:
        print(f"[错误] 文件 {filepath} 中未找到对话记录", file=sys.stderr)
        return None

    return {
        "scenario": scenario,
        "llm_model": llm_model,
        "session_id": session_id,
        "history": history,
    }


# ============================================================
# DeepEval 评分
# ============================================================

def evaluate_dialog(history: list, llm_base_url: str, llm_api_key: str, llm_model: str) -> dict:
    """对整个对话进行整体评估，返回评分结果字典（分数范围 0~10，整数）"""
    result = {
        "准确性": 0,
        "流程合理性": 0,
        "答案相关性": 0,
        "幻觉检测": 0,
        "综合评语": "",
        "评估失败": None,
        "总轮数": len(history),
        "空回复轮数": sum(1 for _, s, _ in history if not s),
    }

    valid_rounds = [(u, s) for u, s, _ in history if s]
    if not valid_rounds:
        result["综合评语"] = "所有轮次均为空回复，无法评估"
        return result

    dialog_text = "\n".join(f"用户: {u}\n客服: {s}" for u, s in valid_rounds)

    try:
        import os as _os
        _os.environ["OPENAI_API_KEY"] = llm_api_key
        _os.environ["OPENAI_BASE_URL"] = llm_base_url

        from deepeval.metrics import GEval, AnswerRelevancyMetric, HallucinationMetric
        from deepeval.test_case import LLMTestCase, SingleTurnParams

        # ============================================================
        # 1. 准确性 — 逐轮评估客服回复相对于用户输入的准确性，取平均分
        # ============================================================
        try:
            m = GEval(name="准确性",
                      criteria="客服的回复信息是否准确，没有编造或虚构内容（如虚构菜品、错误价格等）",
                      evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
                      model=llm_model)
            acc_scores = []
            for user_msg, smt_reply in valid_rounds:
                try:
                    tc = LLMTestCase(input=user_msg, actual_output=smt_reply)
                    m.measure(tc)
                    acc_scores.append(m.score)
                except Exception:
                    continue
            result["准确性"] = round((sum(acc_scores) / len(acc_scores)) * 10) if acc_scores else 0
        except Exception:
            result["准确性"] = 0

        # ============================================================
        # 2. 流程合理性 — 整体对话评估（保持整段评估，因为流程是否合理需要看上下文连贯性）
        # ============================================================
        try:
            m = GEval(name="流程合理性",
                      criteria="客服是否完成了必要的确认、引导和下单流程，整体对话逻辑是否顺畅",
                      evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT], model=llm_model)
            tc = LLMTestCase(input=dialog_text, actual_output=dialog_text)
            m.measure(tc)
            result["流程合理性"] = round(m.score * 10)
        except Exception:
            result["流程合理性"] = 0

        # ============================================================
        # 3. 答案相关性 — 逐轮评估，取平均分
        # ============================================================
        try:
            ar = AnswerRelevancyMetric(model=llm_model, threshold=0.5)
            ar_scores = []
            for user_msg, smt_reply in valid_rounds:
                try:
                    tc = LLMTestCase(input=user_msg, actual_output=smt_reply)
                    ar.measure(tc)
                    ar_scores.append(ar.score)
                except Exception:
                    continue
            result["答案相关性"] = round((sum(ar_scores) / len(ar_scores)) * 10) if ar_scores else 0
        except Exception:
            result["答案相关性"] = 0

        # ============================================================
        # 4. 幻觉检测 — 逐轮评估，取平均分
        # ============================================================
        try:
            hc = HallucinationMetric(model=llm_model, threshold=0.5)
            hc_scores = []
            for user_msg, smt_reply in valid_rounds:
                try:
                    hc_tc = LLMTestCase(input=user_msg, actual_output=smt_reply, context=[user_msg])
                    hc.measure(hc_tc)
                    hc_scores.append(hc.score)
                except Exception:
                    continue
            result["幻觉检测"] = round((1.0 - (sum(hc_scores) / len(hc_scores))) * 10) if hc_scores else 0
        except Exception:
            result["幻觉检测"] = 0

        # 综合评语
        empty_note = f"（其中 {result['空回复轮数']} 轮为空回复）" if result['空回复轮数'] > 0 else ""
        remarks = []
        if result["准确性"] >= 8:
            remarks.append("信息准确，无编造")
        elif result["准确性"] >= 5:
            remarks.append("信息基本准确")
        else:
            remarks.append("信息准确性不足")

        if result["流程合理性"] >= 8:
            remarks.append("流程顺畅完整")
        elif result["流程合理性"] >= 5:
            remarks.append("流程基本合理")
        else:
            remarks.append("流程中断较多")

        if result["答案相关性"] >= 8:
            remarks.append("回复紧扣用户问题")
        elif result["答案相关性"] >= 5:
            remarks.append("回复基本相关")
        else:
            remarks.append("回复相关性低")

        if result["幻觉检测"] >= 8:
            remarks.append("无幻觉内容")
        elif result["幻觉检测"] >= 5:
            remarks.append("少量幻觉倾向")
        else:
            remarks.append("存在明显幻觉")

        result["综合评语"] = "；".join(remarks) + empty_note

    except Exception as e:
        result["评估失败"] = str(e)

    return result


# ============================================================
# 结果输出
# ============================================================

def stars(score: int) -> str:
    """分数转星级显示（满分 10 分 = 5 星）"""
    filled = score // 2
    empty = 5 - filled
    return "★" * filled + "☆" * empty


def print_result(filepath: str, log_data: dict, eval_result: dict):
    """打印评分结果"""
    basename = os.path.basename(filepath)
    print()
    print("=" * 60)
    print(f"  文件: {basename}")
    print(f"  场景: {log_data['scenario']}")
    print(f"  轮次: {eval_result['总轮数']} 轮" +
          (f"（{eval_result['空回复轮数']} 轮为空）" if eval_result['空回复轮数'] else ""))
    print(f"  — 满分 10 分 —")
    print("-" * 60)

    if eval_result.get("评估失败"):
        print(f"  评估失败: {eval_result['评估失败']}")
        print("=" * 60)
        return

    dims = [
        ("准确性", "信息是否准确，有无编造"),
        ("流程合理性", "对话流程是否顺畅完整"),
        ("答案相关性", "回复是否紧扣用户问题"),
        ("幻觉检测", "是否包含虚构内容"),
    ]
    for d, desc in dims:
        score = eval_result.get(d, 0)
        print(f"  {d}  {stars(score)}  {score}分")
    print(f"  ── {eval_result.get('综合评语', '')}")
    print("=" * 60)


def save_score(filepath: str, log_data: dict, eval_result: dict):
    """将评分结果追加写入日志文件"""
    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("  DeepEval 评分结果")
    lines.append(f"  评分时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  评分模型: {LLM_MODEL}")
    lines.append(f"  — 满分 10 分 —")
    lines.append("-" * 60)

    if eval_result.get("评估失败"):
        lines.append(f"  评估失败: {eval_result['评估失败']}")
    else:
        dims = ["准确性", "流程合理性", "答案相关性", "幻觉检测"]
        for d in dims:
            score = eval_result.get(d, 0)
            lines.append(f"  {d}  {stars(score)}  {score}分")
        lines.append(f"  ── {eval_result.get('综合评语', '')}")

    lines.append("=" * 60)
    lines.append("")

    content = "\n".join(lines)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(content)
    print(f"[日志] 评分结果已追加到: {os.path.basename(filepath)}")


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="SMT 自动呼叫 - 对话评分工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python scripts/evaluate.py                    # 评分最新的日志
  python scripts/evaluate.py 20260719_195813.log # 评分指定日志
  python scripts/evaluate.py --all               # 评分所有未评分的日志
        """,
    )

    parser.add_argument("filename", nargs="?", default=None, help="日志文件名（相对于 result/ 目录）")
    parser.add_argument("--all", action="store_true", help="评分所有未评分的日志文件")
    parser.add_argument("--result-dir", default=RESULT_DIR, help=f"日志目录，默认 {RESULT_DIR}")
    parser.add_argument("--llm-api-key", default=LLM_API_KEY)
    parser.add_argument("--llm-base-url", default=LLM_BASE_URL)
    parser.add_argument("--llm-model", default=LLM_MODEL)

    args = parser.parse_args()

    result_dir = args.result_dir
    if not os.path.exists(result_dir):
        print(f"[错误] 目录不存在: {result_dir}", file=sys.stderr)
        sys.exit(1)

    # 确定要评分的文件列表
    if args.filename:
        filepath = os.path.join(result_dir, args.filename)
        files = [filepath] if os.path.exists(filepath) else []
        if not files:
            print(f"[错误] 文件不存在: {filepath}", file=sys.stderr)
            sys.exit(1)
    elif args.all:
        files = sorted(
            [os.path.join(result_dir, f) for f in os.listdir(result_dir)
             if f.endswith(".log") and f != ".gitkeep"]
        )
        if not files:
            print("[提示] result/ 目录下没有日志文件")
            return
    else:
        # 默认评分最新的日志文件
        log_files = sorted(
            [f for f in os.listdir(result_dir) if f.endswith(".log")],
            reverse=True
        )
        if not log_files:
            print("[提示] result/ 目录下没有日志文件")
            return
        files = [os.path.join(result_dir, log_files[0])]

    for filepath in files:
        log_data = parse_log(filepath)
        if not log_data:
            continue

        eval_result = evaluate_dialog(
            log_data["history"], args.llm_base_url, args.llm_api_key, args.llm_model
        )

        print_result(filepath, log_data, eval_result)
        save_score(filepath, log_data, eval_result)


if __name__ == "__main__":
    main()
