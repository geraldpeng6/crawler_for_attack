#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import json
import time
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


class InteractionElementFinder:
    """查找网页中的交互元素，如点赞、点踩、投票等按钮"""
    
    # 可能的交互元素关键词
    INTERACTION_KEYWORDS = [
        # 中文关键词
        '点赞', '赞', '喜欢', '顶', '支持', 
        '点踩', '踩', '不喜欢', '倒', '反对',
        '投票', '评分', '评价', '收藏', '分享',
        # 英文关键词
        'like', 'upvote', 'up vote', 'up-vote', 'thumbs up', '+1',
        'dislike', 'downvote', 'down vote', 'down-vote', 'thumbs down', '-1',
        'vote', 'rating', 'rate', 'favorite', 'bookmark', 'share', 'react',
        'helpful', 'recommend', 'agree', 'disagree', 'support', 'oppose'
    ]
    
    # 可能的交互元素CSS选择器模式
    ELEMENT_SELECTORS = [
        'button', 'a.vote', 'a.like', 'div.vote', 'div.like', 
        'span.vote', 'span.like', 'i.fa-thumbs-up', 'i.fa-thumbs-down',
        '[aria-label*="like"]', '[aria-label*="vote"]', '[title*="like"]', '[title*="vote"]',
        '.vote-up', '.vote-down', '.upvote', '.downvote', '.like-button', '.dislike-button',
        '[data-action="upvote"]', '[data-action="downvote"]', '[data-action="like"]'
    ]
    
    def __init__(self, similarity_threshold: int = 70):
        """初始化交互元素查找器
        
        Args:
            similarity_threshold: 模糊匹配的相似度阈值(0-100)，默认为70
        """
        self.similarity_threshold = similarity_threshold
    
    def find_interaction_elements(self, driver) -> List[Dict[str, Any]]:
        """在网页中查找所有可能的交互元素
        
        Args:
            driver: Selenium WebDriver实例
            
        Returns:
            包含所有找到的交互元素信息的列表
        """
        found_elements = []
        
        # 1. 通过关键词在文本中查找
        for keyword in self.INTERACTION_KEYWORDS:
            elements = driver.find_elements(By.XPATH, 
                f"//*[contains(text(), '{keyword}') or contains(@value, '{keyword}') or "
                f"contains(@aria-label, '{keyword}') or contains(@title, '{keyword}')]"
            )
            
            for element in elements:
                if self._is_likely_interaction_element(element):
                    found_elements.append(self._create_element_info(element, keyword, 'keyword_match'))
        
        # 2. 通过CSS选择器查找
        for selector in self.ELEMENT_SELECTORS:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if self._is_likely_interaction_element(element):
                        found_elements.append(self._create_element_info(element, selector, 'selector_match'))
            except Exception:
                continue
        
        # 3. 查找包含SVG图标的元素（通常用于现代网站的点赞/点踩按钮）
        svg_elements = driver.find_elements(By.XPATH, "//button[.//svg] | //a[.//svg] | //div[.//svg and @role='button']")
        for element in svg_elements:
            if self._is_likely_interaction_element(element):
                found_elements.append(self._create_element_info(element, 'svg_icon', 'svg_match'))
        
        # 4. 查找可能的计数器元素（通常在点赞按钮旁边）
        counter_elements = driver.find_elements(By.XPATH, 
            "//span[contains(@class, 'count') or contains(@class, 'num') or contains(@class, 'score')]"
        )
        for element in counter_elements:
            parent = element.find_element(By.XPATH, "..")
            if self._is_likely_interaction_element(parent):
                found_elements.append(self._create_element_info(parent, 'counter_parent', 'counter_match'))
        
        # 去重
        unique_elements = self._deduplicate_elements(found_elements)
        return unique_elements
    
    def _is_likely_interaction_element(self, element) -> bool:
        """判断元素是否可能是交互元素"""
        try:
            # 检查元素是否可见且可交互
            if not element.is_displayed() or not element.is_enabled():
                return False
                
            # 获取元素的各种属性
            element_text = element.text.lower() if element.text else ""
            element_tag = element.tag_name.lower()
            element_class = element.get_attribute("class") or ""
            element_id = element.get_attribute("id") or ""
            element_aria_label = element.get_attribute("aria-label") or ""
            element_title = element.get_attribute("title") or ""
            element_role = element.get_attribute("role") or ""
            
            # 组合所有文本信息进行模糊匹配
            combined_text = f"{element_text} {element_class} {element_id} {element_aria_label} {element_title}".lower()
            
            # 检查是否是可点击元素
            clickable_tags = ['button', 'a', 'input']
            clickable_roles = ['button', 'link', 'checkbox', 'radio']
            
            is_clickable = (
                element_tag in clickable_tags or
                element_role in clickable_roles or
                'button' in element_class.lower() or
                'btn' in element_class.lower()
            )
            
            # 对每个关键词进行模糊匹配
            for keyword in self.INTERACTION_KEYWORDS:
                similarity = fuzz.partial_ratio(keyword.lower(), combined_text)
                if similarity >= self.similarity_threshold and is_clickable:
                    return True
                    
            return False
        except Exception:
            return False
    
    def _create_element_info(self, element, match_term: str, match_type: str) -> Dict[str, Any]:
        """创建元素信息字典"""
        try:
            element_text = element.text.strip() if element.text else ""
            element_html = element.get_attribute('outerHTML')
            element_tag = element.tag_name
            element_class = element.get_attribute("class") or ""
            element_id = element.get_attribute("id") or ""
            element_aria_label = element.get_attribute("aria-label") or ""
            element_title = element.get_attribute("title") or ""
            
            # 尝试获取元素的XPath
            try:
                element_xpath = self._generate_xpath(element)
            except:
                element_xpath = "Unknown"
                
            # 尝试获取元素的CSS选择器
            try:
                element_css = self._generate_css_selector(element)
            except:
                element_css = "Unknown"
            
            return {
                'element_text': element_text,
                'element_tag': element_tag,
                'element_class': element_class,
                'element_id': element_id,
                'element_aria_label': element_aria_label,
                'element_title': element_title,
                'element_html': element_html,
                'element_xpath': element_xpath,
                'element_css': element_css,
                'match_term': match_term,
                'match_type': match_type
            }
        except Exception as e:
            return {
                'element_text': 'Error extracting element info',
                'element_tag': 'unknown',
                'error': str(e),
                'match_term': match_term,
                'match_type': match_type
            }
    
    def _generate_xpath(self, element) -> str:
        """生成元素的XPath"""
        script = """
        function getPathTo(element) {
            if (element.id !== '')
                return '//*[@id="' + element.id + '"]';
            if (element === document.body)
                return '/html/body';

            var index = 1;
            var siblings = element.parentNode.childNodes;
            for (var i = 0; i < siblings.length; i++) {
                var sibling = siblings[i];
                if (sibling === element)
                    return getPathTo(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + index + ']';
                if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                    index++;
            }
        }
        return getPathTo(arguments[0]);
        """
        driver = element.parent
        return driver.execute_script(script, element)
    
    def _generate_css_selector(self, element) -> str:
        """生成元素的CSS选择器"""
        script = """
        function getCssSelector(el) {
            if (!(el instanceof Element)) return;
            var path = [];
            while (el.nodeType === Node.ELEMENT_NODE) {
                var selector = el.nodeName.toLowerCase();
                if (el.id) {
                    selector += '#' + el.id;
                    path.unshift(selector);
                    break;
                } else {
                    var sib = el, nth = 1;
                    while (sib = sib.previousElementSibling) {
                        if (sib.nodeName.toLowerCase() == selector) nth++;
                    }
                    if (nth != 1) selector += ":nth-of-type("+nth+")";
                }
                path.unshift(selector);
                el = el.parentNode;
            }
            return path.join(" > ");
        }
        return getCssSelector(arguments[0]);
        """
        driver = element.parent
        return driver.execute_script(script, element)
    
    def _deduplicate_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去除重复的元素"""
        unique_elements = []
        seen_xpaths = set()
        
        for element in elements:
            xpath = element.get('element_xpath', '')
            if xpath and xpath not in seen_xpaths:
                seen_xpaths.add(xpath)
                unique_elements.append(element)
        
        return unique_elements


class WebCrawler:
    """网页爬虫，用于爬取网页中的交互元素"""
    
    def __init__(self, headless: bool = False, output_dir: str = 'output'):
        """初始化爬虫
        
        Args:
            headless: 是否使用无头模式运行浏览器
            output_dir: 输出目录
        """
        self.headless = headless
        self.output_dir = output_dir
        self.driver = None
        self.element_finder = InteractionElementFinder()
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
    
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
            for col in url_columns:
                for idx, url in enumerate(df[col]):
                    if isinstance(url, str) and ('http://' in url or 'https://' in url):
                        print(f"Processing URL {idx+1}/{len(df)}: {url}")
                        self.process_url(url, idx)
                        # 添加延迟以避免被网站封锁
                        time.sleep(2)
        
        except Exception as e:
            print(f"Error processing CSV file: {e}")
    
    def process_url(self, url: str, index: int):
        """处理单个URL
        
        Args:
            url: 网页URL
            index: URL索引
        """
        if not self.driver:
            self.setup_driver()
        
        try:
            # 访问网页
            self.driver.get(url)
            
            # 等待页面加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 滚动页面以加载懒加载元素
            self._scroll_page()
            
            # 查找交互元素
            interaction_elements = self.element_finder.find_interaction_elements(self.driver)
            
            if interaction_elements:
                # 保存元素信息
                self._save_elements(url, interaction_elements, index)
                
                # 点击第一个元素（如果有）
                if interaction_elements:
                    self._click_element(url, interaction_elements[0], index)
            else:
                print(f"No interaction elements found on {url}")
        
        except TimeoutException:
            print(f"Timeout loading page: {url}")
        except Exception as e:
            print(f"Error processing URL {url}: {e}")
    
    def _scroll_page(self):
        """滚动页面以加载懒加载元素"""
        try:
            # 获取页面高度
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # 滚动到页面底部
            for _ in range(3):  # 滚动3次
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
            print(f"Error scrolling page: {e}")
    
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
            domain = url.split('//')[-1].split('/')[0].replace('.', '_')
            filename = f"{self.output_dir}/{index}_{domain}_{timestamp}.json"
            
            # 保存元素信息
            data = {
                'url': url,
                'timestamp': timestamp,
                'elements_count': len(elements),
                'elements': elements
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            print(f"Saved {len(elements)} elements to {filename}")
            
            # 保存网页截图
            screenshot_filename = f"{self.output_dir}/{index}_{domain}_{timestamp}.png"
            self.driver.save_screenshot(screenshot_filename)
            print(f"Saved screenshot to {screenshot_filename}")
            
        except Exception as e:
            print(f"Error saving elements: {e}")
    
    def _click_element(self, url: str, element_info: Dict[str, Any], index: int):
        """点击元素
        
        Args:
            url: 网页URL
            element_info: 元素信息
            index: URL索引
        """
        try:
            # 尝试使用XPath定位元素
            xpath = element_info.get('element_xpath')
            if xpath and xpath != "Unknown":
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    print(f"Clicking element: {element_info.get('element_text', '')} (XPath)")
                    element.click()
                    time.sleep(1)  # 等待点击后的响应
                    return
                except (NoSuchElementException, Exception) as e:
                    print(f"Error clicking element by XPath: {e}")
            
            # 尝试使用CSS选择器定位元素
            css = element_info.get('element_css')
            if css and css != "Unknown":
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, css)
                    print(f"Clicking element: {element_info.get('element_text', '')} (CSS)")
                    element.click()
                    time.sleep(1)  # 等待点击后的响应
                    return
                except (NoSuchElementException, Exception) as e:
                    print(f"Error clicking element by CSS: {e}")
            
            print(f"Could not click element on {url}")
            
        except Exception as e:
            print(f"Error clicking element: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Web crawler for interaction elements')
    parser.add_argument('csv_file', help='Path to CSV file containing URLs')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--output-dir', default='output', help='Output directory for results')
    
    args = parser.parse_args()
    
    crawler = WebCrawler(headless=args.headless, output_dir=args.output_dir)
    
    try:
        crawler.process_csv(args.csv_file)
    finally:
        crawler.close_driver()


if __name__ == '__main__':
    main()