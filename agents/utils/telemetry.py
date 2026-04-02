import json
import os
import time
from datetime import datetime
from pathlib import Path

# Prices per 1M tokens (Using approximate Claude 3.5 Sonnet stats as reference)
# Since you are using claude -p, the actual billing is $0, but tracking this cost 
# allows you to mathematically prove your agent's efficiency optimizations.
PRICING = {
    "claude_cli": {"input": 3.0, "output": 15.0},
    "ollama": {"input": 0.0, "output": 0.0} # Local model is free
}

class TokenMonitor:
    def __init__(self, log_dir: Path):
        self.log_file = log_dir / "telemetry_usage.jsonl"
        
    def _estimate_tokens(self, text: str) -> int:
        """
        Fast token estimation without Heavy ML Dependencies (like tiktoken).
        English/Code averages ~4 chars per token.
        Chinese averages ~1.5 to 2 chars per token.
        Safe unified heuristic: UTF-8 bytes length / 2.5
        """
        if not text:
            return 0
        return max(1, int(len(text.encode('utf-8', errors='ignore')) / 2.5))

    def record_usage(self, agent_name: str, model: str, prompt: str, response: str, duration: float, error: str = None) -> dict:
        """记录调用并打印可视化 Telemetry"""
        input_tokens = self._estimate_tokens(prompt)
        output_tokens = self._estimate_tokens(response)
        
        rates = PRICING.get(model, {"input": 0.0, "output": 0.0})
        cost_usd = (input_tokens / 1000000.0) * rates["input"] + (output_tokens / 1000000.0) * rates["output"]
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration_sec": round(duration, 2),
            "estimated_cost_usd": round(cost_usd, 6),
            "error": error
        }
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
            
        # UI Terminal Feedback
        status = "❌ FAIL" if error else "✅ OK"
        print(f"  📊 [Telemetry {status}] {model} | Input: ~{input_tokens} tk | Output: ~{output_tokens} tk | Time: {duration:.1f}s | Virtual Cost: ${cost_usd:.5f}")
        return log_entry
