import urllib.request
import json
import sys

url = "http://127.0.0.1:7000/v1/chat/completions"
data = {
    "messages": [{"role": "user", "content": "hello"}],
    "stream": False
}
req = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req) as response:
        print(f"Status: {response.status}")
        body = response.read().decode("utf-8")
        print("Response:")
        print(body)
except Exception as e:
    print(f"Failed: {e}", file=sys.stderr)
