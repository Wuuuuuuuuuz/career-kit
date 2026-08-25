"""数据根目录——用户数据的唯一落位来源。

所有用户数据（档案、知识库、缓存）默认存放在用户主目录下：
- 换工作目录启动不丢档案
- pip 安装后 site-packages 不可写也不影响使用
- 用户积累的知识库属于用户资产，不随包升级丢失

可用环境变量 CAREER_KIT_DATA_DIR 覆盖根目录（测试 / CI 场景）。
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_ROOT = Path(os.environ.get("CAREER_KIT_DATA_DIR", str(Path.home() / ".career-kit")))
PROFILE_DIR = DATA_ROOT
KNOWLEDGE_DIR = DATA_ROOT / "knowledge"
CACHE_DIR = DATA_ROOT / "cache"
