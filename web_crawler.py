#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from datetime import datetime
from typing import List, Dict, Any

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from element_finder import InteractionElementFinder
from utils import ensure_directory, extract_domain, is_valid_url, format_filename
from browser_profile import BrowserProfile


class WebCrawler:
    """网页爬虫，用于爬取网页中的交互元素"""

    def __init__(self, headless: bool = False, output_dir: str = 'output',
                 element_finder: InteractionElementFinder = None,
                 scroll_count: int = 3, delay: float = 2.0,
                 stop_event = None, profile_name: str = None):
        """初始化爬虫

        Args:
            headless: 是否使用无头模式运行浏览器
            output_dir: 输出目录
            element_finder: 交互元素查找器实例
            scroll_count: 页面滚动次数
            delay: URL间延迟时间(秒)
            stop_event: 停止事件，用于从外部停止爬虫
            profile_name: 浏览器配置文件名称，如果提供则使用该配置
        """
        self.headless = headless
        self.output_dir = output_dir
        self.driver = None
        self.element_finder = element_finder or InteractionElementFinder()
        self.scroll_count = scroll_count
        self.delay = delay
        self.stop_event = stop_event
        self.profile_name = profile_name
        self.browser_profile = BrowserProfile(profile_name) if profile_name else None

        # 创建输出目录
        ensure_directory(output_dir)

    def setup_driver(self):
        """设置Selenium WebDriver"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36')

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.set_page_load_timeout(30)

        # 如果有浏览器配置文件，应用它
        if self.browser_profile:
            print(f"正在应用浏览器配置文件: {self.profile_name}")
            self.browser_profile.apply_to_driver(self.driver)

    def close_driver(self):
        """关闭WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def process_csv(self, csv_path: str):
        """处理CSV文件中的URL

        Args:
            csv_path: CSV文件路径
        """
        try:
            # 读取CSV文件
            df = pd.read_csv(csv_path)

            # 查找包含URL的列
            url_columns = []
            for col in df.columns:
                # 检查列名是否包含URL相关关键词
                if any(keyword in col.lower() for keyword in ['url', 'link', 'website', 'site', 'web']):
                    url_columns.append(col)

            # 如果没有找到URL列，尝试检查每一列的内容
            if not url_columns:
                for col in df.columns:
                    # 检查前10行是否包含URL
                    sample = df[col].head(10).astype(str)
                    if any('http' in str(val).lower() for val in sample):
                        url_columns.append(col)

            # 如果仍然没有找到URL列，使用第一列
            if not url_columns and len(df.columns) > 0:
                url_columns = [df.columns[0]]

            # 处理每个URL
            total_urls = sum(len(df[col]) for col in url_columns)
            processed = 0

            for col in url_columns:
                for idx, url in enumerate(df[col]):
                    # 检查是否应该停止
                    if self.stop_event and self.stop_event.is_set():
                        print("爬虫已停止")
                        return

                    if is_valid_url(url):
                        processed += 1
                        print(f"处理URL {processed}/{total_urls}: {url}")
                        self.process_url(url, idx)

                        # 添加延迟以避免被网站封锁
                        if self.stop_event:
                            # 如果有停止事件，分段等待以便及时响应停止
                            for _ in range(int(self.delay * 2)):
                                if self.stop_event.is_set():
                                    break
                                time.sleep(0.5)
                        else:
                            time.sleep(self.delay)

        except Exception as e:
            print(f"处理CSV文件出错: {e}")

    def process_url(self, url: str, index: int):
        """处理单个URL

        Args:
            url: 网页URL
            index: URL索引
        """
        # 检查是否应该停止
        if self.stop_event and self.stop_event.is_set():
            return

        if not self.driver:
            self.setup_driver()

        try:
            # 访问网页
            self.driver.get(url)

            # 等待页面加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # 检查是否应该停止
            if self.stop_event and self.stop_event.is_set():
                return

            # 滚动页面以加载懒加载元素
            self._scroll_page()

            # 检查是否应该停止
            if self.stop_event and self.stop_event.is_set():
                return

            # 查找交互元素
            interaction_elements = self.element_finder.find_interaction_elements(self.driver)

            if interaction_elements:
                # 保存元素信息
                self._save_elements(url, interaction_elements, index)

                # 检查是否应该停止
                if self.stop_event and self.stop_event.is_set():
                    return

                # 点击第一个元素（如果有）
                if interaction_elements:
                    self._click_element(url, interaction_elements[0], index)
            else:
                print(f"在 {url} 上未找到交互元素")

        except TimeoutException:
            print(f"加载页面超时: {url}")
        except Exception as e:
            print(f"处理URL出错 {url}: {e}")

    def _scroll_page(self):
        """滚动页面以加载懒加载元素"""
        try:
            # 获取页面高度
            last_height = self.driver.execute_script("return document.body.scrollHeight")

            # 滚动到页面底部
            for i in range(self.scroll_count):
                # 检查是否应该停止
                if self.stop_event and self.stop_event.is_set():
                    return

                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)  # 等待页面加载

                # 计算新的页面高度
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            # 滚动回页面顶部
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
        except Exception as e:
            print(f"滚动页面出错: {e}")

    def _save_elements(self, url: str, elements: List[Dict[str, Any]], index: int):
        """保存元素信息到文件

        Args:
            url: 网页URL
            elements: 元素信息列表
            index: URL索引
        """
        try:
            # 创建输出文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            domain = extract_domain(url)

            # 使用工具函数格式化文件名
            json_filename = format_filename(index, domain, timestamp, "json")
            full_json_path = f"{self.output_dir}/{json_filename}"

            # 保存元素信息
            data = {
                'url': url,
                'timestamp': timestamp,
                'elements_count': len(elements),
                'elements': elements
            }

            with open(full_json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"已保存 {len(elements)} 个元素到 {full_json_path}")

            # 保存网页截图
            screenshot_filename = format_filename(index, domain, timestamp, "png")
            full_screenshot_path = f"{self.output_dir}/{screenshot_filename}"
            self.driver.save_screenshot(full_screenshot_path)
            print(f"已保存截图到 {full_screenshot_path}")

        except Exception as e:
            print(f"保存元素出错: {e}")

    def _click_element(self, url: str, element_info: Dict[str, Any], index: int):
        """点击元素

        Args:
            url: 网页URL
            element_info: 元素信息
            index: URL索引
        """
        # 检查是否应该停止
        if self.stop_event and self.stop_event.is_set():
            return

        try:
            # 尝试使用XPath定位元素
            xpath = element_info.get('element_xpath')
            if xpath and xpath != "Unknown":
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    print(f"点击元素: {element_info.get('element_text', '')} (XPath)")
                    element.click()
                    time.sleep(1)  # 等待点击后的响应
                    return
                except (NoSuchElementException, Exception) as e:
                    print(f"通过XPath点击元素出错: {e}")

            # 检查是否应该停止
            if self.stop_event and self.stop_event.is_set():
                return

            # 尝试使用CSS选择器定位元素
            css = element_info.get('element_css')
            if css and css != "Unknown":
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, css)
                    print(f"点击元素: {element_info.get('element_text', '')} (CSS)")
                    element.click()
                    time.sleep(1)  # 等待点击后的响应
                    return
                except (NoSuchElementException, Exception) as e:
                    print(f"通过CSS点击元素出错: {e}")

            print(f"无法在 {url} 上点击元素")

        except Exception as e:
            print(f"点击元素出错: {e}")
