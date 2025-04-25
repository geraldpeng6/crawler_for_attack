#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
爬虫GUI程序入口
"""

from gui import CrawlerGUI

if __name__ == "__main__":
    app = CrawlerGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
