from typing import Any, Type, List, Dict
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from bs4 import BeautifulSoup
import trafilatura
import requests
import html2text
from concurrent.futures import ThreadPoolExecutor
import time
import os
import random
from src.logger import get_logger

# 初始化日志记录器
logger = get_logger("extract_web_content")

class ExtractWebContentToolSchema(BaseModel):
    """Input for ExtractWebContentTool."""
    url: str = Field(
        ..., description="URL of the webpage to extract content from"
    )
    title: str = Field(
        ..., description="Title of the webpage to extract content from, can be empty"
    )

class ExtractWebContentTool(BaseTool):
    name: str = "Extract content from a webpage"
    description: str = (
        "A tool that can be used to extract content from a given URL."
    )
    args_schema: Type[BaseModel] = ExtractWebContentToolSchema
    timeout: int = 5

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("初始化ExtractWebContentTool")

    def _run(
        self,
        url: str,
        title: str,
    ) -> Any:
        logger.info(f"开始从URL提取内容: {url}")
        start_time = time.time()
        result = self.extract_content(url, title)
        end_time = time.time()
        logger.info(f"内容提取完成，耗时: {end_time - start_time:.2f}秒")
        return result

    def extract_content(self, url, title):
        try:
            start_time = time.time()
            content = self.extract_text(url)
            end_time = time.time()
            logger.info(f"成功从 {url} 提取内容，耗时: {end_time - start_time:.2f}秒")
            return {"url": url, "title": title, "content": content}
        except Exception as e:
            logger.error(f"从 {url} 提取内容失败: {str(e)}")
            return {"url": url, "title": title, "content": ""}

    def extract_text(self, url):
        methods = [
            self.extract_content_firecrawl,
            self.extract_text_html2text,
            self.extract_content_trafilatura,
            self.extract_content_beautifulsoup
        ]

        for method in methods:
            try:
                logger.info(f"尝试使用 {method.__name__} 提取内容")
                start_time = time.time()
                text = method(url)
                end_time = time.time()
                if text and len(text) > 150:
                    logger.info(f"使用 {method.__name__} 成功提取内容，耗时: {end_time - start_time:.2f}秒")
                    return text
            except Exception as e:
                logger.error(f"{method.__name__} 提取错误: {str(e)}")

        logger.error("所有提取方法都失败")
        return ""

    def extract_content_firecrawl(self, url):
        try:
            start_time = time.time()
            
            # Get token from environment variable and randomly select one
            token_string = os.environ.get("FIRECRAWL_API_TOKEN")
            base_url = os.environ.get("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev/v1")
            
            if not token_string:
                logger.error("环境变量中未设置FIRECRAWL_API_TOKEN")
                return ""
            
            # Split tokens by comma and randomly select one
            tokens = [token.strip() for token in token_string.split(",")]
            token = random.choice(tokens)
            logger.info(f"随机选择了第 {tokens.index(token) + 1} 个token（共 {len(tokens)} 个）")
                
            batch_url = f"{base_url}/batch/scrape"
            
            payload = {
                "urls": [url],
                "ignoreInvalidURLs": False,
                "formats": ["markdown"],
                "onlyMainContent": True,
                "headers": {},
                "waitFor": 0,
                "mobile": False,
                "skipTlsVerification": False,
                "timeout": 30000,
                "actions": [
                    {
                        "type": "wait",
                        "milliseconds": 2000
                    }
                ],
                "location": {
                    "country": "US",
                    "languages": ["en-US"]
                },
                "removeBase64Images": True,
                "blockAds": True,
                "proxy": "basic"
            }
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # Submit batch scraping request
            logger.info("提交Firecrawl批量抓取请求")
            response = requests.post(batch_url, json=payload, headers=headers)
            response.raise_for_status()
            job_data = response.json()
            
            if not job_data.get("success"):
                logger.error(f"Firecrawl批量抓取请求失败: {job_data}")
                return ""
                
            job_id = job_data.get("id")
            logger.info(f"Firecrawl作业ID: {job_id}")
            
            # Poll for results
            max_retries = 5
            retry_interval = 3  # seconds
            
            for attempt in range(max_retries):
                logger.info(f"轮询Firecrawl结果，尝试 {attempt+1}/{max_retries}")
                status_url = f"{base_url}/batch/scrape/{job_id}"
                status_response = requests.get(status_url, headers=headers)
                status_response.raise_for_status()
                status_data = status_response.json()
                
                if status_data.get("status") == "completed":
                    # Extract markdown content
                    if status_data.get("data") and len(status_data["data"]) > 0:
                        # First item should be our URL since we only requested one
                        data_item = status_data["data"][0]
                        
                        # Check for markdown field directly (new format)
                        if "markdown" in data_item:
                            end_time = time.time()
                            logger.info(f"Firecrawl提取完成，耗时: {end_time - start_time:.2f}秒")
                            return data_item.get("markdown", "")
                        
                        # Fall back to the previous format if needed
                        elif "formats" in data_item:
                            for format_data in data_item.get("formats", []):
                                if format_data.get("format") == "markdown":
                                    end_time = time.time()
                                    logger.info(f"Firecrawl提取完成，耗时: {end_time - start_time:.2f}秒")
                                    return format_data.get("data", "")
                    
                    logger.error("在Firecrawl响应中找不到Markdown内容")
                    return ""
                
                # If not completed, wait and try again
                if attempt < max_retries - 1:
                    logger.info(f"Firecrawl作业未完成，等待 {retry_interval} 秒后重试")
                    time.sleep(retry_interval)
                    retry_interval = min(retry_interval * 1.5, 10)
            
            logger.error("Firecrawl提取超时")
            return ""
            
        except Exception as e:
            logger.error(f"Firecrawl提取失败: {str(e)}")
            return ""

    def extract_text_html2text(self, url):
        try:
            start_time = time.time()
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            h = html2text.HTML2Text()
            h.ignore_links = True
            h.ignore_images = True
            result = h.handle(response.text)
            end_time = time.time()
            logger.info(f"html2text提取完成，耗时: {end_time - start_time:.2f}秒")
            return result
        except Exception as e:
            logger.error(f"html2text提取失败: {str(e)}")
            return ""

    def extract_content_trafilatura(self, url):
        try:
            start_time = time.time()
            downloaded = trafilatura.fetch_url(url)
            result = trafilatura.extract(downloaded, include_images=False, include_links=False)
            end_time = time.time()
            logger.info(f"Trafilatura提取完成，耗时: {end_time - start_time:.2f}秒")
            return result
        except Exception as e:
            logger.error(f"Trafilatura提取失败: {str(e)}")
            return ""

    def extract_content_beautifulsoup(self, url):
        try:
            start_time = time.time()
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            result = ' '.join(soup.stripped_strings)
            end_time = time.time()
            logger.info(f"BeautifulSoup提取完成，耗时: {end_time - start_time:.2f}秒")
            return result
        except Exception as e:
            logger.error(f"BeautifulSoup提取失败: {str(e)}")
            return ""


