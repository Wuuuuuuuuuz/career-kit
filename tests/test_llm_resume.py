"""LLM 简历解析端到端测试——用真实简历驱动完整流程。"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# 修复 Windows 终端中文显示
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 配置
PYTHON_EXE = r"C:\Users\16070\AppData\Local\Programs\Python\Python312\python.exe"
DEFAULT_BASE_URL = "https://token-plan-cn.xiaomimimo.com/anthropic"
DEFAULT_API_KEY = "tp-cvwuv6lgvskloafr4wjgdc6j8wgjgufmqyywdkjgmzwdyggk"
TEST_DIR = Path(__file__).parent.parent / "dev" / "test"


def get_anthropic_client() -> anthropic.Anthropic:
    """创建 Anthropic 客户端。"""
    base_url = os.environ.get("ANTHROPIC_BASE_URL", DEFAULT_BASE_URL)
    api_key = os.environ.get("ANTHROPIC_API_KEY", DEFAULT_API_KEY)
    return anthropic.Anthropic(api_key=api_key, base_url=base_url)


def extract_tool_calls(response) -> list[dict]:
    """从 Claude 响应中提取 tool 调用。"""
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

        # 将 assistant 的响应添加到历史
        messages.append({"role": "assistant", "content": response.content})

        # 执行所有 tool 调用
        tool_results = []
        for tc in tool_calls:
            print(f"    [Tool #{iteration}] {tc['name']}({json.dumps(tc['input'], ensure_ascii=False)[:120]})")

            result = await session.call_tool(tc["name"], tc["input"])
            result_text = result.content[0].text
            print(f"    [Result] {result_text[:150]}...")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc["id"],
                "content": result_text,
            })

        # 将 tool 结果添加到历史
        messages.append({"role": "user", "content": tool_results})

        # 继续对话
        response = client.messages.create(
            model="mimo-v2.5",
            max_tokens=2048,
            system=system_prompt,
            tools=claude_tools,
            messages=messages,
        )

    # 输出最终回复
    final_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_text += block.text

    messages.append({"role": "assistant", "content": response.content})
    return final_text


async def test_with_resume(resume_path: str, format_name: str):
    """用指定简历文件测试完整流程。"""
    print(f"\n{'=' * 60}")
    print(f"测试: {format_name} 格式简历")
    print(f"文件: {resume_path}")
    print(f"{'=' * 60}")

    # 启动 MCP 服务器
    server_params = StdioServerParameters(
        command=PYTHON_EXE,
        args=["-m", "src.server"],
        cwd=str(Path(__file__).parent.parent),
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # 获取工具列表
            tools_response = await session.list_tools()
            claude_tools = []
            for tool in tools_response.tools:
                claude_tools.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                })

            client = get_anthropic_client()
            messages = []

            system_prompt = """你是 Career Kit 的 AI 助手，帮助用户进行职业规划。

工作流程：
1. 用户可能直接给你简历文件路径，调用 parse_resume 解析
2. 解析后，调用 intake 将信息填入 who 和 have section
3. 继续追问用户的目标（want section）
4. 最后调用 finalize_profile 确认档案

请用中文回复，保持简洁专业。"""

            # 第一轮：开始会话
            print("\n[轮次 1] 启动会话...")
            messages.append({"role": "user", "content": "你好，我想做职业规划，这是我的简历"})
            final = await run_conversation(session, client, messages, claude_tools, system_prompt)
            print(f"\n[AI] {final[:200]}...")

            # 第二轮：提供简历路径
            print(f"\n[轮次 2] 提供简历 ({format_name})...")
            messages.append({"role": "user", "content": f"简历文件路径: {resume_path}"})
            final = await run_conversation(session, client, messages, claude_tools, system_prompt)
            print(f"\n[AI] {final[:300]}...")

            # 第三轮：补充目标信息
            print("\n[轮次 3] 补充目标...")
            messages.append({"role": "user", "content": "我想找 AI Agent 方向的实习，最好是大厂，6个月内"})
            final = await run_conversation(session, client, messages, claude_tools, system_prompt)
            print(f"\n[AI] {final[:300]}...")

    print(f"\n[完成] {format_name} 格式测试通过!")
    return True


async def main():
    """运行所有格式的测试。"""
    print("\n" + "=" * 60)
    print("LLM + 真实简历端到端测试")
    print("=" * 60)

    test_cases = [
        (str(TEST_DIR / "AI.md"), "Markdown"),
    ]

    for resume_path, format_name in test_cases:
        if not Path(resume_path).exists():
            print(f"[SKIP] {resume_path} 不存在")
            continue

        try:
            await test_with_resume(resume_path, format_name)
        except Exception as e:
            print(f"[FAIL] {format_name}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
