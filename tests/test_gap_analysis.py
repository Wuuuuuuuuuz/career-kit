"""差距分析功能测试——SOP 驱动模式。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8')

from src.models import CareerProfile
from src.tools.gap_analyzer import (
    build_gap_analysis_prompt,
    build_sop_analysis_prompt,
    format_gap_report,
    parse_gap_analysis,
)
from src.tools.profile import load_profile, merge_section, save_profile
from src.tools.sop_executor import execute_sop, load_sop
from src.tools.data_source import DataRouter, LocalKnowledgeSource, LLMKnowledgeSource


def test_sop_config_loading():
    """测试 SOP 配置文件加载。"""
    print("=" * 60)
    print("测试 1: SOP 配置文件加载")
    print("=" * 60)

    # 测试加载简历过筛 SOP
    resume_sop = load_sop("resume_screening")
    assert resume_sop["name"] == "简历过筛"
    assert len(resume_sop["steps"]) > 0
    step_ids = [s["id"] for s in resume_sop["steps"]]
    assert "build_persona" in step_ids
    assert "build_resume_advice" in step_ids
    print(f"[OK] 简历过筛 SOP 加载成功，共 {len(resume_sop['steps'])} 步")

    # 测试加载面试通过 SOP
    interview_sop = load_sop("interview_prep")
    assert interview_sop["name"] == "面试通过"
    assert len(interview_sop["steps"]) > 0
    step_ids = [s["id"] for s in interview_sop["steps"]]
    assert "search_interview_experiences" in step_ids
    assert "build_interview_advice" in step_ids
    print(f"[OK] 面试通过 SOP 加载成功，共 {len(interview_sop['steps'])} 步")

    print()


def test_sop_execution():
    """测试 SOP 执行（不含实际 LLM 调用）。"""
    print("=" * 60)
    print("测试 2: SOP 执行")
    print("=" * 60)

    user_have = {
        "skills": ["Python", "React"],
        "experience": "2年前端开发",
        "education": "双非本科",
    }
    user_want = {
        "target_role": "AI Agent 开发工程师",
        "target_company": "字节跳动",
        "timeline": "6个月",
    }

    # 执行简历过筛 SOP
    result = execute_sop("resume_screening", user_have, user_want)
    assert result["sop_name"] == "简历过筛"
    assert len(result["steps"]) > 0
    assert result["context"]["user_have"]  # 上下文应该有数据
    print(f"[OK] 简历过筛 SOP 执行成功，{len(result['steps'])} 步")

    # 检查每步有 prompt 或 data_source_query（或被跳过）
    for step in result["steps"]:
        has_output = step.get("prompt") or step.get("data_source_query") or step.get("skipped_reason")
        assert has_output, f"步骤 {step['id']} 没有输出"
    print("[OK] 每步都有输出（或被标记为跳过）")

    # 执行面试通过 SOP
    result2 = execute_sop("interview_prep", user_have, user_want)
    assert result2["sop_name"] == "面试通过"
    assert len(result2["steps"]) > 0
    print(f"[OK] 面试通过 SOP 执行成功，{len(result2['steps'])} 步")

    print()


def test_data_source():
    """测试数据源接口。"""
    print("=" * 60)
    print("测试 3: 数据源接口")
    print("=" * 60)

    # 测试本地知识源
    local = LocalKnowledgeSource()
    results = local.search("AI Agent 面试", "interview_experiences")
    print(f"[OK] 本地知识源搜索完成，结果数：{len(results)}")

    # 测试 LLM 兜底源
    llm = LLMKnowledgeSource()
    results = llm.search("test", "similar_profiles")
    assert len(results) == 1
    assert results[0]["fallback"] is True
    print("[OK] LLM 兜底源返回正确")

    # 测试路由器
    router = DataRouter()
    result = router.search("AI Agent", "interview_experiences")
    assert "results" in result
    assert "has_local" in result
    assert "fallback_to_llm" in result
    print(f"[OK] 路由器工作正常，has_local={result['has_local']}, fallback={result['fallback_to_llm']}")

    print()


def test_sop_with_retrieval():
    """测试带数据检索的 SOP 执行。"""
    print("=" * 60)
    print("测试 4: SOP + 数据检索")
    print("=" * 60)

    user_have = {"skills": ["Python"], "education": "双非本科"}
    user_want = {"target_role": "AI Agent 开发工程师"}

    result = execute_sop("resume_screening", user_have, user_want)

    # 检查有数据源配置的步骤
    data_steps = [s for s in result["steps"] if s.get("data_source_query") or s.get("skipped_reason")]
    assert len(data_steps) > 0
    print(f"[OK] 有 {len(data_steps)} 个步骤包含数据源配置")

    for step in data_steps:
        if step.get("data_source_query"):
            print(f"  - {step['name']}: query='{step['data_source_query'][:50]}...'")
        else:
            print(f"  - {step['name']}: {step['skipped_reason']}")

    print()


def test_build_sop_prompt():
    """测试 SOP 驱动的 prompt 构建。"""
    print("=" * 60)
    print("测试 5: SOP Prompt 构建")
    print("=" * 60)

    profile = CareerProfile()
    profile.have = {
        "skills": ["Python", "React"],
        "experience": "2年前端开发",
        "education": "双非本科",
    }
    profile.want = {
        "target_role": "AI Agent 开发工程师",
        "target_company": "字节跳动",
    }
    profile.target_jd = {
        "position": "AI Agent 开发工程师",
        "required_skills": ["LangGraph", "RAG", "FastAPI"],
    }

    prompt, metadata = build_sop_analysis_prompt(profile)

    # 检查 prompt 包含必要内容
    assert "Python" in prompt
    assert "AI Agent" in prompt
    assert "简历过筛" in prompt
    assert "面试通过" in prompt
    assert "JSON" in prompt
    print("[OK] prompt 包含所有必要内容")

    # 检查 metadata
    assert "resume_sop" in metadata
    assert "interview_sop" in metadata
    print(f"[OK] metadata 包含 {len(metadata['resume_sop']['steps'])} + {len(metadata['interview_sop']['steps'])} 步")

    print()


def test_parse_analysis():
    """测试 LLM 输出解析。"""
    print("=" * 60)
    print("测试 6: 解析 LLM 输出")
    print("=" * 60)

    llm_response = '''
    ```json
    {
        "match_score": 45,
        "match_level": "partial_match",
        "skill_gaps": [
            {"skill": "LangGraph", "current_level": "不了解", "required_level": "熟练", "priority": "high", "is_hidden": false, "how_to_improve": "学习官方文档"}
        ],
        "strengths": [
            {"area": "前端开发", "description": "2年经验", "resume_highlight": "强调全栈潜力", "interview_talk": "展示学习能力"}
        ],
        "resume_optimization": {
            "ats_keywords": ["Python", "AI", "Agent"],
            "highlight_projects": [
                {"project": "前端项目", "how_to_package": "强调 API 设计能力", "quantified_result": "性能提升 30%"}
            ],
            "missing_keywords": ["LangGraph", "RAG"],
            "resume_tips": ["补充 AI 相关项目"],
            "missing_experiences": [
                {"experience": "AI Agent 开发", "how_to_create": "做一个 RAG 项目"}
            ]
        },
        "interview_preparation": {
            "must_prepare": [
                {"topic": "LangChain 架构", "type": "八股", "priority": "high", "prepare_advice": "看官方文档", "estimated_time": "3天"}
            ],
            "project_deep_dive": [
                {"project": "前端项目", "likely_questions": ["性能优化怎么做的"], "key_points": ["具体数据"], "star_story": "S: 用户反馈慢 T: 优化 A: 用了xxx R: 快了30%"}
            ],
            "system_design_topics": [
                {"topic": "设计一个 Agent 系统", "framework": "需求→架构→组件→权衡"}
            ],
            "behavioral_questions": [
                {"question": "遇到过什么技术难题", "story_template": "用前端性能优化的故事"}
            ],
            "study_plan": {
                "week_1": ["LangChain 基础"],
                "week_2": ["RAG 实战"]
            }
        },
        "priority_actions": [
            {"action": "学习 LangGraph", "timeline": "2个月", "impact": "高", "difficulty": "medium"}
        ],
        "market_context": "AI Agent 岗位需求增长迅速"
    }
    ```
    '''

    result = parse_gap_analysis(llm_response)
    assert result["match_score"] == 45
    assert result["match_level"] == "partial_match"
    assert len(result["skill_gaps"]) == 1
    assert result["resume_optimization"]["ats_keywords"] == ["Python", "AI", "Agent"]
    assert len(result["interview_preparation"]["must_prepare"]) == 1
    assert result["interview_preparation"]["study_plan"]["week_1"] == ["LangChain 基础"]
    print("[OK] 标准 JSON 解析成功")

    # 测试解析失败
    result3 = parse_gap_analysis("这不是 JSON")
    assert "raw_analysis" in result3
    assert result3["match_score"] == 0
    print("[OK] 解析失败时返回原始文本")

    print()


def test_format_report():
    """测试报告格式化。"""
    print("=" * 60)
    print("测试 7: 格式化差距报告")
    print("=" * 60)

    gap = {
        "match_score": 45,
        "match_level": "partial_match",
        "strengths": [
            {"area": "前端开发", "description": "2年经验", "resume_highlight": "强调全栈潜力", "interview_talk": "展示学习能力"},
        ],
        "resume_optimization": {
            "ats_keywords": ["Python", "AI", "Agent"],
            "missing_keywords": ["LangGraph", "RAG"],
            "highlight_projects": [
                {"project": "前端项目", "how_to_package": "强调 API 设计能力", "quantified_result": "性能提升 30%"}
            ],
            "resume_tips": ["补充 AI 相关项目"],
            "missing_experiences": [
                {"experience": "AI Agent 开发", "how_to_create": "做一个 RAG 项目"}
            ],
        },
        "interview_preparation": {
            "must_prepare": [
                {"topic": "LangChain 架构", "type": "八股", "priority": "high", "prepare_advice": "看官方文档", "estimated_time": "3天"}
            ],
            "project_deep_dive": [
                {"project": "前端项目", "likely_questions": ["性能优化怎么做的"], "key_points": ["具体数据"], "star_story": "S:用户反馈慢"}
            ],
            "system_design_topics": [
                {"topic": "设计一个 Agent 系统", "framework": "需求→架构→组件→权衡"}
            ],
            "behavioral_questions": [
                {"question": "遇到过什么技术难题", "story_template": "用前端性能优化的故事"}
            ],
            "study_plan": {
                "week_1": ["LangChain 基础"],
                "week_2": ["RAG 实战"],
            },
        },
        "skill_gaps": [
            {"skill": "LangGraph", "current_level": "不了解", "required_level": "熟练", "priority": "high", "is_hidden": False},
            {"skill": "系统设计", "current_level": "初级", "required_level": "能独立设计", "priority": "high", "is_hidden": True},
        ],
        "priority_actions": [
            {"action": "学习 LangGraph", "timeline": "2个月", "impact": "高", "difficulty": "medium"},
        ],
        "market_context": "AI Agent 岗位需求增长迅速",
    }

    report = format_gap_report(gap)

    assert "45/100" in report
    assert "简历优化" in report
    assert "面试准备" in report
    assert "ATS 关键词" in report
    assert "LangGraph" in report
    assert "显性要求" in report
    assert "隐性要求" in report
    assert "学习计划" in report
    assert "STAR" in report
    print("[OK] 报告格式化成功")

    print(f"\n报告预览:\n{'-' * 40}")
    print(report[:1500])
    print(f"{'-' * 40}\n")


def test_mcp_tools():
    """测试 MCP tools 注册。"""
    print("=" * 60)
    print("测试 8: MCP Tools 注册")
    print("=" * 60)

    from src.server import mcp

    tools = [t.name for t in mcp._tool_manager.list_tools()]

    assert "import_jd" in tools
    assert "analyze_gaps" in tools
    assert "save_gap_analysis" in tools
    print("[OK] import_jd 已注册")
    print("[OK] analyze_gaps 已注册")
    print("[OK] save_gap_analysis 已注册")

    print()


def test_full_flow():
    """测试完整流程（使用临时目录）。"""
    print("=" * 60)
    print("测试 9: 完整流程模拟")
    print("=" * 60)

    import src.tools.profile as profile_module
    original_dir = profile_module.PROFILE_DIR

    with tempfile.TemporaryDirectory() as tmpdir:
        profile_module.PROFILE_DIR = Path(tmpdir)

        # 1. 创建档案
        profile = CareerProfile()
        profile.have = {"skills": ["Python", "React"], "experience": "2年", "education": "双非本科"}
        profile.want = {"target_role": "AI Agent 开发", "target_company": "字节跳动"}
        save_profile(profile, "test")
        print("[OK] 创建档案")

        # 2. 导入 JD
        profile = load_profile("test")
        profile.target_jd = {
            "position": "AI Agent 开发工程师",
            "required_skills": ["LangGraph", "RAG", "FastAPI"],
        }
        profile.touch()
        save_profile(profile, "test")
        print("[OK] 导入 JD")

        # 3. SOP 驱动分析
        profile = load_profile("test")
        prompt, metadata = build_sop_analysis_prompt(profile)
        assert "LangGraph" in prompt or "AI Agent" in prompt
        assert metadata["resume_sop"]["name"] == "简历过筛"
        assert metadata["interview_sop"]["name"] == "面试通过"
        print("[OK] SOP 分析构建成功")

        # 4. 模拟 LLM 输出并保存
        gap_data = {
            "skill_gaps": [{"skill": "LangGraph", "priority": "high", "is_hidden": False}],
            "match_score": 50,
            "resume_optimization": {"ats_keywords": ["Python", "AI"]},
            "interview_preparation": {"must_prepare": [{"topic": "LangChain", "type": "八股", "priority": "high"}]},
            "market_context": "测试市场",
        }
        profile.gap = gap_data
        profile.touch()
        save_profile(profile, "test")
        print("[OK] 保存差距分析")

        # 5. 验证最终状态
        final = load_profile("test")
        assert final.gap["match_score"] == 50
        assert final.gap["resume_optimization"]["ats_keywords"] == ["Python", "AI"]
        print("[OK] 最终状态验证通过")

        profile_module.PROFILE_DIR = original_dir

    print()


def main():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("差距分析功能测试套件（SOP 驱动）")
    print("=" * 60 + "\n")

    tests = [
        test_sop_config_loading,
        test_sop_execution,
        test_data_source,
        test_sop_with_retrieval,
        test_build_sop_prompt,
        test_parse_analysis,
        test_format_report,
        test_mcp_tools,
        test_full_flow,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            print()

    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
