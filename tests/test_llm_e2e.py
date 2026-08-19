"""LLM 端到端测试——用真实 LLM 驱动 MCP 工具调用。"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 默认配置（可通过环境变量覆盖）
DEFAULT_BASE_URL = "https://token-plan-cn.xiaomimimo.com/anthropic"
DEFAULT_API_KEY = "tp-cvwuv6lgvskloafr4wjgdc6j8wgjgufmqyywdkjgmzwdyggk"


def get_anthropic_client() -> anthropic.Anthropic:
    """创建 Anthropic 客户端，支持自定义 endpoint。"""
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


PYTHON_EXE = r"C:\Users\16070\AppData\Local\Programs\Python\Python312\python.exe"


async def test_llm_e2e():
    """用真实 LLM 驱动完整的建档流程。"""
    print("=" * 60)
    print("LLM 端到端测试")
    print("=" * 60)

    # 启动 MCP 服务器
    server_params = StdioServerParameters(
        command=PYTHON_EXE,
        args=["-m", "src.server"],
        cwd=str(Path(__file__).parent.parent),
    )

    print("\n[1] 启动 MCP 服务器...")
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("[OK] 服务器连接成功")

            # 获取工具列表并转换为 Claude 格式
            tools_response = await session.list_tools()
            claude_tools = []
            for tool in tools_response.tools:
                claude_tools.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                })
            print(f"[OK] 加载 {len(claude_tools)} 个工具")

            # 创建 Anthropic 客户端
            client = get_anthropic_client()

            # 对话历史
            messages = []

            # 系统提示
            system_prompt = """你是 Career Kit 的 AI 助手。你的任务是帮助用户进行职业规划。

当用户开始对话时，你应该：
1. 调用 start_session 获取欢迎信息
2. 根据用户输入，调用相应的工具

请用中文回复。"""

            # 模拟用户对话
            test_messages = [
                "你好，我想做职业规划",
                "我是前端工程师，3年经验，想转 AI 方向",
            ]

            print("\n[2] 开始 LLM 对话测试...\n")

            for i, user_msg in enumerate(test_messages, 1):
                print(f"--- 第 {i} 轮 ---")
                print(f"用户: {user_msg}")

                messages.append({"role": "user", "content": user_msg})

                # 调用 Claude
                response = client.messages.create(
                    model="mimo-v2.5",
                    max_tokens=1024,
                    system=system_prompt,
                    tools=claude_tools,
                    messages=messages,
                )

                # 处理响应和 tool 调用
                iteration = 0
                while response.stop_reason == "tool_use":
                    iteration += 1
                    tool_calls = extract_tool_calls(response)

                    # 将 assistant 的响应添加到历史
                    messages.append({"role": "assistant", "content": response.content})

                    # 执行所有 tool 调用
                    tool_results = []
                    for tc in tool_calls:
                        print(f"  [Tool Call #{iteration}] {tc['name']}({json.dumps(tc['input'], ensure_ascii=False)[:100]})")

                        result = await session.call_tool(tc["name"], tc["input"])
                        result_text = result.content[0].text
                        print(f"  [Tool Result] {result_text[:150]}...")

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
                        max_tokens=1024,
                        system=system_prompt,
                        tools=claude_tools,
                        messages=messages,
                    )

                # 输出最终回复
                final_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text += block.text

                print(f"AI: {final_text[:300]}...")
                messages.append({"role": "assistant", "content": response.content})
                print()

    print("=" * 60)
    print("LLM 端到端测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_llm_e2e())
