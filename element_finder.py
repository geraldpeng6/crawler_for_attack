#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Dict, Any
from fuzzywuzzy import fuzz
from selenium.webdriver.common.by import By


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
