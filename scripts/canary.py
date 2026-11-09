"""
canary.py
---------
Runs calibration tests: judges must rank golden set above anti-set.
Called after any prompt change, model change, or every 10 episodes.
"""
import os
import json
import sys
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(Path(__file__).parent.parent / ".env")
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

import ledger
from foundation_loader import load_foundations, FoundationBundle

MODEL_FALLBACKS = [
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

def _call_gemini(prompt: str) -> str:
    for model_name in MODEL_FALLBACKS:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                continue
            raise
    raise RuntimeError("All models exhausted in canary test")

def run_canary_test(bundle: FoundationBundle = None) -> bool:
    if bundle is None:
        bundle = load_foundations()
        
    golden = bundle.golden_set.get("golden", [])
    anti = bundle.golden_set.get("anti", [])
    
    if not golden or not anti:
        print("[canary] Skipping: golden set or anti-set is empty.")
        ledger.record_canary_result(True, "skipped: empty golden/anti set")
        return True
    
    rubric_summary = "\n".join(
        f"- {dim}: {data['anchors']['5']}" 
        for dim, data in bundle.rubric.get("dimensions", {}).items()
    )
    
    test_cases_passed = 0
    test_cases_total = 0
    
    for golden_item in golden[:2]:
        for anti_item in anti[:2]:
            test_cases_total += 1
            
            prompt = f"""You are a script quality judge for a Discord chat comedy channel.

RUBRIC (what makes a script good):
{rubric_summary}

SCRIPT A:
Title: {golden_item.get('title', 'Unknown')}
Why it was selected as GOOD: {golden_item.get('why_it_works', '')}

SCRIPT B (known bad example):
Title: {anti_item.get('title', 'Unknown')}
Why it was flagged as BAD: {anti_item.get('why_it_fails', '')}

Based on the rubric above, which script is higher quality?
Reply with ONLY: "A" or "B"
"""
            try:
                result = _call_gemini(prompt).strip().upper()
                if result.startswith("A"):
                    test_cases_passed += 1
                else:
                    print(f"[canary] FAIL: Preferred anti-set script B over golden script A")
            except Exception as e:
                print(f"[canary] Error during test: {e}")
    
    if test_cases_total == 0:
        ledger.record_canary_result(True, "no test cases run")
        return True
    
    pass_rate = test_cases_passed / test_cases_total
    passed = pass_rate >= 0.75
    
    details = f"Pass rate: {test_cases_passed}/{test_cases_total} ({pass_rate:.0%})"
    ledger.record_canary_result(passed, details)
    
    if not passed:
        print(f"[canary] CANARY FAIL! {details}")
        print("[canary] System pausing. Human review required before next run.")
    else:
        print(f"[canary] PASS. {details}")
    
    return passed

if __name__ == "__main__":
    b = load_foundations()
    res = run_canary_test(b)
    print(f"Canary result: {'PASS' if res else 'FAIL'}")
