"""SSE 流式接口测试脚本"""
import httpx, json, time

URL = "http://localhost:8000/api/chat"
PAYLOAD = {"message": "熊猫基地门票多少钱？", "session_id": "sse-test-001"}

print("=" * 60)
print("🚀 SSE 流式测试")
print(f"   问题: {PAYLOAD['message']}")
print(f"   会话: {PAYLOAD['session_id']}")
print("=" * 60)

t0 = time.time()
token_count = 0
structure_count = 0
end_seen = False
errors = []
final_answer = ""

with httpx.stream("POST", URL, json=PAYLOAD, timeout=120.0) as resp:
    print(f"状态码: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('content-type', '')}")
    print(f"X-Accel-Buffering: {resp.headers.get('x-accel-buffering', '')}")
    print()

    current_event = None
    for line in resp.iter_lines():
        elapsed = time.time() - t0

        if not line.strip():
            continue

        if line.startswith("event:"):
            current_event = line[6:].strip()
            if current_event in ("token", "structure_ready", "end"):
                print(f"[{elapsed:6.2f}s] ═══ event: {current_event} ═══")

        elif line.startswith("data:"):
            data_str = line[5:].strip()
            try:
                data = json.loads(data_str)
            except Exception:
                errors.append(f"JSON 解析失败: {data_str[:80]}")
                continue

            if current_event == "token":
                token_count += 1
                text = data.get("text", "")
                if token_count <= 10:
                    print(f"  token #{token_count}: {repr(text)}")
                elif token_count == 11:
                    print(f"  ... 省略中间 token ...")
                if token_count > 10 and token_count % 20 == 0:
                    print(f"  token #{token_count}: {repr(text[:40])}...")

            elif current_event == "structure_ready":
                structure_count += 1
                stype = data.get("type", "?")
                payload_preview = str(data.get("payload", ""))[:100]
                print(f"  📦 卡片类型: {stype}")
                print(f"     内容: {payload_preview}")

            elif current_event == "end":
                end_seen = True
                final_answer = data.get("final_answer", "")
                session = data.get("session_id", "")
                print(f"  ✅ 最终答案长度: {len(final_answer)} 字符")
                print(f"  Session ID: {session}")

        if end_seen:
            break

print()
print("=" * 60)
elapsed_total = time.time() - t0
print(f"📊 统计:")
print(f"   token 数: {token_count}")
print(f"   structure 卡片: {structure_count}")
print(f"   end 事件: {'收到' if end_seen else '❌ 未收到'}")
print(f"   总耗时: {elapsed_total:.2f}s")
if token_count > 0:
    print(f"   首 token 延迟: {elapsed_total:.2f}s（从请求到结束）")
if errors:
    print(f"⚠️  错误 {len(errors)} 条:")
    for e in errors[:3]:
        print(f"   {e}")
print()
print("最终答案预览（前200字）:")
print(final_answer[:200] if final_answer else "(空)")
print()
print("✅ SSE 测试完成" if (token_count > 0 and end_seen) else "❌ SSE 测试异常")
print("=" * 60)
