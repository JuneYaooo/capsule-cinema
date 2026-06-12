from typing import Any, Optional, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
import requests
import os
from dotenv import load_dotenv
from src.logger import get_logger

load_dotenv()

# 初始化日志记录器
logger = get_logger("searxng_web_search")

class SearxngWebSearchListToolSchema(BaseModel):
    """Input for SearxngWebSearchListTool."""
    search_query: str = Field(
        ..., description="Mandatory search query you want to use to search the internet"
    )
    search_type: str = Field(
        default="general",
        description="Type of search to perform: 'general', 'image', or 'news'"
    )

class SearxngWebSearchListTool(BaseTool):
    name: str = "Search the internet using SearxNG"
    description: str = (
        "A tool that can be used to search the internet with SearxNG and return a list of results."
    )
    args_schema: Type[BaseModel] = SearxngWebSearchListToolSchema
    base_url: Optional[str] = None
    timeout: int = 5

    def __init__(self, base_url: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.base_url = base_url or os.getenv('SEARXNG_URL')
        logger.info(f"初始化SearxngWebSearchListTool，基础URL: {self.base_url}")

    def _run(
        self,
        search_query: str,
        search_type: str = "general",
    ) -> Any:

        logger.info(f"执行搜索，查询: {search_query}，类型: {search_type}")
        
        if search_type == "general":
            results = self.search_general(search_query)
        elif search_type == "image":
            results = self.search_image(search_query)
        elif search_type == "news":
            results = self.search_news(search_query)
        else:
            error_msg = f"无效的搜索类型: {search_type}，请选择 'general'、'image' 或 'news'"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"搜索完成，获取到 {len(results)} 条结果")
        return results

    def search_general(self, query, time_range='year', page=1, max_results=20):
        logger.info(f"执行通用搜索，查询: {query}，时间范围: {time_range}")
        params = {
            'q': query,
            'categories': 'general',
            'engines': 'google,bing,duckduckgo',
            'language': 'en',
            'time_range': time_range,
            'format': 'json',
            'page': page
        }
        try:
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                results = response.json().get('results', [])
                logger.info(f"通用搜索成功，获取到 {len(results)} 条结果")
                return results[:max_results]
            else:
                logger.error(f"通用搜索请求失败，状态码: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"通用搜索异常: {str(e)}")
            return []

    def search_image(self, query, time_range='week', page=1, max_results=20):
        logger.info(f"执行图片搜索，查询: {query}，时间范围: {time_range}")
        params = {
            'q': query,
            'categories': 'images',
            'engines': 'google,bing',
            'language': 'en',
            'time_range': time_range,
            'format': 'json',
            'page': page
        }
        try:
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                results = response.json().get('results', [])
                filtered_results = [item for item in results if item.get('img_src')]
                logger.info(f"图片搜索成功，获取到 {len(filtered_results)} 张图片")
                return filtered_results[:max_results]
            else:
                logger.error(f"图片搜索请求失败，状态码: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"图片搜索异常: {str(e)}")
            return []

    def search_news(self, query, time_range='week', page=1, max_results=15):
        logger.info(f"执行新闻搜索，查询: {query}，时间范围: {time_range}")
        params = {
            'q': query,
            'categories': 'news',
            'engines': 'google,bing',
            'language': 'en',
            'time_range': time_range,
            'format': 'json',
            'page': page
        }
        try:
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                results = response.json().get('results', [])
                logger.info(f"新闻搜索成功，获取到 {len(results)} 条新闻")
                return results[:max_results]
            else:
                logger.error(f"新闻搜索请求失败，状态码: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"新闻搜索异常: {str(e)}")
            return []
