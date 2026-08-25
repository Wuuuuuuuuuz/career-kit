"""差距分析功能测试——SOP 驱动模式。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8')

from src.models import CareerProfile
from src.tools.gap_analyzer import format_gap_report
from src.tools.methodology import build_methodology_context, load_methodology
from src.tools.knowledge_search import search_knowledge
from src.tools.profile import load_profile, merge_section, save_profile


def test_sop_config_loading():
    """测试方法论配置文件加载。"""
    print("=" * 60)
    print("测试 1: 方法论配置加载")
    print("=" * 60)

    # 测试加载简历过筛方法论
    resume_m = load_methodology("resume_screening")
    assert resume_m["name"] == "简历过筛"
    phase_ids = [p["id"] for p in resume_m["methodology"]["phases"]]
    assert "gather_data" in phase_ids
    assert "generate_advice" in phase_ids
    print(f"[OK] 简历过筛方法论加载成功，共 {len(phase_ids)} 阶段")

    # 测试加载面试通过方法论
    interview_m = load_methodology("interview_prep")
    assert interview_m["name"] == "面试通过"
    phase_ids = [p["id"] for p in interview_m["methodology"]["phases"]]
    assert "analyze_interview" in phase_ids
    assert "generate_preparation" in phase_ids
    print(f"[OK] 面试通过方法论加载成功，共 {len(phase_ids)} 阶段")

    print()


def test_sop_execution():
    """测试方法论上下文构建（替代旧 SOP 执行）。"""
    print("=" * 60)
    print("测试 2: 方法论上下文构建")
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
        "timeline": "6个月",
    }

    # 构建简历过筛上下文
    ctx = build_methodology_context("resume_screening", profile)
    assert ctx["methodology"]
    assert ctx["profile"]["have"]["skills"] == ["Python", "React"]
    assert ctx["methodology"]["name"] == "简历过筛"
    print("[OK] 简历过筛上下文构建成功")

    # 构建面试通过上下文
    ctx2 = build_methodology_context("interview_prep", profile)
    assert ctx2["methodology"]["name"] == "面试通过"
    assert ctx2["profile"]["want"]["target_role"] == "AI Agent 开发工程师"
    print("[OK] 面试通过上下文构建成功")

    print()


def test_knowledge_search():
    """测试知识库检索。"""
    print("=" * 60)
    print("测试 3: 知识库检索")
    print("=" * 60)

    result = search_knowledge("AI Agent 面试")
    assert "results" in result
    assert "count" in result
    print(f"[OK] 知识库检索完成，结果数：{result['count']}")

    # 空查询不崩溃
    result2 = search_knowledge("")
    assert "results" in result2
    print("[OK] 空查询安全处理")

    print()


def test_sop_with_retrieval():
    """测试带数据检索的 SOP 执行。"""
    print("=" * 60)
    print("测试 4: 方法论数据需求声明")
    print("=" * 60)

    m = load_methodology("resume_screening")
    phases = m["methodology"]["phases"]

    # 检查有数据需求的阶段
    data_phases = [p for p in phases if p.get("data_needs")]
    assert len(data_phases) > 0
    print(f"[OK] 有 {len(data_phases)} 个阶段包含数据需求")

    for phase in data_phases:
        needs = phase.get("data_needs", [])
        print(f"  - {phase['id']}: {len(needs)} 个数据需求")

    print()


def test_build_sop_prompt():
    """测试方法论上下文构建。"""
    print("=" * 60)
    print("测试 5: 方法论上下文构建")
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

    from src.tools.methodology import build_methodology_context

    ctx1 = build_methodology_context("resume_screening", profile)
    ctx2 = build_methodology_context("interview_prep", profile)

    # 检查方法论内容
    assert ctx1["methodology"]
    assert ctx2["methodology"]
    assert "profile" in ctx1
    print("[OK] 方法论上下文包含所有必要内容")

    prompt = json.dumps(ctx1["methodology"], ensure_ascii=False, default=str) + json.dumps(
        ctx2["methodology"], ensure_ascii=False, default=str
    )
    assert "Python" in prompt or "简历" in prompt
    print("[OK] 方法论内容校验通过")

    print()


def test_parse_analysis():
    """测试 LLM 输出解析（server 层统一走 JSON 解析，code block 由 _parse_json_param 前置处理）。"""
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

    result = json.loads(llm_response.split("```json")[1].split("```")[0].strip())
    assert result["match_score"] == 45
    assert result["match_level"] == "partial_match"
    assert len(result["skill_gaps"]) == 1
    assert result["resume_optimization"]["ats_keywords"] == ["Python", "AI", "Agent"]
    assert len(result["interview_preparation"]["must_prepare"]) == 1
    assert result["interview_preparation"]["study_plan"]["week_1"] == ["LangChain 基础"]
    print("[OK] 标准 JSON 解析成功")

    # 测试解析失败路径由 server 层 error_response 兜底
    from src.server import _parse_json_param
    try:
        _parse_json_param("这不是 JSON", "差距分析")
        raise AssertionError("应当抛出 InvalidJsonError")
    except Exception as exc:
        assert type(exc).__name__ == "InvalidJsonError"
    print("[OK] 非法输入被 server 层统一拒绝")

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

        # 3. 方法论驱动分析
        profile = load_profile("test")
        from src.tools.methodology import build_methodology_context
        ctx1 = build_methodology_context("resume_screening", profile)
        ctx2 = build_methodology_context("interview_prep", profile)
        assert ctx1["methodology"]
        assert ctx2["methodology"]
        print("[OK] 方法论上下文构建成功")

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
        test_knowledge_search,
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
