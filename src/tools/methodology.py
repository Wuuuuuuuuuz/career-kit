"""方法论加载器——读取方法论 YAML，返回结构化上下文给 LLM。

替代旧的 sop_executor.py。只负责加载和组装，不构建 prompt、不执行搜索。
LLM agent 拿到上下文后自主决定执行路径。
"""

from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml

from ..models import CareerProfile

METHODOLOGY_DIR = Path(__file__).parent.parent.parent / "sop"


def load_methodology(name: str) -> dict[str, Any]:
    """加载 sop/{name}.yaml 方法论配置。

    Args:
        name: YAML 文件名（不含扩展名），如 "resume_screening"

    Returns:
        解析后的 methodology dict

    Raises:
        FileNotFoundError: YAML 文件不存在
    """
    sop_file = METHODOLOGY_DIR / f"{name}.yaml"
    if not sop_file.exists():
        raise FileNotFoundError(f"方法论配置不存在：{sop_file}")
    with open(sop_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # 校验：必须有 methodology 字段
    if "methodology" not in data:
        raise ValueError(f"方法论配置缺少 methodology 字段：{sop_file}")
    return data


def build_methodology_context(
    methodology_name: str,
    profile: CareerProfile,
) -> dict[str, Any]:
    """构建返回给 LLM 的结构化上下文。

    Returns:
        {
            "methodology": { name, description, principles, phases, output_schema },
            "profile": { have, want, target_jd, gap },
        }
    """
    data = load_methodology(methodology_name)
    methodology = data["methodology"]
    methodology["name"] = data.get("name", methodology_name)
    methodology["version"] = data.get("version", "1.0")
    methodology["description"] = data.get("description", "")

    return {
        "methodology": methodology,
        "profile": {
            "have": profile.have or {},
            "want": profile.want or {},
            "target_jd": profile.target_jd or {},
            "gap": profile.gap or {},
        },
    }
