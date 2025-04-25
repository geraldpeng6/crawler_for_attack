#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import queue
import logging

from web_crawler import WebCrawler
from element_finder import InteractionElementFinder
from utils import ensure_directory
from browser_profile import BrowserProfile


class RedirectText:
    """重定向文本到Tkinter文本控件"""

    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.queue = queue.Queue()
        self.updating = True
        threading.Thread(target=self.update_text_widget, daemon=True).start()

    def write(self, string):
        self.queue.put(string)

    def flush(self):
        pass

    def update_text_widget(self):
        while self.updating:
            try:
                while True:
                    text = self.queue.get_nowait()
                    self.text_widget.configure(state='normal')
                    self.text_widget.insert(tk.END, text)
                    self.text_widget.see(tk.END)
                    self.text_widget.configure(state='disabled')
                    self.queue.task_done()
            except queue.Empty:
                pass
            self.text_widget.after(100, self.update_text_widget)
            return

    def stop(self):
        self.updating = False


class CrawlerGUI(tk.Tk):
    """爬虫GUI应用"""

    def __init__(self):
        super().__init__()

        self.title("网页交互元素爬虫工具")
        self.geometry("900x700")
        self.minsize(800, 600)

        self.crawler_thread = None
        self.stop_event = threading.Event()

        self.create_widgets()
        self.setup_logging()

    def create_widgets(self):
        """创建GUI控件"""
        # 创建主框架
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建左侧设置面板
        settings_frame = ttk.LabelFrame(main_frame, text="爬虫设置")
        settings_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5, pady=5)

        # 文件选择
        file_frame = ttk.Frame(settings_frame)
        file_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(file_frame, text="CSV文件:").pack(side=tk.LEFT, padx=5)
        self.csv_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.csv_path_var, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="浏览...", command=self.browse_csv).pack(side=tk.LEFT, padx=5)

        # 输出目录
        output_frame = ttk.Frame(settings_frame)
        output_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(output_frame, text="输出目录:").pack(side=tk.LEFT, padx=5)
        self.output_dir_var = tk.StringVar(value="output")
        ttk.Entry(output_frame, textvariable=self.output_dir_var, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Button(output_frame, text="浏览...", command=self.browse_output_dir).pack(side=tk.LEFT, padx=5)

        # 浏览器配置文件
        profile_frame = ttk.LabelFrame(settings_frame, text="浏览器配置文件")
        profile_frame.pack(fill=tk.X, padx=5, pady=5)

        # 配置文件选择
        profile_select_frame = ttk.Frame(profile_frame)
        profile_select_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(profile_select_frame, text="选择配置:").pack(side=tk.LEFT, padx=5)
        self.profile_var = tk.StringVar()
        self.profile_combobox = ttk.Combobox(profile_select_frame, textvariable=self.profile_var, state="readonly", width=20)
        self.profile_combobox.pack(side=tk.LEFT, padx=5)
        self.update_profile_list()

        # 配置文件管理按钮
        profile_buttons_frame = ttk.Frame(profile_frame)
        profile_buttons_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(profile_buttons_frame, text="创建新配置", command=self.create_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(profile_buttons_frame, text="删除配置", command=self.delete_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(profile_buttons_frame, text="刷新列表", command=self.update_profile_list).pack(side=tk.LEFT, padx=5)

        # 无头模式选项
        headless_frame = ttk.Frame(settings_frame)
        headless_frame.pack(fill=tk.X, padx=5, pady=5)

        self.headless_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(headless_frame, text="无头模式 (不显示浏览器窗口)", variable=self.headless_var).pack(anchor=tk.W, padx=5)

        # 高级设置
        advanced_frame = ttk.LabelFrame(settings_frame, text="高级设置")
        advanced_frame.pack(fill=tk.X, padx=5, pady=5)

        # 相似度阈值
        similarity_frame = ttk.Frame(advanced_frame)
        similarity_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(similarity_frame, text="相似度阈值 (0-100):").pack(side=tk.LEFT, padx=5)
        self.similarity_var = tk.IntVar(value=70)
        ttk.Spinbox(similarity_frame, from_=0, to=100, textvariable=self.similarity_var, width=5).pack(side=tk.LEFT, padx=5)

        # 页面滚动次数
        scroll_frame = ttk.Frame(advanced_frame)
        scroll_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(scroll_frame, text="页面滚动次数:").pack(side=tk.LEFT, padx=5)
        self.scroll_count_var = tk.IntVar(value=3)
        ttk.Spinbox(scroll_frame, from_=0, to=10, textvariable=self.scroll_count_var, width=5).pack(side=tk.LEFT, padx=5)

        # 延迟时间
        delay_frame = ttk.Frame(advanced_frame)
        delay_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(delay_frame, text="URL间延迟 (秒):").pack(side=tk.LEFT, padx=5)
        self.delay_var = tk.DoubleVar(value=2.0)
        ttk.Spinbox(delay_frame, from_=0.5, to=10.0, increment=0.5, textvariable=self.delay_var, width=5).pack(side=tk.LEFT, padx=5)

        # 自定义关键词
        keywords_frame = ttk.LabelFrame(settings_frame, text="自定义关键词 (每行一个)")
        keywords_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.keywords_text = tk.Text(keywords_frame, height=5, width=30)
        self.keywords_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 按钮
        buttons_frame = ttk.Frame(settings_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=10)

        self.start_button = ttk.Button(buttons_frame, text="开始爬取", command=self.start_crawler)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(buttons_frame, text="停止", command=self.stop_crawler, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # 创建右侧日志面板
        log_frame = ttk.LabelFrame(main_frame, text="日志")
        log_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='disabled')
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_logging(self):
        """设置日志重定向"""
        self.text_handler = RedirectText(self.log_text)

        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(self.text_handler)]
        )

        # 重定向标准输出和标准错误
        sys.stdout = self.text_handler
        sys.stderr = self.text_handler

        logging.info("爬虫GUI已启动")

    def browse_csv(self):
        """浏览并选择CSV文件"""
        filename = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if filename:
            self.csv_path_var.set(filename)
            logging.info(f"已选择CSV文件: {filename}")

    def browse_output_dir(self):
        """浏览并选择输出目录"""
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.output_dir_var.set(directory)
            logging.info(f"已选择输出目录: {directory}")

    def update_profile_list(self):
        """更新浏览器配置文件列表"""
        profiles = [""] + BrowserProfile.get_all_profiles()
        self.profile_combobox['values'] = profiles
        if profiles and self.profile_var.get() not in profiles:
            self.profile_var.set("")

    def create_profile(self):
        """创建新的浏览器配置文件"""
        # 创建一个对话框来获取配置文件名称和初始URL
        dialog = tk.Toplevel(self)
        dialog.title("创建浏览器配置文件")
        dialog.geometry("500x300")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # 配置文件名称
        name_frame = ttk.Frame(dialog)
        name_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(name_frame, text="配置文件名称:").pack(side=tk.LEFT, padx=5)
        name_var = tk.StringVar()
        ttk.Entry(name_frame, textvariable=name_var, width=20).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # 初始URL
        url_frame = ttk.Frame(dialog)
        url_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(url_frame, text="初始URL:").pack(side=tk.LEFT, padx=5)
        url_var = tk.StringVar(value="https://www.baidu.com")
        ttk.Entry(url_frame, textvariable=url_var, width=30).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # 等待时间
        time_frame = ttk.Frame(dialog)
        time_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(time_frame, text="最长等待时间(秒):").pack(side=tk.LEFT, padx=5)
        time_var = tk.IntVar(value=300)
        ttk.Spinbox(time_frame, from_=60, to=3600, textvariable=time_var, width=5).pack(side=tk.LEFT, padx=5)

        # 状态标签
        status_frame = ttk.Frame(dialog)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        status_label = ttk.Label(status_frame, text="请填写上述信息，然后点击「打开浏览器」按钮")
        status_label.pack(fill=tk.X)

        # 说明文本
        ttk.Label(dialog, text="1. 点击「打开浏览器」按钮\n2. 在打开的浏览器中登录或设置所需的Cookie\n3. 完成后关闭浏览器窗口或等待超时\n4. 点击「保存配置」按钮完成设置",
                 wraplength=480, justify=tk.LEFT).pack(padx=10, pady=10)

        # 按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # 浏览器实例和配置对象
        browser_data = {"driver": None, "profile": None}

        def open_browser():
            profile_name = name_var.get().strip()
            url = url_var.get().strip()
            wait_time = time_var.get()

            if not profile_name:
                messagebox.showerror("错误", "请输入配置文件名称", parent=dialog)
                return

            if not url.startswith("http"):
                messagebox.showerror("错误", "请输入有效的URL", parent=dialog)
                return

            # 禁用打开浏览器按钮，防止重复点击
            open_browser_btn.config(state=tk.DISABLED)
            status_label.config(text="正在打开浏览器...")

            # 创建配置文件对象
            profile = BrowserProfile(profile_name)
            browser_data["profile"] = profile

            def browser_thread():
                try:
                    # 创建浏览器但不自动保存
                    driver = profile._create_driver(headless=False)
                    browser_data["driver"] = driver

                    # 访问初始URL
                    driver.get(url)

                    # 更新UI状态
                    self.after(0, lambda: status_label.config(text="浏览器已打开，请在其中登录或设置Cookie"))
                    self.after(0, lambda: save_btn.config(state=tk.NORMAL))

                    # 等待用户操作或超时
                    timeout = time.time() + wait_time
                    while time.time() < timeout:
                        try:
                            # 检查浏览器是否仍然打开
                            if not browser_data["driver"]:
                                break
                            driver.current_url  # 如果浏览器已关闭会抛出异常
                            time.sleep(1)
                        except:
                            # 浏览器已关闭
                            browser_data["driver"] = None
                            self.after(0, lambda: status_label.config(text="浏览器已关闭，请点击「保存配置」按钮"))
                            break

                    # 如果超时
                    if time.time() >= timeout and browser_data["driver"]:
                        self.after(0, lambda: status_label.config(text="等待超时，请点击「保存配置」按钮"))

                except Exception as e:
                    self.after(0, lambda: status_label.config(text=f"打开浏览器出错: {e}"))
                    self.after(0, lambda: open_browser_btn.config(state=tk.NORMAL))
                    browser_data["driver"] = None

            threading.Thread(target=browser_thread, daemon=True).start()

        def save_profile():
            if browser_data["profile"] and browser_data["driver"]:
                try:
                    # 保存浏览器状态
                    status_label.config(text="正在保存配置...")
                    browser_data["profile"]._save_browser_state(browser_data["driver"])

                    # 关闭浏览器
                    browser_data["driver"].quit()
                    browser_data["driver"] = None

                    # 更新UI
                    self.update_profile_list()
                    self.profile_var.set(browser_data["profile"].profile_name)

                    # 关闭对话框
                    dialog.destroy()

                    # 更新主窗口状态
                    self.status_var.set("浏览器配置已保存")

                except Exception as e:
                    status_label.config(text=f"保存配置出错: {e}")
            else:
                if not browser_data["driver"]:
                    status_label.config(text="浏览器已关闭，正在保存配置...")
                    # 更新UI
                    self.update_profile_list()
                    if browser_data["profile"]:
                        self.profile_var.set(browser_data["profile"].profile_name)

                    # 关闭对话框
                    dialog.destroy()

                    # 更新主窗口状态
                    self.status_var.set("浏览器配置已保存")
                else:
                    status_label.config(text="无法保存配置，请先打开浏览器")

        def on_dialog_close():
            # 关闭浏览器（如果仍然打开）
            if browser_data["driver"]:
                try:
                    browser_data["driver"].quit()
                except:
                    pass
            dialog.destroy()

        # 创建按钮
        open_browser_btn = ttk.Button(button_frame, text="打开浏览器", command=open_browser)
        open_browser_btn.pack(side=tk.LEFT, padx=5)

        save_btn = ttk.Button(button_frame, text="保存配置", command=save_profile, state=tk.DISABLED)
        save_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="取消", command=on_dialog_close).pack(side=tk.RIGHT, padx=5)

        # 设置对话框关闭事件
        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

        # 居中显示对话框
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        dialog.wait_window()

    def delete_profile(self):
        """删除浏览器配置文件"""
        profile_name = self.profile_var.get()
        if not profile_name:
            messagebox.showinfo("提示", "请先选择一个配置文件")
            return

        if messagebox.askyesno("确认", f"确定要删除配置文件 '{profile_name}' 吗？"):
            if BrowserProfile.delete_profile(profile_name):
                logging.info(f"已删除配置文件: {profile_name}")
                self.profile_var.set("")
                self.update_profile_list()
            else:
                messagebox.showerror("错误", f"删除配置文件 '{profile_name}' 失败")

    def get_custom_keywords(self):
        """获取自定义关键词"""
        keywords_text = self.keywords_text.get("1.0", tk.END).strip()
        if keywords_text:
            return [kw.strip() for kw in keywords_text.split('\n') if kw.strip()]
        return []

    def start_crawler(self):
        """启动爬虫线程"""
        # 检查CSV文件
        csv_path = self.csv_path_var.get()
        if not csv_path:
            messagebox.showerror("错误", "请选择CSV文件")
            return

        if not os.path.exists(csv_path):
            messagebox.showerror("错误", f"CSV文件不存在: {csv_path}")
            return

        # 检查输出目录
        output_dir = self.output_dir_var.get()
        if not output_dir:
            messagebox.showerror("错误", "请指定输出目录")
            return

        # 确保输出目录存在
        ensure_directory(output_dir)

        # 获取设置
        headless = self.headless_var.get()
        similarity_threshold = self.similarity_var.get()
        scroll_count = self.scroll_count_var.get()
        delay = self.delay_var.get()
        custom_keywords = self.get_custom_keywords()
        profile_name = self.profile_var.get()

        # 重置停止事件
        self.stop_event.clear()

        # 更新UI状态
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("正在爬取...")

        # 启动爬虫线程
        self.crawler_thread = threading.Thread(
            target=self.run_crawler,
            args=(csv_path, output_dir, headless, similarity_threshold, scroll_count, delay, custom_keywords, profile_name),
            daemon=True
        )
        self.crawler_thread.start()

        logging.info("爬虫已启动")

    def run_crawler(self, csv_path, output_dir, headless, similarity_threshold, scroll_count, delay, custom_keywords, profile_name=None):
        """在线程中运行爬虫"""
        try:
            # 创建元素查找器
            element_finder = InteractionElementFinder(similarity_threshold=similarity_threshold)

            # 添加自定义关键词
            if custom_keywords:
                logging.info(f"添加自定义关键词: {', '.join(custom_keywords)}")
                element_finder.INTERACTION_KEYWORDS.extend(custom_keywords)

            # 创建爬虫
            crawler = WebCrawler(
                headless=headless,
                output_dir=output_dir,
                element_finder=element_finder,
                scroll_count=scroll_count,
                delay=delay,
                stop_event=self.stop_event,
                profile_name=profile_name if profile_name else None
            )

            # 如果使用了浏览器配置文件，记录日志
            if profile_name:
                logging.info(f"使用浏览器配置文件: {profile_name}")

            # 处理CSV文件
            crawler.process_csv(csv_path)

            # 关闭爬虫
            crawler.close_driver()

            if self.stop_event.is_set():
                logging.info("爬虫已手动停止")
            else:
                logging.info("爬虫已完成")

        except Exception as e:
            logging.error(f"爬虫出错: {e}")

        finally:
            # 更新UI状态
            self.after(0, self.crawler_finished)

    def crawler_finished(self):
        """爬虫完成后更新UI"""
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("就绪")

    def stop_crawler(self):
        """停止爬虫"""
        if self.crawler_thread and self.crawler_thread.is_alive():
            logging.info("正在停止爬虫...")
            self.stop_event.set()
            self.stop_button.config(state=tk.DISABLED)
            self.status_var.set("正在停止...")

    def on_closing(self):
        """关闭窗口时的处理"""
        if self.crawler_thread and self.crawler_thread.is_alive():
            if messagebox.askokcancel("退出", "爬虫正在运行，确定要退出吗？"):
                self.stop_event.set()
                self.destroy()
        else:
            self.destroy()

        # 恢复标准输出和标准错误
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

        # 停止文本重定向
        if hasattr(self, 'text_handler'):
            self.text_handler.stop()


if __name__ == "__main__":
    app = CrawlerGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