class ExtractWebContentListToolSchema(BaseModel):
    """Input for ExtractWebContentListTool."""
    web_info_list: List[Dict[str, str]] = Field(
        ..., description="List of Web information items to extract content from. Each item should be a dictionary containing 'url', 'title', and optionally 'snap' keys."
    )

class ExtractWebContentListTool(BaseTool):
    name: str = "Extract content from multiple webpages"
    description: str = (
        "A tool that can be used to extract content from a list of URLs concurrently."
    )
    args_schema: Type[BaseModel] = ExtractWebContentListToolSchema
    max_workers: int = 2

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("初始化ExtractWebContentListTool")

    def _run(
        self,
        web_info_list: List[Dict[str, str]],
    ) -> Any:
        logger.info(f"开始从 {len(web_info_list)} 个网页提取内容")
        start_time = time.time()
        results = self.fetch_contents_concurrently(web_info_list)
        end_time = time.time()
        logger.info(f"所有网页内容提取完成，耗时: {end_time - start_time:.2f}秒")
        return results

    def fetch_contents_concurrently(self, web_info_list):
        logger.info(f"web_info_list类型: {type(web_info_list)}")
        extractor = ExtractWebContentTool()
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(
                lambda item: self.extract_content_wrapper(extractor, item['url'], item['title']),
                web_info_list
            ))
        return results

    def extract_content_wrapper(self, extractor, url, title):
        logger.info(f"从 {url} 提取内容")
        start_time = time.time()
        result = extractor.extract_content(url, title)
        end_time = time.time()
        logger.info(f"从 {url} 提取内容完成，耗时: {end_time - start_time:.2f}秒")
        return result