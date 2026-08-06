import urllib.request
import json
import sys

def test_news_analyze():
    url = "http://127.0.0.1:8005/api/news/analyze"
    payload = {
        "title": "US Non-Farm Payrolls (NFP)",
        "impact": "High",
        "actual": "245K",
        "forecast": "190K",
        "previous": "229K",
        "date": "2026-08-05",
        "time": "14:30"
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req) as resp:
        res_data = json.loads(resp.read().decode('utf-8'))
        print("API Response Status:", resp.status)
        print("News Title:", res_data.get("title"))
        print("Recommendation:", res_data.get("recommendation"))
        sys.stdout.buffer.write(("Analysis Snippet: " + res_data.get("analysis")[:200] + "\n").encode('utf-8'))
        assert res_data.get("status") == "SUCCESS"
        print(">>> ALL NEWS ANALYZE CHECKS PASSED 100% <<<")

if __name__ == "__main__":
    test_news_analyze()
