#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import pickle
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from utils import ensure_directory


class BrowserProfile:
    """浏览器配置文件管理类，用于保存和加载浏览器配置（如Cookie）"""

    PROFILES_DIR = "browser_profiles"

    def __init__(self, profile_name: str = "default"):
        """初始化浏览器配置文件

        Args:
            profile_name: 配置文件名称
        """
        self.profile_name = profile_name
        self.profile_dir = os.path.join(self.PROFILES_DIR, profile_name)
        self.user_data_dir = os.path.join(self.profile_dir, "user_data")
        self.cookies_file = os.path.join(self.profile_dir, "cookies.pkl")
        self.local_storage_file = os.path.join(self.profile_dir, "local_storage.json")
        self.session_storage_file = os.path.join(self.profile_dir, "session_storage.json")

        # 确保配置文件目录和用户数据目录存在
        ensure_directory(self.profile_dir)
        ensure_directory(self.user_data_dir)

    def create_profile(self, url: str = "https://www.baidu.com", wait_time: int = 300) -> bool:
        """创建浏览器配置文件

        打开一个浏览器窗口，让用户登录或设置Cookie，然后保存配置

        Args:
            url: 初始URL
            wait_time: 等待用户操作的最大时间（秒）

        Returns:
            是否成功创建配置文件
        """
        try:
            logging.info(f"正在创建浏览器配置文件: {self.profile_name}")
            logging.info("请在打开的浏览器中登录或设置所需的Cookie")
            logging.info(f"浏览器将在 {wait_time} 秒后自动关闭，或者您可以手动关闭浏览器窗口")

            # 创建一个可见的浏览器窗口
            driver = self._create_driver(headless=False)

            # 访问初始URL
            driver.get(url)

            # 等待用户操作
            timeout = time.time() + wait_time
            while time.time() < timeout:
                # 每秒检查一次浏览器是否仍然打开
                try:
                    # 尝试获取当前URL，如果浏览器已关闭会抛出异常
                    current_url = driver.current_url
                    time.sleep(1)
                except:
                    # 浏览器已关闭
                    logging.info("浏览器已关闭")
                    break

            # 保存配置
            self._save_browser_state(driver)

            # 关闭浏览器
            driver.quit()

            logging.info(f"浏览器配置文件已保存: {self.profile_name}")
            return True

        except Exception as e:
            logging.error(f"创建浏览器配置文件出错: {e}")
            return False

    def apply_to_driver(self, driver: webdriver.Chrome) -> bool:
        """将配置应用到WebDriver

        注意：当使用用户数据目录时，不需要手动设置cookies、localStorage和sessionStorage，
        因为这些都已经包含在用户数据目录中。此方法主要用于兼容旧版本。

        Args:
            driver: WebDriver实例

        Returns:
            是否成功应用配置
        """
        # 如果我们使用的是用户数据目录，则不需要手动应用配置
        if hasattr(driver, 'options') and any('--user-data-dir' in arg for arg in driver.options.arguments):
            logging.info("使用用户数据目录，无需手动应用配置")
            return True

        try:
            # 加载Cookie（仅在不使用用户数据目录时）
            if os.path.exists(self.cookies_file):
                with open(self.cookies_file, 'rb') as f:
                    cookies = pickle.load(f)

                # 先访问一个页面，然后才能设置Cookie
                current_url = driver.current_url
                if not current_url.startswith('http'):
                    driver.get('about:blank')

                for cookie in cookies:
                    try:
                        driver.add_cookie(cookie)
                    except Exception as e:
                        logging.warning(f"添加Cookie出错: {e}")

            # 加载localStorage
            if os.path.exists(self.local_storage_file):
                with open(self.local_storage_file, 'r', encoding='utf-8') as f:
                    local_storage = json.load(f)

                for key, value in local_storage.items():
                    driver.execute_script(f"localStorage.setItem('{key}', '{value}');")

            # 加载sessionStorage
            if os.path.exists(self.session_storage_file):
                with open(self.session_storage_file, 'r', encoding='utf-8') as f:
                    session_storage = json.load(f)

                for key, value in session_storage.items():
                    driver.execute_script(f"sessionStorage.setItem('{key}', '{value}');")

            return True

        except Exception as e:
            logging.error(f"应用浏览器配置出错: {e}")
            return False

    def _save_browser_state(self, driver: webdriver.Chrome):
        """保存浏览器状态

        注意：当使用用户数据目录时，浏览器状态会自动保存到用户数据目录中。
        但我们仍然保存一些关键数据作为备份。

        Args:
            driver: WebDriver实例
        """
        try:
            # 保存Cookie
            cookies = driver.get_cookies()
            with open(self.cookies_file, 'wb') as f:
                pickle.dump(cookies, f)

            # 保存localStorage
            local_storage = driver.execute_script("return Object.assign({}, localStorage);")
            with open(self.local_storage_file, 'w', encoding='utf-8') as f:
                json.dump(local_storage, f, ensure_ascii=False, indent=2)

            # 保存sessionStorage
            session_storage = driver.execute_script("return Object.assign({}, sessionStorage);")
            with open(self.session_storage_file, 'w', encoding='utf-8') as f:
                json.dump(session_storage, f, ensure_ascii=False, indent=2)

            # 创建一个标记文件，表示配置已保存
            with open(os.path.join(self.profile_dir, "profile.json"), 'w', encoding='utf-8') as f:
                profile_info = {
                    "name": self.profile_name,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "user_data_dir": self.user_data_dir
                }
                json.dump(profile_info, f, ensure_ascii=False, indent=2)

            logging.info(f"浏览器状态已保存到: {self.profile_dir}")

        except Exception as e:
            logging.error(f"保存浏览器状态出错: {e}")

    def _create_driver(self, headless: bool = False) -> webdriver.Chrome:
        """创建WebDriver实例

        Args:
            headless: 是否使用无头模式

        Returns:
            WebDriver实例
        """
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')

        # 使用用户数据目录
        chrome_options.add_argument(f'--user-data-dir={self.user_data_dir}')

        # 其他常用选项
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36')

        # 启用所有实验性功能
        chrome_options.add_argument('--enable-features=NetworkService,NetworkServiceInProcess')

        # 禁用安全限制
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')

        # 禁用扩展和弹出窗口
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-popup-blocking')

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)

        return driver

    @classmethod
    def get_all_profiles(cls) -> List[str]:
        """获取所有可用的配置文件

        Returns:
            配置文件名称列表
        """
        ensure_directory(cls.PROFILES_DIR)
        profiles = []

        for item in os.listdir(cls.PROFILES_DIR):
            profile_dir = os.path.join(cls.PROFILES_DIR, item)
            if os.path.isdir(profile_dir):
                # 检查是否存在profile.json文件（新版本）
                profile_json = os.path.join(profile_dir, "profile.json")
                if os.path.exists(profile_json):
                    profiles.append(item)
                    continue

                # 向后兼容：检查是否存在cookies.pkl文件（旧版本）
                cookies_file = os.path.join(profile_dir, "cookies.pkl")
                if os.path.exists(cookies_file):
                    profiles.append(item)

        return profiles

    @classmethod
    def delete_profile(cls, profile_name: str) -> bool:
        """删除配置文件

        Args:
            profile_name: 配置文件名称

        Returns:
            是否成功删除
        """
        try:
            profile_dir = os.path.join(cls.PROFILES_DIR, profile_name)
            if os.path.exists(profile_dir):
                for file in os.listdir(profile_dir):
                    os.remove(os.path.join(profile_dir, file))
                os.rmdir(profile_dir)
                return True
            return False
        except Exception as e:
            logging.error(f"删除配置文件出错: {e}")
            return False
