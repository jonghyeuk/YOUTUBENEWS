"""gpt-image-2 이미지 생성 (스트리밍 + JPEG).

왜 이렇게 하나:
- 이 클라우드 세션의 프록시는 응답이 ~30초 넘게 걸리면 502 "upstream request failed"를 돌려준다.
  4K 고품질 이미지는 1~2분 걸리므로 stream=true(SSE)로 연결을 유지해야 한다.
- PNG 4K 결과는 base64로 수십 MB라 마지막 이벤트 수신 중 연결이 끊긴 적이 있다 →
  output_format=jpeg(품질 92)로 전송량을 줄인다.
- 크레딧 소진(429 credit_balance_exhausted)은 재시도해도 소용없으니 즉시 중단한다.

사용: python imggen.py job.json
job.json: {"prompt": "...", "out": "path.jpg", "size": "3840x2160", "quality": "high",
           "refs": ["ref.jpg", ...]}   # refs가 있으면 /images/edits (참조 이미지로 화풍·인물 고정)
"""
import sys, json, base64, time
import requests

API = "https://api.openai.com/v1/images"


def _read_stream(resp, out_path):
    final = None
    for line in resp.iter_lines():
        if not line or not line.startswith(b"data:"):
            continue
        payload = line[5:].strip()
        if payload == b"[DONE]":
            break
        ev = json.loads(payload)
        if "error" in ev:
            print("  ERROR", json.dumps(ev)[:400])
            return False
        t = ev.get("type", "")
        if t.endswith("partial_image"):
            print("  partial", ev.get("partial_image_index"), flush=True)
        elif t.endswith("completed"):
            final = ev
    if not final or "b64_json" not in final:
        print("  no final image received")
        return False
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(final["b64_json"]))
    print("saved", out_path, final.get("usage"))
    return True


def generate(prompt, out, size="3840x2160", refs=None, quality="high", model="gpt-image-2", tries=3):
    for attempt in range(tries):
        try:
            if refs:
                files = [("image[]", (r.split("/")[-1], open(r, "rb"), "image/jpeg")) for r in refs]
                resp = requests.post(f"{API}/edits", stream=True, timeout=900, files=files, data={
                    "model": model, "prompt": prompt, "size": size, "quality": quality, "n": "1",
                    "stream": "true", "partial_images": "1",
                    "output_format": "jpeg", "output_compression": "92"})
            else:
                resp = requests.post(f"{API}/generations", stream=True, timeout=900, json={
                    "model": model, "prompt": prompt, "size": size, "quality": quality, "n": 1,
                    "stream": True, "partial_images": 1,
                    "output_format": "jpeg", "output_compression": 92})
            if resp.status_code != 200:
                body = resp.text[:400]
                print("HTTP", resp.status_code, body)
                if "credit_balance_exhausted" in body or "insufficient_quota" in body:
                    return False  # 충전 전엔 재시도 무의미
                time.sleep(5)
                continue
            if _read_stream(resp, out):
                return True
        except Exception as e:
            print("EXC", e)
            time.sleep(5)
    return False


if __name__ == "__main__":
    job = json.load(open(sys.argv[1], encoding="utf-8"))
    ok = generate(job["prompt"], job["out"], job.get("size", "3840x2160"),
                  job.get("refs"), job.get("quality", "high"))
    sys.exit(0 if ok else 1)
