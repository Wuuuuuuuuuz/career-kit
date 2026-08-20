"""企业 JD 数据源基类——接口规范。

实现者只需：
1. 继承 CompanyScraper
2. 实现 search() 和 get_detail()
3. 在 config.yaml 中注册
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CompanyScraper(ABC):
    """企业 JD 数据源抽象基类。

    接口规范：
    - search(**kwargs) → list[dict]：搜索岗位，参数由各实现自定义
    - get_detail(url) → dict：获取岗位详情

    返回字段规范（建议，多了不限，少了不强制）：

    search 返回：
        {
            "title": "岗位名称",
            "url": "岗位链接",
            "company": "公司名称",
            "location": "工作地点",
            "department": "部门（可选）",
            "summary": "岗位摘要",
        }

    get_detail 返回：
        {
            "title": "岗位名称",
            "company": "公司名称",
            "location": "工作地点",
            "salary": "薪资范围（可选）",
            "description": "岗位描述全文",
            "requirements": "任职要求全文",
            "benefits": "福利待遇（可选）",
        }
    """

    @abstractmethod
    def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        """搜索岗位。

        Args:
            **kwargs: 搜索参数，由各实现自定义。
                常见参数：keyword, city, department, job_type 等
                具体支持哪些参数见 config.yaml 中的 params 定义。

        Returns:
            岗位列表，每项为一个 dict。
        """

    @abstractmethod
    def get_detail(self, url: str) -> dict[str, Any]:
        """获取岗位详情。

        Args:
            url: 岗位详情页 URL

        Returns:
            岗位详情 dict。
        """
