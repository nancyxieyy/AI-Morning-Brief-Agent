#!/usr/bin/env python3
"""
测评用例捕获器 (Case Collector)
从最近一次 run.py 运行的日志中，提取全量原始 RSS 载荷文章，加上测试断言（规则+大模型裁判预期），
一件录入到 Golden / Regression / Badcase 测试集里。
"""
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "agents" / "evals" / "datasets"
LAST_RUN_FILE = BASE_DIR / "logs" / "last_run_articles.json"

def main():
    parser = argparse.ArgumentParser(description="一键捕获最近一次晨报抓取的 RSS 原料入库")
    parser.add_argument("--type", choices=["golden", "regression", "badcases"], required=True, help="要存入的目标弹药库")
    parser.add_argument("--name", type=str, default=f"Case-{datetime.now().strftime('%Y%m%d-%H%M')}", help="用例名称（如：广告混入事故）")
    parser.add_argument("--criteria", type=str, required=True, help="裁判打分标准（如：不准出现八卦新闻、必须要排版美观）")
    parser.add_argument("--min-count", type=int, default=0, help="最低应输出并提取出的合格文章数")
    parser.add_argument("--must-include", type=str, default="", help="逗号分隔的硬性规则：必须包含的关键词")
    parser.add_argument("--must-exclude", type=str, default="", help="逗号分隔的硬性规则：绝不允许出现的关键词")
    
    args = parser.parse_args()
    
    if not LAST_RUN_FILE.exists():
        print(f"❌ 找不到最近的一次运行记录 ({LAST_RUN_FILE})")
        print("   💡 请先让早报引擎 `python3 agents/morning_brief/run.py` 运行一次，产生原始物料。")
        sys.exit(1)
        
    try:
        articles = json.loads(LAST_RUN_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ 读取物料载荷记录失败: {e}")
        sys.exit(1)

    if not articles:
        print("❌ 上次运行抓取到 0 篇文章，无法生成有效用例。")
        print("   💡 请等早报正常运行一次后再捕获。")
        sys.exit(1)
        
    target_file = DATA_DIR / f"{args.type}.json"
    
    try:
        if target_file.exists():
            dataset = json.loads(target_file.read_text(encoding="utf-8"))
        else:
            dataset = []
    except:
        dataset = []
        
    new_case = {
        "name": args.name,
        "input_articles": articles,
        "criteria": args.criteria,
        "rules": {
            "min_article_count": args.min_count,
            "must_include": [k.strip() for k in args.must_include.split(",") if k.strip()],
            "must_exclude": [k.strip() for k in args.must_exclude.split(",") if k.strip()]
        }
    }
    
    dataset.append(new_case)
    target_file.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"✅ 成功提取上次运行时的 {len(articles)} 篇 RSS 原料")
    print(f"   => 已封装为用例 [{args.name}] 并塞入 📁 {args.type}.json")
    print(f"   => 裁判准则: {args.criteria}")
    print(f"   => 规则拦截: 最少需要 {args.min_count} 篇文章")

if __name__ == "__main__":
    main()
