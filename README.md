# 网页交互元素爬虫工具 (Web Interaction Element Crawler)

一个用于自动爬取网页中交互元素（如点赞、投票按钮等）的工具，支持GUI界面和命令行操作，可保存浏览器配置文件以处理需要登录的网站。

## 功能特点

- 🔍 自动识别网页中的交互元素（如点赞、投票、评论按钮等）
- 🖱️ 模拟点击交互元素并记录结果
- 📊 将爬取结果保存为JSON格式和网页截图
- 🔐 支持保存浏览器配置文件（包括cookies和登录状态）
- 📋 支持从CSV文件批量导入URL
- 🎛️ 提供图形用户界面(GUI)和命令行界面
- 🔧 高度可定制的参数设置

## 系统要求

- Python 3.8+
- Chrome浏览器

## 安装指南

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/crawler_for_attack.git
cd crawler_for_attack
```

### 2. 创建虚拟环境

使用uv（推荐）:

```bash
pip install uv
uv venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows
```

或使用标准venv:

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
uv pip install -r requirements.txt
# 或
pip install -r requirements.txt
```

## 使用方法

### 图形界面模式

启动GUI界面:

```bash
python run_gui.py
```

GUI界面提供以下功能:
- 选择CSV文件（包含要爬取的URL）
- 设置输出目录
- 调整爬虫参数（相似度阈值、滚动次数、延迟时间等）
- 添加自定义关键词
- 创建和管理浏览器配置文件
- 实时日志显示

### 命令行模式

```bash
python main.py path/to/urls.csv [--headless] [--output-dir OUTPUT_DIR]
```

参数说明:
- `path/to/urls.csv`: 包含URL列表的CSV文件路径
- `--headless`: 使用无头模式运行浏览器（不显示浏览器窗口）
- `--output-dir`: 指定输出目录，默认为"output"

## 浏览器配置文件

### 创建浏览器配置文件

1. 在GUI界面中，点击"管理配置文件"按钮
2. 输入配置文件名称
3. 点击"打开浏览器"按钮
4. 在打开的浏览器中登录或设置所需的cookies
5. 完成后点击"保存配置"按钮

### 使用浏览器配置文件

1. 在GUI界面中，从下拉菜单选择已创建的配置文件
2. 正常启动爬虫，它将使用所选配置文件中的cookies和登录状态

## CSV文件格式

CSV文件应包含URL列表，程序会自动识别包含URL的列。示例:

```csv
url,name,category
https://example.com/page1,Example 1,News
https://example.com/page2,Example 2,Blog
```

## 输出格式

爬虫会为每个处理的URL生成两个文件:

1. JSON文件: 包含找到的交互元素的详细信息
   ```json
   {
     "url": "https://example.com/page1",
     "timestamp": "20230101_120000",
     "elements_count": 2,
     "elements": [
       {
         "element_text": "Like",
         "element_tag": "button",
         "element_class": "like-button",
         "element_xpath": "//button[@class='like-button']",
         "match_type": "keyword_match",
         "match_keyword": "like"
       },
       ...
     ]
   }
   ```

2. PNG文件: 网页截图，显示找到的交互元素

## 自定义关键词

您可以在GUI界面中添加自定义关键词，每行一个。这些关键词将用于识别交互元素。

默认关键词包括:
- like
- vote
- upvote
- downvote
- 等等...

## 高级配置

### 相似度阈值

控制关键词匹配的灵活度（0-100）。较低的值会匹配更多元素，但可能包含误报；较高的值匹配更精确，但可能遗漏一些元素。

### 滚动次数

控制页面滚动的次数，用于加载懒加载元素。

### 延迟时间

URL之间的等待时间（秒），避免被网站检测为爬虫。

## 故障排除

### 浏览器驱动问题

程序会自动下载适合您Chrome版本的WebDriver。如果遇到问题，请确保您的Chrome浏览器是最新版本。

### 无法识别元素

如果爬虫无法识别某些交互元素:
1. 尝试降低相似度阈值
2. 添加自定义关键词
3. 检查元素是否使用了不常见的HTML结构

### 被网站封锁

如果遇到被网站封锁的情况:
1. 增加延迟时间
2. 使用浏览器配置文件
3. 避免短时间内爬取同一网站的大量页面

## 许可证

[MIT License](LICENSE)

## 贡献

欢迎提交问题报告和拉取请求！
