"""企业 JD 爬虫框架——社区驱动的企业招聘信息源。

每个企业一个目录，实现 CompanyScraper 接口即可注册。
"""

from .base import CompanyScraper
from .loader import get_scraper, list_scrapers, search_company_jobs, get_job_detail

__all__ = [
    "CompanyScraper",
    "get_scraper",
    "list_scrapers",
    "search_company_jobs",
    "get_job_detail",
]
