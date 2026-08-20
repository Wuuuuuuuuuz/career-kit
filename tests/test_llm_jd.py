"""LLM JD 导入 + 差距分析端到端测试。"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 配置
PYTHON_EXE = r"C:\Users\16070\AppData\Local\Programs\Python\Python312\python.exe"
DEFAULT_BASE_URL = "https://token-plan-cn.xiaomimimo.com/anthropic"
DEFAULT_API_KEY = "tp-cvwuv6lgvskloafr4wjgdc6j8wgjgufmqyywdkjgmzwdyggk"
JD_FILE = Path(__file__).parent.parent / "dev" / "test" / "JD1.md"
RESUME_FILE = Path(__file__).parent.parent / "dev" / "test" / "AI.md"


def get_anthropic_client() -> anthropic.Anthropic:
    base_url = os.environ.get("ANTHROPIC_BASE_URL", DEFAULT_BASE_URL)
    api_key = os.environ.get("ANTHROPIC_API_KEY", DEFAULT_API_KEY)
    return anthropic.Anthropic(api_key=api_key, base_url=base_url)


def extract_tool_calls(response) -> list[dict]:
    tool_calls = []
    for block in response.content:
        if block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return tool_calls


async def run_conversation(session, client, messages, claude_tools, system_prompt):
    response = client.messages.create(
        model="mimo-v2.5",
        max_tokens=2048,
        system=system_prompt,
        tools=claude_tools,
        messages=messages,
    )

    iteration = 0
    while response.stop_reason == "tool_use":
        iteration += 1
        tool_calls = extract_tool_calls(response)
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tc in tool_calls:
            print(f"    [Tool #{iteration}] {tc['name']}({json.dumps(tc['input'], ensure_ascii=False)[:150]})")
            result = await session.call_tool(tc["name"], tc["input"])
            result_text = result.content[0].text
            print(f"    [Result] {result_text[:200]}...")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc["id"],
                "content": result_text,
            })

        messages.append({"role": "user", "content": tool_results})
        response = client.messages.create(
            model="mimo-v2.5",
            max_tokens=2048,
            system=system_prompt,
            tools=claude_tools,
            messages=messages,
        )

    final_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_text += block.text
    messages.append({"role": "assistant", "content": response.content})
    return final_text


async def test_jd_import():
    """测试 JD 导入 + 差距分析。"""
    print("=" * 60)
    print("JD 导入 + 差距分析端到端测试")
    print("=" * 60)

    server_params = StdioServerParameters(
        command=PYTHON_EXE,
        args=["-m", "src.server"],
        cwd=str(Path(__file__).parent.parent),
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools_response = await session.list_tools()
            claude_tools = [{
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema,
            } for t in tools_response.tools]
            print(f"[OK] 加载 {len(claude_tools)} 个工具\n")

            client = get_anthropic_client()
            messages = []

            system_prompt = """你是 Career Kit 的 AI 助手。

工作流程：
1. 解析简历 → intake 填充 who/have
2. 解析 JD → import_jd 导入
3. 调用 analyze_gaps 进行差距分析
4. 调用 save_gap_analysis 保存结果

请用中文回复。"""

            # 第一轮：解析简历
            print("[轮次 1] 解析简历...")
            messages.append({
                "role": "user",
                "content": f"这是我的简历：{RESUME_FILE}"
            })
            final = await run_conversation(session, client, messages, claude_tools, system_prompt)
            print(f"\n[AI] {final[:200]}...\n")

            # 第二轮：导入 JD
            print("[轮次 2] 导入 JD...")
            jd_text = JD_FILE.read_text(encoding="utf-8")
            messages.append({
                "role": "user",
                "content": f"我想应聘这个岗位，请帮我分析差距：\n\n{jd_text}"
            })
            final = await run_conversation(session, client, messages, claude_tools, system_prompt)
            print(f"\n[AI] {final[:500]}...\n")

            # 第三轮：确认分析
            print("[轮次 3] 确认分析...")
            messages.append({
                "role": "user",
                "content": "请完成差距分析并给出建议"
            })
            final = await run_conversation(session, client, messages, claude_tools, system_prompt)
            print(f"\n[AI] {final[:800]}...\n")

    print("=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_jd_import())
