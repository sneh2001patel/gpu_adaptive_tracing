# vllm-project/vllm#9413: [Performance]: inference with qwen2.5 using version vLLM 0.6.3 is felt to be slower
state=closed reason=not_planned created=2024-10-16T08:34:48Z closed=2025-03-18T02:04:36Z labels=['performance', 'stale']
cross-referenced PRs: none

## body (@Jimmy-L99)
### Your current environment

Then I roughly wrote a concurrent test code
<details>
<summary>The output of `concurrent_test.py`</summary>
import asyncio
import time
import random
from datetime import datetime
import httpx
import csv

queries = [
    "query1",
    "query2",
    "query3",
    "query4",
    "query5",
    "query6",
    "query7",
    "query8",
    "query9",
    "query10",
]

async def send_query(user_id, queries, start_event, results, semaphore):

    async with semaphore:
        await start_event.wait()
        query = random.choice(queries)
        send_time = time.perf_counter()
        start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "http://address:host/v1/chat/completions",
                    json={
                        "model": "Qwen2.5-1.5b",
                        "messages": [{"role": "user", "content": query}],
                        "temperature": 0.7,
                    },
                    timeout=120
                )
                end_time = time.perf_counter()
                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                response_time = end_time - send_time
                results.append([user_id, query, start_timestamp, end_timestamp, response_time, response.json()])
            except Exception as e:
                end_time = time.perf_counter()
                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                response_time = end_time - send_time
                results.append([user_id, query, start_timestamp, end_timestamp, response_time, f"Error: {e}"])

async def test_concurrent_users(num_users, queries_per_user=1, max_concurrent=100):

    tasks = []
    results = []
    start_event = asyncio.Event()
    semaphore = asyncio.Semaphore(max_concurrent)

    for user_id in range(1, num_users + 1):
        for _ in range(queries_per_user):
            task = asyncio.create_task(send_query(user_id, queries, start_event, results, semaphore))
            tasks.append(task)

    await asyncio.sleep(0.1)
    test_start_time = time.perf_counter()
    start_event.set()
    await asyncio.gather(*tasks)
    test_end_time = time.perf_counter()

    with open('/root/ljm/ChatGLM4/GLM-4/lichi_demo/langchain/test_results.csv', 'a', newline='') as csvfile:
        fieldnames = ['User ID', 'Query', 'Start Timestamp', 'End Timestamp', 'Response Time', 'Response']
        writer = csv.writer(csvfile)
        writer.writerow(fieldnames)
        writer.writerows(results)

    response_times = [result[4] for result in results if isinstance(result[4], (int, float))]
    if response_times:
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        print(f"平均响应时间: {avg_response_time:.2f}s")
        print(f"最大响应时间: {max_response_time:.2f}s")
        print(f"最小响应时间: {min_response_time:.2f}s")

    print(f"测试完成，总耗时: {test_end_time - test_start_time:.2f}s")

async def main():
    # 设置要测试的并发用户数
    user_counts = [100]
    rounds = 1

    for count in user_counts:
        for round_num in range(1, rounds + 1):
            print(f"\n--- 测试 {count} 个并发用户，轮次 {round_num} ---")
            await test_concurrent_users(num_users=count, queries_per_user=1, max_concurrent=100)

if __name__ == "__main__":
    asyncio.run(main())


</details>

### env1:
> vLLM 0.6.3
> torch 2.4.0
> transformers 4.45.2
#### test 2 times results:

-- Test 100 concurrent users, round 1 --
Average response time: 20.10s
Maximum response time: 35.49s
Minimum response time: 2.48s
Test completed, total time: 37.86s

-- Test 100 concurrent users, round 1 --
Average response time: 19.19s
Maximum response time: 34.13s
Minimum response time: 1.02s
Test completed, total time: 36.23s

### env2:
> vLLM 0.5.1
> torch 2.3.0
> transformers 4.42.4
#### test 3 times results:
-- Test 100 concurrent users, round 1 --
Average response time: 13.76s
Maximum response time: 23.72s
Minimum response time: 1.74s
Test completed, total time: 25.56s

-- Test 100 concurrent users, round 1 --
Average response time: 12.92s
Maximum response time: 22.47s
Minimum response time: 1.04s
Test completed, total time: 23.36s

-- Test 100 concurrent users, round 1 --
Average response time: 12.93s
Maximum response time: 22.80s
Minimum response time: 1.20s
Test completed, total time: 23.99s

Looks like it took a third more time. I found that because when I typed a single question, it didn't feel like it was taking the right time, maybe it has something to do with the transformers and torch versions?

### Model Input Dumps

**

### 🐛 Describe the bug

***

### Before submitting a new issue...

- [X] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @beimingxinghai 2024-10-29T06:44:42Z
+1，same issue for Qwen2ForCausalLM

## comment @souliot 2024-11-05T04:02:51Z
+1，same issue for Qwen2ForCausalLM

## comment @530154436 2024-11-16T07:50:41Z
+1, I'm experiencing the same issue while using Qwen2.5-7B-Instruct.

## comment @github-actions[bot] 2025-02-16T02:03:38Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2025-03-18T02:04:35Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!