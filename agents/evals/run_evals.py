#!/usr/bin/env python3
"""
自动评测沙盒 (Evals Runner) v2
- 支持 Rule-based 快速失败（省 Token） + LLM-as-a-Judge 深度评分
- 默认采用另一个大模型 (Ollama) 作为裁判进行独立思考，避免同源模型出现盲点。
- 独立历史记录落盘，以供对比退化曲线
- 支持 CLI 参数选择特定数据集
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
EVALS_DIR = BASE_DIR / "agents" / "evals"
DATA_DIR = EVALS_DIR / "datasets"
LOG_DIR = BASE_DIR / "logs"

# 引入项目原本的摘要器配置
sys.path.insert(0, str(BASE_DIR / "agents" / "morning_brief"))
try:
    from run import summarize_with_claude_cli, summarize_with_ollama, build_prompt
except ImportError as e:
    print(f"⚠️ 无法导入 run.py 的核心函数: {e}")
    sys.exit(1)

# 为 Ollama 和 Claude 准备的评分提示词
JUDGE_PROMPT_TEMPLATE = """你是公正无私架构评测裁判。
请对大模型生成的摘要文本进行严格打分。
评估通过标准：
{custom_criteria}

大模型生成的输出结果如下：
---
{generated_text}
---

请严格返回 JSON（不要输出多余解释和 Markdown，必须可以用 json.loads 加载）：
{{
  "score": 0到100的量化分数,
  "passed": true 或 false (综合及格即true),
  "reason": "扣分原因或通过的评价"
}}
"""

def load_dataset(filename: str) -> list:
    f = DATA_DIR / filename
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except:
        return []

def run_rule_based_checks(generated_text: str, rules: dict) -> tuple[bool, str, dict]:
    """执行 Rule-Based 格式硬性规则检查"""
    try:
        raw = generated_text.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.endswith("```"):
            raw = raw[:-3]
            
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start == -1 or end == 0:
            return False, "无法找到 JSON 对象边界", {}
            
        parsed_json = json.loads(raw[start:end])
    except Exception as e:
        return False, f"JSON 解析失败: {e}", {}

    articles = parsed_json.get("articles", [])
    expected_min_count = rules.get("min_article_count", 0)
    if len(articles) < expected_min_count:
        return False, f"文章数量不足 (期望 >={expected_min_count}, 实际={len(articles)})", parsed_json
        
    must_include = rules.get("must_include", [])
    for kw in must_include:
        if kw.lower() not in generated_text.lower():
            return False, f"缺失必须包含的关键词: {kw}", parsed_json
            
    must_exclude = rules.get("must_exclude", [])
    for kw in must_exclude:
        if kw.lower() in generated_text.lower():
            return False, f"出现了禁止的关键词: {kw}", parsed_json

    return True, "规则层全绿通过", parsed_json

def evaluate_case(case: dict, judge_model: str, dry_run: bool) -> dict:
    """给定原始 case，生成、快抛校验并打分"""
    print(f"  👉 测试靶向用例: {case.get('name', '未命名用例')}")
    
    if dry_run:
        print("  🚧 [Dry-Run 模式] 验证格式加载，跳过实际大模型调用")
        return {"passed": True, "score": 100, "reason": "Dry run pass", "time": 0, "eval_type": "Skip"}
        
    articles = case.get("input_articles", [])
    custom_criteria = case.get("criteria", "必须是一份客观、精炼的摘要。")
    rules = case.get("rules", {})
    
    # 步骤 1: 业务生成（固定测被侧对象 claude_cli）
    prompt = build_prompt(articles, "2026-04-01")
    t0 = time.time()
    try:
        generated_text = summarize_with_claude_cli(prompt)
    except Exception as e:
         return {"passed": False, "score": 0, "reason": f"目标模型生成时崩溃: {e}", "time": time.time()-t0, "eval_type": "Generation_Crash"}
         
    gen_time = time.time() - t0

    # 步骤 2: 规则引擎 (Rule-based Fast Fail) -> 拦截节省 Token
    rule_pass, rule_reason, _ = run_rule_based_checks(generated_text, rules)
    if not rule_pass:
        return {
            "passed": False, 
            "score": 0, 
            "reason": f"基于规则被拦截: {rule_reason}", 
            "time": gen_time,
            "eval_type": "Rule_Engine"
        }

    # 步骤 3: 调度异构裁判大模型评分 (LLM-as-a-Judge)
    judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
        custom_criteria=custom_criteria,
        generated_text=generated_text
    )
    
    judge_t0 = time.time()
    try:
        if judge_model == "ollama":
            judge_res = summarize_with_ollama(judge_prompt)
        else:
            judge_res = summarize_with_claude_cli(judge_prompt)
            
        start = judge_res.find('{')
        end = judge_res.rfind('}') + 1
        judge_json = json.loads(judge_res[start:end])
    except Exception as e:
        judge_json = {"passed": False, "score": 0, "reason": f"裁判模型解析判定失败: {e}"}
        
    judge_json["time"] = gen_time + (time.time() - judge_t0)
    judge_json["model_output"] = generated_text
    judge_json["eval_type"] = f"LLM_Judge({judge_model})"
    return judge_json

def append_to_history(case_name: str, ds_name: str, result: dict):
    """永久落盘审计历史，用于查看模型退化走向"""
    LOG_DIR.mkdir(exist_ok=True)
    history_file = LOG_DIR / "eval_history.jsonl"
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "dataset": ds_name,
        "case_name": case_name,
        "passed": result.get("passed", False),
        "score": result.get("score", 0),
        "reason": result.get("reason", ""),
        "eval_type": result.get("eval_type", "Unknown")
    }
    with open(history_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

def main():
    parser = argparse.ArgumentParser(description="NancysDaily Auto Evals Runner")
    parser.add_argument("--dataset", type=str, help="指定跑哪个数据集，如 golden.json，不传则跑全部")
    parser.add_argument("--judge-model", choices=["claude", "ollama"], default="ollama", help="打分裁判使用的独立大模型（默认使用 Ollama 本地裁判，规避 Claude 互评盲区）")
    parser.add_argument("--dry-run", action="store_true", help="跳过大模型调用，快速跑通验证管线")
    args = parser.parse_args()

    print("==================================================")
    print(f"🚀 NancysDaily 自动化评测机 v2")
    print(f"   🤖 现任主裁判: {args.judge_model.upper()}")
    print("==================================================\n")
    
    target_datasets = [args.dataset] if args.dataset else ["golden.json", "regression.json", "badcases.json"]
    
    total_cases = 0
    total_passed = 0
    
    for ds_name in target_datasets:
        cases = load_dataset(ds_name)
        if not cases:
            print(f"📁 [{ds_name}] 暂无用例数据，绕过此队列。")
            continue
            
        print(f"📁 =============== 评测集: {ds_name} ({len(cases)} 用例) ===============")
        for c in cases:
            case_name = c.get('name', '未命名用例')
            res = evaluate_case(c, args.judge_model, args.dry_run)
            
            # 记录打分落库
            if not args.dry_run:
                append_to_history(case_name, ds_name, res)
            
            status = "✅ PASS" if res.get("passed") else "❌ FAIL"
            score = res.get("score", 0)
            reason = res.get("reason", "")
            eval_type = res.get("eval_type", "Unknown")
            
            print(f"     [{status}] {eval_type}拦截器 | 最终打分: {score} | 链路总耗时: {res.get('time', 0):.1f}s")
            print(f"     => 【案件评语】: {reason}\n")
            
            total_cases += 1
            if res.get("passed"):
                total_passed += 1

    print("==================================================")
    if total_cases == 0:
        print("💡 当前沙盒无测试录入，请通过 save_case.py 加入测试弹药后重试。")
    else:
        print(f"🎯 管线封测完成: 【{total_passed}/{total_cases}】项通过！")
        if total_passed < total_cases:
            print("⚠️ 【拦截报警】：存在质量退化的生成实例，禁止代码发布至线上环节。退出码 1")
            sys.exit(1)
        else:
            print("✅ 【畅行绿灯】：所有严格质量防线和评估准则均已攻克，准许集成发布！")

if __name__ == "__main__":
    main()
