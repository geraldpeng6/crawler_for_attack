#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
爬虫程序入口，用于爬取网页中的交互元素
"""

import argparse
from web_crawler import WebCrawler


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
