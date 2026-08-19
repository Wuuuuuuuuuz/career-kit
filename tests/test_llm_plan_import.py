"""LLM 计划导入端到端测试。"""

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
TEST_PLAN_FILE = Path(__file__).parent.parent / "dev" / "test" / "计划1.md"


def get_anthropic_client() -> anthropic.Anthropic:
    """创建 Anthropic 客户端。"""
    base_url = os.environ.get("ANTHROPIC_BASE_URL", DEFAULT_BASE_URL)
    api_key = os.environ.get("ANTHROPIC_API_KEY", DEFAULT_API_KEY)
    return anthropic.Anthropic(api_key=api_key, base_url=base_url)


def extract_tool_calls(response) -> list[dict]:
    """从响应中提取 tool 调用。"""
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
    """运行一轮对话，处理所有 tool 调用。"""
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
            print(f"    [Tool #{iteration}] {tc['name']}({json.dumps(tc['input'], ensure_ascii=False)[:120]})")

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


async def test_plan_import():
    """测试计划导入流程。"""
    print("=" * 60)
    print("LLM 计划导入端到端测试")
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
            claude_tools = []
            for tool in tools_response.tools:
                claude_tools.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                })
            print(f"[OK] 加载 {len(claude_tools)} 个工具")

            client = get_anthropic_client()
            messages = []

            system_prompt = """你是 Career Kit 的 AI 助手。

工作流程：
1. 用户可能要求导入计划文件，调用 import_plan 解析
2. 如果已有计划，调用 compare_plan_versions 对比
3. 根据用户选择调用 replace_plan 或 merge_plan
4. 可以调用 list_plan_versions 查看版本历史

请用中文回复。"""

            # 第一轮：开始会话并导入计划
            print("\n[轮次 1] 导入计划文件...")
            messages.append({
                "role": "user",
                "content": f"我想导入已有的职业规划，文件路径: {TEST_PLAN_FILE}"
            })
            final = await run_conversation(session, client, messages, claude_tools, system_prompt)
            print(f"\n[AI] {final[:400]}...")

            # 第二轮：选择替换
            print("\n[轮次 2] 选择替换为新计划...")
            messages.append({
                "role": "user",
                "content": "我想完全替换为新计划"
            })
            final = await run_conversation(session, client, messages, claude_tools, system_prompt)
            print(f"\n[AI] {final[:400]}...")

            # 第三轮：查看版本历史
            print("\n[轮次 3] 查看版本历史...")
            messages.append({
                "role": "user",
                "content": "查看计划版本历史"
            })
            final = await run_conversation(session, client, messages, claude_tools, system_prompt)
            print(f"\n[AI] {final[:400]}...")

    print("\n" + "=" * 60)
    print("计划导入测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_plan_import())
