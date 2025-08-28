import re
import json
import requests
import random
from bs4 import BeautifulSoup
import logging
from config import (
    DEEPSEEK_API_KEY, 
    HAS_TWITTER_CONFIG, 
    CAN_USE_TWITTER_API,
    DEEPSEEK_API_TIMEOUT, 
    DEEPSEEK_API_MAX_RETRIES,
    DEEPSEEK_API_RETRY_DELAY
)
try:
    from fake_useragent import UserAgent
except ImportError:
    UserAgent = None

# 引入Twitter API模块（如果配置了Twitter API）
try:
    from twitter_api import TwitterAPI, twitter_api
    HAS_TWEEPY = True
except ImportError:
    HAS_TWEEPY = False
    logger = logging.getLogger(__name__)
    logger.warning("无法导入tweepy库，请使用pip install tweepy安装")
else:
    logger = logging.getLogger(__name__)

def get_twitter_instructions():
    """返回处理Twitter内容的特别指示"""
    return "特别说明：对于Twitter/X推文，请特别注意：\n" + \
           "1. 将所有<<高亮内容>>标记之间的文本作为重要的关键点\n" + \
           "2. 将所有#标签作为标签(tags)\n" + \
           "3. 摘要应更简洁，重点概括推文内容和上下文\n" + \
           "4. 关键点应包含推文中的重要引述、数据和论点"

# logger = get_logger(__name__)

# 移除重复的函数定义，前面已经有一个完整的定义了

class ContentProcessor:
    def __init__(self):
        self.api_key = DEEPSEEK_API_KEY
        self.api_endpoint = "https://api.deepseek.com/v1/chat/completions"
        
        # API调用配置
        self.api_timeout = DEEPSEEK_API_TIMEOUT  # 秒
        self.max_retries = DEEPSEEK_API_MAX_RETRIES
        self.retry_delay = DEEPSEEK_API_RETRY_DELAY  # 初始延迟秒数
        
    def _get_twitter_content_via_api(self, url):
        """使用Twitter API直接获取推文内容（如果配置了API）"""
        if not CAN_USE_TWITTER_API or not HAS_TWEEPY:
            if not HAS_TWITTER_CONFIG:
                logger.info("未配置Twitter API，无法使用API获取推文")
            elif not CAN_USE_TWITTER_API:
                logger.info("Twitter API已禁用，如需启用请设置USE_TWITTER_API=true")
            else:
                logger.info("未安装tweepy库，无法使用API获取推文")
            return None
            
        try:
            # 使用Twitter API获取推文
            logger.info(f"尝试使用Twitter API直接获取推文: {url}")
            tweet_data = twitter_api.get_tweet_data(url)
            
            if tweet_data and isinstance(tweet_data, dict) and 'content' in tweet_data:
                logger.info(f"成功使用Twitter API获取推文内容")
                return tweet_data
            else:
                logger.warning("Twitter API返回数据为空或格式不正确")
                return None
        except Exception as e:
            logger.error(f"使用Twitter API获取推文时出错: {str(e)}")
            return None
    
    def _fetch_webpage_content(self, url):
        """从URL获取网页内容"""
        try:
            # 检查是否是Twitter/X.com链接
            is_twitter = "twitter.com" in url or "x.com" in url
            
            # 如果是Twitter/X链接且启用了Twitter API，优先尝试使用API获取内容
            if is_twitter and CAN_USE_TWITTER_API and HAS_TWEEPY:
                # 首先尝试使用Twitter API直接获取内容
                api_result = self._get_twitter_content_via_api(url)
                if api_result:
                    logger.info("成功使用Twitter API获取推文，跳过Web抓取")
                    return api_result
            
            # 配置随机延时范围
            min_delay = 1 if not is_twitter else 2
            max_delay = 3 if not is_twitter else 5
            
            # 准备多种User-Agent，模拟各种浏览器
            chrome_agents = [
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
            ]
            firefox_agents = [
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0'
            ]
            safari_agents = [
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
            ]
            mobile_agents = [
                'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36'
            ]
            
            # 根据链接类型选择合适的User-Agent组
            user_agents = []
            try:
                # 尝试使用fake-useragent库获取随机UA
                import random
                from fake_useragent import UserAgent
                ua = UserAgent()
                user_agents = [ua.chrome, ua.firefox, ua.safari]
            except:
                # 如果fake-useragent不可用，使用预定义的UA
                if is_twitter:
                    # 对于Twitter，优先使用Chrome和Firefox
                    user_agents = chrome_agents + firefox_agents
                else:
                    # 对于其他站点，使用所有UA
                    user_agents = chrome_agents + firefox_agents + safari_agents
                    # 部分站点可能可以用移动UA
                    if random.random() < 0.2:
                        user_agents += mobile_agents
            
            # 随机选择一个User-Agent
            user_agent = random.choice(user_agents)
            
            # 为X.com设置增强的headers，更接近真实浏览器
            if is_twitter:
                # 随机生成viewport尺寸，模拟不同屏幕
                viewport_width = random.randint(1200, 1920)
                viewport_height = random.randint(800, 1080)
                
                # 构建更真实的headers
                headers = {
                    'User-Agent': user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'cross-site',  # 模拟从其他站点访问
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0',
                    'dnt': '1',
                    'Sec-CH-UA': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
                    'Sec-CH-UA-Mobile': '?0',
                    'Sec-CH-UA-Platform': '"macOS"',
                    'Referer': random.choice(['https://www.google.com/', 'https://www.bing.com/', 'https://duckduckgo.com/']),
                    'Pragma': 'no-cache',
                    'viewport-width': str(viewport_width),
                    'device-memory': '8',
                }
                
                # 为X.com使用更长的超时时间
                timeout = random.randint(20, 30)
                logger.info(f"正在使用增强头信息访问X.com内容: {url}")
            else:
                # 对其他网站使用较简单的头信息
                headers = {
                    'User-Agent': user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0',
                }
                timeout = random.randint(10, 20)
            
            # 创建Session对象以维持cookies
            session = requests.Session()
            
            # 如果是X.com，先访问首页以获取必要的cookies
            if is_twitter:
                try:
                    logger.info("先访问X.com首页获取cookies")
                    # 尝试访问多个入口点以获取完整cookie集
                    entry_points = [
                        "https://x.com",
                        "https://twitter.com", 
                        "https://x.com/home",
                        "https://x.com/explore"
                    ]
                    
                    for entry in entry_points:
                        try:
                            logger.info(f"访问入口点: {entry}")
                            resp = session.get(entry, headers=headers, timeout=timeout)
                            if resp.status_code == 200:
                                logger.info(f"成功访问入口点并获取cookies: {entry}")
                                # 稍等一会，模拟真实用户行为
                                import time
                                time.sleep(random.uniform(min_delay, max_delay))
                        except Exception as e:
                            logger.warning(f"访问X.com入口点{entry}时出错: {str(e)}")
                    
                    # 模拟鼠标移动和页面滚动的行为（通过headers）
                    headers['X-Client-Data'] = 'eyJ1YSI6Ik1vemlsbGEvNS4wIChXaW5kb3dzIE5UIDEwLjA7IFdpbjY0OyB4NjQpIEFwcGxlV2ViS2l0LzUzNy4zNiAoS0hUTUwsIGxpa2UgR2Vja28pIENocm9tZS85Ni4wLjQ2NjQuMTEwIFNhZmFyaS81MzcuMzYiLCJicm93c2VyIjoiQ2hyb21lIiwiYnJvd3Nlcl92ZXJzaW9uIjoiOTYuMCIsIm9zIjoiV2luZG93cyIsIm9zX3ZlcnNpb24iOiIxMCIsImRldmljZSI6IiIsInJlZmVycmVyIjoiaHR0cHM6Ly93d3cuZ29vZ2xlLmNvbS8ifQ=='
                except Exception as e:
                    logger.warning(f"访问X.com首页时出错，继续尝试直接访问目标URL: {str(e)}")
            
            # 添加随机延时，模拟真实用户行为
            import time
            time.sleep(random.uniform(min_delay, max_delay))
            
            # 发送请求获取网页内容
            logger.info(f"正在请求URL: {url}")
            response = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            
            # 检测编码
            if response.encoding == 'ISO-8859-1':
                # 可能检测错误，尝试用更准确的方式检测
                encodings = requests.utils.get_encodings_from_content(response.text)
                if encodings:
                    response.encoding = encodings[0]
                else:
                    response.encoding = response.apparent_encoding
            
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 检查是否为X.com/Twitter并且返回了访问限制页面
            is_twitter = "twitter.com" in url or "x.com" in url
            if is_twitter:
                # 检查特定的错误信息，扩展错误文本集合
                error_texts = [
                    "隐私相关扩展",
                    "privacy extensions",
                    "Something went wrong",
                    "出了点问题",
                    "请尝试重新加载",
                    "try reloading",
                    "rate limit",
                    "too many requests",
                    "访问受限",
                    "access denied",
                    "blocked",
                    "blocked temporarily",
                    "try again later",
                    "稍后再试",
                    "login",
                    "登录以查看",
                    "sign in",
                    "too many connections"
                ]
                
                page_text = soup.get_text().lower()
                if any(text.lower() in page_text for text in error_texts):
                    logger.warning("检测到X.com访问限制页面，尝试备用方法...")
                    
                    # 尝试提取Twitter ID
                    twitter_id = None
                    username = None
                    
                    # 从URL中提取Twitter ID
                    if "/status/" in url:
                        # 提取用户名和推文ID
                        parts = url.split('/')
                        status_index = -1
                        for i, part in enumerate(parts):
                            if part == "status":
                                status_index = i
                                break
                        
                        if status_index > 0 and status_index + 1 < len(parts):
                            username = parts[status_index - 1]
                            twitter_id = parts[status_index + 1].split("?")[0]
                    # 尝试从URL中提取用户名和推文ID的其他方式
                    elif "x.com" in url or "twitter.com" in url:
                        parts = url.split('/')
                        if len(parts) >= 5:  # 足够长的URL可能包含用户名和ID
                            potential_id = parts[-1].split("?")[0]
                            if potential_id.isalnum():
                                twitter_id = potential_id
                                # 尝试提取用户名
                                if len(parts) >= 4:
                                    username = parts[-3]  # 假设URL格式为 twitter.com/username/status/id
                    
                    # 1. 首先尝试使用Twitter API（如果启用并配置了）
                    api_success = False
                    tweet_data = None
                    
                    if CAN_USE_TWITTER_API and HAS_TWEEPY and twitter_id and twitter_id.isalnum():
                        try:
                            logger.info(f"尝试使用Twitter API获取推文 ID: {twitter_id}")
                            # 使用已经初始化好的twitter_api实例
                            api = twitter_api
                            
                            # 构建完整的Twitter URL用于API调用
                            full_twitter_url = f"https://twitter.com/{username}/status/{twitter_id}" if username else url
                            logger.info(f"使用URL获取推文: {full_twitter_url}")
                            tweet_data = api.get_tweet_data(full_twitter_url)
                            
                            if tweet_data and isinstance(tweet_data, dict) and 'content' in tweet_data:
                                content_preview = tweet_data.get('content', '')
                                logger.info(f"成功从Twitter API获取推文内容: {content_preview[:50] if content_preview else '(无内容)'}")
                                
                                # 提取推文文本
                                tweet_text = tweet_data.get('content', '')
                                
                                # 提取用户信息
                                tweet_meta = tweet_data.get('tweet_meta', {})
                                user_name = tweet_meta.get('username', '')
                                user_display_name = tweet_meta.get('author', '')
                                
                                # 提取日期
                                created_at = tweet_meta.get('date', '')
                                
                                # 提取标签和提及
                                hashtags = tweet_meta.get('tags', [])
                                mentions = tweet_meta.get('mentions', [])
                                
                                # 创建一个简单的HTML结构，模拟从web获取的内容
                                html_content = f"""
                                <html>
                                <head><title>{user_display_name} (@{user_name}) / X</title></head>
                                <body>
                                    <div class="main-tweet">
                                        <div class="tweet-header">
                                            <span class="tweet-user">{user_display_name} (@{user_name})</span>
                                            <span class="tweet-date">{created_at}</span>
                                        </div>
                                        <div class="tweet-content">{tweet_text}</div>
                                        <div class="tweet-entities">
                                            {"<div class='tweet-hashtags'>#" + " #".join(hashtags) + "</div>" if hashtags else ""}
                                            {"<div class='tweet-mentions'>@" + " @".join(mentions) + "</div>" if mentions else ""}
                                        </div>
                                    </div>
                                </body>
                                </html>
                                """
                                
                                # 解析为BeautifulSoup对象
                                soup = BeautifulSoup(html_content, 'html.parser')
                                api_success = True
                                logger.info("成功使用Twitter API获取推文并创建内容结构")
                                
                                # 直接使用API返回的提取标签
                                hashtags = tweet_data.get('extracted_tags', [])
                        except Exception as e:
                            logger.error(f"使用Twitter API获取推文失败: {str(e)}")
                    else:
                        if not CAN_USE_TWITTER_API:
                            if not HAS_TWITTER_CONFIG:
                                logger.info("未配置Twitter API，跳过API获取步骤")
                            else:
                                logger.info("Twitter API已禁用，如需启用请设置USE_TWITTER_API=true")
                        elif not HAS_TWEEPY:
                            logger.info("未安装tweepy库，跳过API获取步骤")
                        elif not twitter_id:
                            logger.info("未能从URL中提取有效的推文ID，跳过API获取步骤")
                    
                    # 2. 如果Twitter API失败，尝试Nitter服务
                    if not api_success and twitter_id and twitter_id.isalnum():
                        try:
                            # 根据 status.d420.de 更新的健康的nitter实例列表
                            nitter_urls = [
                                f"https://xcancel.com/i/status/{twitter_id}",         # 99% 健康度
                                f"https://nuku.trabun.org/i/status/{twitter_id}",      # 98% 健康度
                                f"https://nitter.tiekoetter.com/i/status/{twitter_id}", # 24% 健康度
                                f"https://lightbrd.com/i/status/{twitter_id}",         # 94% 健康度
                                f"https://nitter.privacyredirect.com/i/status/{twitter_id}", # 91% 健康度
                                f"https://nitter.net/i/status/{twitter_id}",           # 93% 健康度
                                f"https://nitter.poast.org/i/status/{twitter_id}",     # 85% 健康度
                                f"https://nitter.space/i/status/{twitter_id}",         # 95% 健康度
                                f"https://nitter.kuuro.net/i/status/{twitter_id}",     # 83% 健康度
                            ]
                            
                            # 随机打乱顺序，避免总是访问同一个实例
                            import random
                            random.shuffle(nitter_urls)
                            
                            success = False
                            for nitter_url in nitter_urls:
                                try:
                                    logger.info(f"尝试使用Nitter替代服务: {nitter_url}")
                                    nitter_headers = {
                                        'User-Agent': random.choice(user_agents),
                                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                                        'Accept-Language': 'en-US,en;q=0.5',
                                        'Connection': 'keep-alive',
                                        'Upgrade-Insecure-Requests': '1',
                                    }
                                    nitter_resp = requests.get(nitter_url, headers=nitter_headers, timeout=15)
                                    if nitter_resp.status_code == 200:
                                        # 检查内容是否有效
                                        nitter_soup = BeautifulSoup(nitter_resp.content, 'html.parser')
                                        main_content = nitter_soup.select(".main-tweet") or nitter_soup.select("article")
                                        
                                        if main_content and len(nitter_soup.get_text()) > 200:
                                            soup = nitter_soup
                                            logger.info("成功从Nitter获取内容")
                                            success = True
                                            break
                                        else:
                                            logger.warning(f"Nitter返回页面但内容不足: {nitter_url}")
                                    else:
                                        logger.warning(f"Nitter服务返回非200状态码: {nitter_resp.status_code}")
                                except Exception as e:
                                    logger.warning(f"Nitter替代服务失败: {str(e)}")
                                    continue
                                
                                # 添加随机延时，避免快速连续请求
                                time.sleep(random.uniform(1, 3))
                            
                            # 如果所有Nitter实例都失败，记录错误
                            if not success and not api_success:  # 如果API也失败了
                                logger.error("所有备用方法均失败")
                        except Exception as e:
                            logger.error(f"尝试Nitter替代服务时出错: {str(e)}")
                    # 如果API已经成功获取，跳过Nitter
                    elif api_success:
                        logger.info("Twitter API已成功获取内容，跳过Nitter服务")
            
            # 检查是否是Twitter/X.com链接
            is_twitter = "twitter.com" in url or "x.com" in url or "nitter" in url
            
            # 移除不需要的元素
            for element in soup(["script", "style", "nav", "footer", "iframe", "noscript", "aside"] + ([] if is_twitter else ["header"])):
                element.extract()
            
            # 提取标题 (尝试多种方法)
            title = "未知标题"
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
            elif soup.find("meta", property="og:title"):
                meta_tag = soup.find("meta", property="og:title")
                if meta_tag and hasattr(meta_tag, "get"):
                    title = meta_tag.get("content", "未知标题") # pyright: ignore[reportAttributeAccessIssue]
                else:
                    title = "未知标题"
            elif soup.find("h1"):
                title = soup.find("h1").get_text().strip() # pyright: ignore[reportOptionalMemberAccess]
            
            # 清理标题
            if isinstance(title, str):
                # 对于Nitter服务，清理标题中的"/ Twitter"或"/ X"
                title = re.sub(r'\s*[/|]\s*(Twitter|X|推特).*$', '', title)
            
            # 获取主要内容
            content = ""
            hashtags = []  # 用于存储X.com/Twitter的#标签
            mentions = []  # 用于存储@提及
            dollar_tags = []  # 用于存储$开头的标签
            
            # 检查是否是Twitter/X.com链接
            is_twitter = "twitter.com" in url or "x.com" in url or "nitter" in url
            
            # 如果是Twitter/X.com链接，尝试提取标签和高亮内容
            if is_twitter:
                # 提取所有带#的标签和@提及
                all_text = soup.get_text()
                hashtag_matches = re.findall(r'#(\w+)', all_text)
                mention_matches = re.findall(r'@(\w+)', all_text)
                
                if hashtag_matches:
                    hashtags.extend(hashtag_matches)
                    logger.info(f"从Twitter/X提取到标签: {hashtags}")
                
                if mention_matches:
                    mentions.extend(mention_matches)
                    logger.info(f"从Twitter/X提取到提及: {mentions}")
                
                # 检查是否是从nitter获取的内容
                is_nitter = "nitter" in url
                
                # 针对不同来源使用不同的选择器
                if is_nitter:
                    tweet_content_selectors = [
                        ".tweet-content", 
                        ".main-tweet .tweet-content", 
                        ".timeline-item .tweet-content",
                        "article .tweet-content",
                        ".main-tweet",
                        "article"
                    ]
                    # 从nitter特别提取标签
                    hashtag_elements = soup.select(".tweet-content .hashtag, .main-tweet .hashtag")
                    for elem in hashtag_elements:
                        tag_text = elem.get_text().strip()
                        if tag_text.startswith('#'):
                            tag = tag_text[1:]  # 移除#符号
                            if tag and tag not in hashtags:
                                hashtags.append(tag)
                                
                    # 从nitter特别提取提及
                    mention_elements = soup.select(".tweet-content .tweet-link, .main-tweet .tweet-link")
                    for elem in mention_elements:
                        mention_text = elem.get_text().strip()
                        if mention_text.startswith('@'):
                            mention = mention_text[1:]  # 移除@符号
                            if mention and mention not in mentions:
                                mentions.append(mention)
                else:
                    # X.com原始网站的选择器
                    tweet_content_selectors = [
                        "div[data-testid='tweetText']", 
                        "article[data-testid='tweet']", 
                        "div[lang]",
                        "p.tweet-text",
                        "div.tweet-content",
                        # 新版X.com的选择器
                        "article div[lang]",
                        "div[role='article']",
                        "[data-testid='tweet'] div[dir='auto']"
                    ]
                    
                    # 特别提取X.com的标签和提及
                    hashtag_elements = soup.select("a[href*='hashtag']")
                    for elem in hashtag_elements:
                        tag_text = elem.get_text().strip()
                        if tag_text.startswith('#'):
                            tag = tag_text[1:]
                            if tag and tag not in hashtags:
                                hashtags.append(tag)
                    
                    mention_elements = soup.select("a[href*='/status/'] span, a[href^='/']")
                    for elem in mention_elements:
                        mention_text = elem.get_text().strip()
                        if mention_text.startswith('@'):
                            mention = mention_text[1:]
                            if mention and mention not in mentions and len(mention) > 1:
                                mentions.append(mention)
                
                # 查找推文正文内容
                tweet_content = None
                tweet_text_full = ""
                
                # 首先尝试各种选择器找到主要内容
                for selector in tweet_content_selectors:
                    tweet_elements = soup.select(selector)
                    if tweet_elements:
                        # 使用最长的内容块作为推文内容
                        tweet_content = max(tweet_elements, key=lambda x: len(x.get_text()))
                        tweet_text_full = tweet_content.get_text().strip()
                        logger.info(f"找到推文内容，长度: {len(tweet_text_full)}")
                        break
                
            # 如果找到推文内容，提取其中的关键信息
            if tweet_content:
                # 尝试查找引用或高亮的文本（扩展选择器范围）
                quote_elements = tweet_content.select(
                    "blockquote, em, strong, b, span[style*='bold'], span[style*='font-weight'], " + 
                    "span.r-b88u0q, div.r-1s2bzr4, span[style*='italic'], " + 
                    "span.css-901oao, div.css-1dbjc4n, span[aria-hidden='true']"
                )
                
                # 查找引用的推文
                quoted_tweet = soup.select("div[role='link'][tabindex='0'], div.quoted-tweet, " + 
                                          "div.css-1dbjc4n[role='link'], div.main-tweet-quoted-tweet")
                
                highlights = []
                
                # 处理高亮元素
                for elem in quote_elements:
                    text = elem.get_text().strip()
                    if text and len(text) > 8:  # 降低长度限制以捕获更多高亮内容
                        # 检查是否已经有类似的高亮内容
                        is_duplicate = False
                        for existing in highlights:
                            # 如果现有高亮是当前文本的子串，或反之，则认为是重复的
                            if text in existing or existing in text:
                                is_duplicate = True
                                # 如果当前文本更长，替换现有的
                                if len(text) > len(existing):
                                    highlights.remove(existing)
                                    highlights.append(text)
                                break
                        
                        if not is_duplicate:
                            highlights.append(text)                    # 处理引用的推文
                    for elem in quoted_tweet:
                        quoted_text = elem.get_text().strip()
                        if quoted_text and len(quoted_text) > 20:  # 引用推文通常较长
                            # 添加特殊标记表明这是引用的推文
                            highlights.append(f"引用推文: {quoted_text[:200]}")
                    
                    # 记录高亮内容用于关键点
                    if highlights:
                        logger.info(f"找到高亮内容: {len(highlights)}个")
                        # 将这些高亮内容添加到content而不是直接修改soup
                        for highlight in highlights:
                            # 将高亮内容追加到content，使用明确的标记便于AI识别
                            content += f"\n\n<<高亮内容>> {highlight} <<高亮结束>>"
            
            # 尝试获取主要内容区域
            main_content = None
            selectors = ["main", "article"]
            
            # 对于Twitter/X.com添加更具体的选择器
            if is_twitter:
                selectors = ["div[data-testid='tweetText']", "article[data-testid='tweet']"] + selectors
                
            # 添加通用选择器
            selectors += ["div[class*='content']", "div[class*='article']", "div[id*='content']", "div[id*='article']"]
            
            for tag in selectors:
                elements = soup.select(tag)
                if elements:
                    # 选择最长的内容块
                    main_content = max(elements, key=lambda x: len(x.get_text()))
                    break
            
            # 如果是Twitter/X内容，使用特殊的内容提取方法
            if is_twitter:
                # 如果已经通过推文内容提取器找到了主要内容，直接使用
                if tweet_text_full and len(tweet_text_full) > 50:
                    # 如果已有content（从高亮内容中提取的），则加入主要推文内容
                    if content:
                        content = f"推文内容: {tweet_text_full}\n\n" + content
                    else:
                        content = tweet_text_full
                else:
                    # 尝试使用更特定的Twitter内容提取方法
                    twitter_content = []
                    
                    # 针对不同Twitter页面结构的选择器
                    content_selectors = [
                        "div[data-testid='tweetText']", 
                        "article[data-testid='tweet']", 
                        "div.tweet-content",
                        ".main-tweet",
                        "div.timeline-item .tweet-content"
                    ]
                    
                    for selector in content_selectors:
                        elements = soup.select(selector)
                        if elements:
                            for elem in elements:
                                text = elem.get_text().strip()
                                if text and len(text) > 30:
                                    twitter_content.append(text)
                    
                    if twitter_content:
                        content = "推文内容: " + "\n\n".join(twitter_content) + "\n\n" + content
            
            # 如果找到主要内容区域（或者不是Twitter内容），就使用它
            if main_content and (not is_twitter or not content):
                # 删除可能的干扰元素
                for element in main_content(["header", "footer", "nav", "aside", "div[class*='comment']"]):
                    element.extract()
                    
                # 提取段落
                paragraphs = []
                for p in main_content.find_all(["p", "h2", "h3", "h4", "li", "blockquote"]):
                    text = p.get_text().strip()
                    if len(text) > 15:  # 稍微降低长度阈值，以捕获更多内容
                        paragraphs.append(text)
                
                # 如果是Twitter但已有内容，则添加到现有内容；否则直接赋值
                if is_twitter and content:
                    content += "\n\n" + "\n\n".join(paragraphs)
                else:
                    content = "\n\n".join(paragraphs)
            
            # 如果没有找到或提取到的内容太少，则回退到整个页面
            if not content or len(content) < 150:  # 降低阈值以避免放弃太多内容
                # 提取所有段落
                paragraphs = []
                for p in soup.find_all(["p", "h1", "h2", "h3", "h4", "li", "blockquote"]):
                    text = p.get_text().strip()
                    if len(text) > 15:  # 降低长度阈值
                        paragraphs.append(text)
                
                # 如果已有内容，则添加；否则直接赋值
                if content and paragraphs:
                    content += "\n\n" + "\n\n".join(paragraphs)
                elif paragraphs:
                    content = "\n\n".join(paragraphs)
            
            # 如果仍然没有足够内容，使用整个页面文本
            if not content or len(content) < 150:
                content = soup.get_text(separator='\n', strip=True)
            
            # 清理多余空白并增强内容结构
            content = '\n\n'.join(line.strip() for line in content.split('\n') if line.strip())
            
            # 提取内容中以$和#开头的文本作为标签
            extracted_special_tags = []
            
            # 提取#标签（不仅限于Twitter/X内容）
            general_hashtag_matches = re.findall(r'#(\w+)', content)
            if general_hashtag_matches:
                for tag in general_hashtag_matches:
                    if tag and len(tag) > 1 and tag.lower() not in [t.lower() for t in extracted_special_tags]:
                        extracted_special_tags.append(tag)
                        
            # 提取$标签
            dollar_tag_matches = re.findall(r'\$(\w+)', content)
            if dollar_tag_matches:
                for tag in dollar_tag_matches:
                    if tag and len(tag) > 1 and tag.lower() not in [t.lower() for t in extracted_special_tags]:
                        extracted_special_tags.append(tag)
            
            logger.info(f"从内容中提取到的特殊标签(#和$): {extracted_special_tags}")
            
            # 提取网站来源
            source = url.split("//")[-1].split("/")[0]
            
            # 处理Twitter/X特定的元数据
            extracted_tags = []
            extracted_mentions = []
            tweet_meta = {}
            
            if is_twitter:
                # 处理提取的标签
                if hashtags:
                    # 去重复、去空值、最多取8个标签
                    extracted_tags = list(set([tag.lower() for tag in hashtags if tag and len(tag) > 1]))[:8]
                    logger.info(f"从Twitter/X成功提取到标签: {extracted_tags}")
                
                # 处理提取的@提及
                if mentions:
                    # 去重复、去空值
                    extracted_mentions = list(set([mention for mention in mentions if mention and len(mention) > 1]))[:5]
                    logger.info(f"从Twitter/X成功提取到提及: {extracted_mentions}")
                
                # 创建tweet元数据
                tweet_meta = {
                    "platform": "Twitter" if "twitter.com" in url else "X",
                    "tags": extracted_tags,
                    "mentions": extracted_mentions
                }
                
                # 如果是nitter服务，记录实际来源
                if "nitter" in url:
                    tweet_meta["via"] = "nitter"
                
                # 尝试提取推文日期（如果可用）
                try:
                    date_elements = soup.select("span.tweet-date, a.tweet-date, span.css-1dbjc4n time, time")
                    if date_elements:
                        for date_elem in date_elements:
                            if date_elem.has_attr('datetime'):
                                tweet_meta["date"] = date_elem['datetime']
                                break
                            elif date_elem.has_attr('title'):
                                tweet_meta["date"] = date_elem['title']
                                break
                            else:
                                date_text = date_elem.get_text().strip()
                                if date_text and (":" in date_text or "/" in date_text or "-" in date_text):
                                    tweet_meta["date"] = date_text
                                    break
                except Exception as e:
                    logger.warning(f"提取推文日期时出错: {str(e)}")
                
                # 设置来源为Twitter/X
                source = "Twitter" if "twitter.com" in url else "X"
            
            logger.info(f"成功提取网页内容，标题: {title}, 内容长度: {len(content)}")
            
            # 构建返回数据
            return_data = {
                "title": title,
                "content": content[:20000],  # 增加上限以包含更多推文内容
                "url": url,
                "source": source,
                "extracted_tags": extracted_tags,
                "special_tags": extracted_special_tags  # 添加提取的$和#标签
            }
            
            # 添加Twitter元数据
            if is_twitter and tweet_meta:
                return_data["tweet_meta"] = tweet_meta
            
            return return_data
        except Exception as e:
            logger.error(f"获取网页内容失败: {str(e)}")
            return {
                "title": "获取失败",
                "content": f"无法获取内容: {str(e)}",
                "url": url,
                "source": url.split("//")[-1].split("/")[0] if "//" in url else url
            }
    
    def process_link(self, url):
        """处理链接并返回结构化内容"""
        # 获取网页内容
        webpage_data = self._fetch_webpage_content(url)
        
        # 检查是否成功获取内容
        if not webpage_data.get("content") or len(webpage_data["content"]) < 100:
            logger.warning(f"获取网页内容不足或为空: {url}")
            return {
                "title": webpage_data.get("title", "无法获取标题"),
                "summary": "无法获取足够的网页内容进行分析。可能是网站访问受限、需要登录，或内容格式特殊。",
                "key_points": ["无法获取内容", "请检查URL是否正确", "尝试手动访问网页查看是否可正常浏览"],
                "tags": ["访问失败", "内容缺失"],
                "related_links": [],
                "source": webpage_data.get("source", url.split("//")[-1].split("/")[0] if "//" in url else url),
                "original_url": url
            }
        
        # 使用DeepSeek API分析内容
        # 检查是否是X.com (Twitter)链接
        is_twitter = "twitter.com" in url or "x.com" in url or "nitter" in url
        
        # 处理网页内容，对于Twitter内容特别处理
        content_to_analyze = webpage_data['content'][:10000]
        
        # 准备额外的Twitter/X特定信息
        twitter_info = ""
        if is_twitter:
            if webpage_data.get('extracted_tags'):
                twitter_info += f"\n推文标签: #{' #'.join(webpage_data['extracted_tags'])}"
            
            # 添加推文元数据信息
            if webpage_data.get('tweet_meta'):
                tweet_meta = webpage_data['tweet_meta']
                
                # 添加提及信息
                if tweet_meta.get('mentions'):
                    twitter_info += f"\n推文提及: @{' @'.join(tweet_meta['mentions'])}"
                
                # 添加日期信息
                if tweet_meta.get('date'):
                    twitter_info += f"\n推文日期: {tweet_meta['date']}"
                
                # 添加来源信息
                if tweet_meta.get('via'):
                    twitter_info += f"\n获取途径: 通过{tweet_meta['via']}服务获取"
        
        prompt = f"""
        请根据以下{'推文' if is_twitter else '网页'}内容进行详细分析，提取重要信息并以结构化JSON格式返回:
        
        {'推文' if is_twitter else '网页'}标题: {webpage_data['title']}
        URL: {webpage_data['url']}
        {twitter_info}
        
        {'推文' if is_twitter else '网页'}内容:
        {content_to_analyze}
        
        请提取以下信息，并以严格的JSON格式返回:
        1. 主题(title): {'推文' if is_twitter else '内容'}的主要标题或主题 (50字以内)
        2. 摘要(summary): {'推文' if is_twitter else '内容'}的主要内容概括 (200-300字)
        3. 关键点(key_points): {'推文' if is_twitter else '内容'}中的关键点列表（至少3-5个）
        4. 标签(tags): 3-5个与{'推文' if is_twitter else '内容'}相关的标签词
        5. 相关链接(related_links): {'推文' if is_twitter else '内容'}中提到的相关链接和对应描述 (如果有)
        6. 来源(source): 内容的原始来源{' (对于推文，应为"Twitter" 或 "X")' if is_twitter else '网站名称'}
        
        {get_twitter_instructions() if is_twitter else ""}
        
        你的回复必须是有效的JSON格式，不要有任何前缀或后缀说明。使用以下结构：
        {{
          "title": "主题",
          "summary": "摘要内容",
          "key_points": ["关键点1", "关键点2", "关键点3", "关键点4", "关键点5"],
          "tags": ["标签1", "标签2", "标签3", "标签4"],
          "related_links": [
            {{"url": "链接1", "description": "链接1描述"}},
            {{"url": "链接2", "description": "链接2描述"}}
          ],
          "source": "来源网站名称"
        }}
        
        若某项信息不存在，请使用合理默认值，例如空数组[]或适当的占位文本。
        确保JSON格式完全正确，可以被JSON解析器直接解析。
        """
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,  # 降低温度以获取更一致的输出
                "response_format": {"type": "json_object"}  # 要求模型返回JSON格式
            }
            
            # 添加重试机制
            max_retries = DEEPSEEK_API_MAX_RETRIES
            retry_delay = DEEPSEEK_API_RETRY_DELAY  # 初始延迟时间
            success = False
            last_error = None
            
            for retry in range(max_retries):
                if retry > 0:
                    logger.warning(f"DeepSeek API请求失败，正在进行第{retry}次重试 (延迟{retry_delay}秒): {str(last_error) if last_error else '未知错误'}")
                    import time
                    time.sleep(retry_delay)
                    # 增加重试延迟
                    retry_delay *= 2
                
                try:
                    logger.info(f"正在发送请求到DeepSeek API分析内容{' (重试)' if retry > 0 else ''}")
                    response = requests.post(
                        self.api_endpoint,
                        headers=headers,
                        json=payload,
                        timeout=DEEPSEEK_API_TIMEOUT  # 使用配置的超时时间
                    )
                    response.raise_for_status()
                    success = True
                    break
                except requests.exceptions.Timeout as e:
                    last_error = e
                    logger.warning(f"DeepSeek API请求超时 (已用{retry+1}/{max_retries}次重试): {str(e)}")
                    if retry == max_retries - 1:  # 如果是最后一次重试
                        raise  # 重新抛出当前异常
                except requests.exceptions.RequestException as e:
                    last_error = e
                    logger.warning(f"DeepSeek API请求异常 (已用{retry+1}/{max_retries}次重试): {str(e)}")
                    if retry == max_retries - 1:  # 如果是最后一次重试
                        raise  # 重新抛出当前异常
            
            if not success:
                # 如果没有成功且没有抛出异常，创建一个新的异常
                raise requests.exceptions.RequestException("DeepSeek API请求失败，所有重试均未成功")
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            
            logger.info(f"收到DeepSeek API响应，尝试解析JSON内容")
            
            # 预处理返回的内容，移除可能包含的代码块标记
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # 尝试解析返回的JSON
            try:
                parsed_data = json.loads(content)
                # 添加原始URL信息和来源
                parsed_data["original_url"] = webpage_data["url"]
                if not parsed_data.get("source") or parsed_data["source"] == "来源网站名称":
                    parsed_data["source"] = webpage_data.get("source", url.split("//")[-1].split("/")[0])
                
                # 确保所有必要字段都存在
                if not parsed_data.get("title"):
                    parsed_data["title"] = webpage_data["title"]
                
                if not parsed_data.get("summary"):
                    parsed_data["summary"] = "未能生成摘要，请查看原文。"
                
                if not parsed_data.get("key_points") or len(parsed_data["key_points"]) == 0:
                    parsed_data["key_points"] = ["未能提取关键点，请查看原文获取详细信息。"]
                
                # 处理特殊标签（$和#开头的文本）
                special_tags = webpage_data.get("special_tags", [])
                if special_tags:
                    logger.info(f"找到特殊标签(#和$): {special_tags}")
                    # 如果已有标签，添加特殊标签；如果没有标签，则使用特殊标签
                    if parsed_data.get("tags") and len(parsed_data["tags"]) > 0:
                        # 添加特殊标签，避免重复
                        for tag in special_tags:
                            if tag.lower() not in [t.lower() for t in parsed_data["tags"]]:
                                parsed_data["tags"].append(tag)
                    else:
                        parsed_data["tags"] = special_tags
                
                # 如果仍然没有标签，使用其他方法
                if not parsed_data.get("tags") or len(parsed_data["tags"]) == 0:
                    # 首先尝试使用提取到的Twitter/X标签
                    if webpage_data.get("extracted_tags") and webpage_data["extracted_tags"]:
                        parsed_data["tags"] = webpage_data["extracted_tags"]
                        logger.info(f"使用从Twitter/X提取的标签: {parsed_data['tags']}")
                    # 如果有tweet_meta数据且包含标签
                    elif webpage_data.get("tweet_meta") and webpage_data["tweet_meta"].get("tags"):
                        parsed_data["tags"] = webpage_data["tweet_meta"]["tags"]
                        logger.info(f"使用从tweet_meta中提取的标签: {parsed_data['tags']}")
                    else:
                        # 提取域名作为默认标签
                        domain = url.split("//")[-1].split("/")[0]
                        parsed_data["tags"] = [domain.split(".")[-2] if len(domain.split(".")) > 1 else domain]
                        
                        # 如果是Twitter/X链接，添加twitter或x作为标签
                        if is_twitter:
                            parsed_data["tags"].append("twitter" if "twitter.com" in url else "x")
                
                if not parsed_data.get("related_links"):
                    parsed_data["related_links"] = []
                
                logger.info(f"成功解析内容数据: 标题='{parsed_data['title'][:30]}...', 标签数量={len(parsed_data['tags'])}")
                return parsed_data
                
            except json.JSONDecodeError as e:
                # 如果返回的不是有效JSON，尝试从文本中提取
                logger.warning(f"API返回的不是有效JSON，尝试从文本中提取: {str(e)}")
                return self._extract_data_from_text(content, webpage_data["url"])
                
        except requests.exceptions.Timeout as e:
            logger.error(f"处理链接内容失败 - DeepSeek API 请求超时: {str(e)}")
            # 记录当前的超时配置
            logger.info(f"当前 API 超时设置: {self.api_timeout}秒，建议适当增加 DEEPSEEK_API_TIMEOUT 值")
            
            return {
                "title": webpage_data.get("title", "处理超时"),
                "summary": f"DeepSeek API 请求超时 ({self.api_timeout}秒)。这可能是由于网络问题或 API 服务器负载过高导致的。请稍后重试或考虑增加 DEEPSEEK_API_TIMEOUT 环境变量的值。",
                "key_points": ["API 请求超时", f"已尝试 {self.max_retries} 次重试", "可能是网络问题或服务器负载高"],
                "tags": ["API超时", "处理错误", webpage_data.get("source", "未知来源")],
                "related_links": [],
                "source": webpage_data.get("source", url.split("//")[-1].split("/")[0] if "//" in url else url),
                "original_url": url
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"处理链接内容失败 - DeepSeek API 连接错误: {str(e)}")
            # 尝试检查 API 连接
            connection_status, error_details = self._check_api_connection()
            connection_message = "API 连接测试:" + ("成功" if connection_status else f"失败 ({error_details})")
            
            return {
                "title": webpage_data.get("title", "连接失败"),
                "summary": f"无法连接到 DeepSeek API 服务器。这可能是由于网络问题、防火墙设置或 API 服务中断导致的。{connection_message}",
                "key_points": ["无法连接到 API 服务器", connection_message, "请检查网络连接和防火墙设置"],
                "tags": ["连接错误", "处理失败", webpage_data.get("source", "未知来源")],
                "related_links": [],
                "source": webpage_data.get("source", url.split("//")[-1].split("/")[0] if "//" in url else url),
                "original_url": url
            }
        except Exception as e:
            logger.error(f"处理链接内容失败: {str(e)}")
            
            # 根据错误类型提供更详细的信息
            error_type = type(e).__name__
            error_message = str(e)
            
            # 准备错误摘要
            error_summary = f"处理内容时出错 ({error_type}): {error_message}"
            
            # 准备键点，根据错误类型提供建议
            key_points = ["无法提取关键点"]
            if "JSON" in error_type or "json" in error_message.lower():
                key_points.append("API 返回的数据格式可能有问题")
                key_points.append("尝试检查 DeepSeek API 服务状态")
            elif "auth" in error_message.lower() or "认证" in error_message:
                key_points.append("API 认证可能失败")
                key_points.append("请检查 DEEPSEEK_API_KEY 环境变量是否正确设置")
            else:
                key_points.append(f"错误类型: {error_type}")
                key_points.append("请检查日志获取更详细信息")
            
            return {
                "title": webpage_data.get("title", "处理失败"),
                "summary": error_summary,
                "key_points": key_points,
                "tags": ["处理错误", error_type, webpage_data.get("source", "未知来源")],
                "related_links": [],
                "source": webpage_data.get("source", url.split("//")[-1].split("/")[0] if "//" in url else url),
                "original_url": url
            }
    
    def _check_api_connection(self):
        """检查 DeepSeek API 连接状态"""
        try:
            test_headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 使用一个简单的请求测试连接
            test_payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "user", "content": "Hello"}
                ],
                "max_tokens": 5
            }
            
            logger.info("正在测试 DeepSeek API 连接...")
            response = requests.post(
                self.api_endpoint,
                headers=test_headers,
                json=test_payload,
                timeout=10  # 使用较短的超时时间进行测试
            )
            
            if response.status_code == 200:
                logger.info("✅ DeepSeek API 连接正常")
                return True, "连接正常"
            else:
                error_msg = f"API 返回非200状态码: {response.status_code}"
                logger.warning(f"⚠️ DeepSeek API 连接测试失败: {error_msg}")
                return False, error_msg
                
        except requests.exceptions.Timeout:
            error_msg = "API 请求超时"
            logger.warning(f"⚠️ DeepSeek API 连接超时")
            return False, error_msg
        except requests.exceptions.ConnectionError:
            error_msg = "无法连接到 API 服务器"
            logger.warning(f"⚠️ DeepSeek API 连接错误: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            logger.warning(f"⚠️ DeepSeek API 连接测试出现异常: {error_msg}")
            return False, error_msg
            
    def _extract_data_from_text(self, text, url):
        """从文本中提取结构化数据"""
        logger.info("尝试从非JSON文本中提取结构化数据")
        
        # 定义默认结果
        data = {
            "title": "未知标题",
            "summary": "",
            "key_points": [],
            "tags": [],
            "related_links": [],
            "source": url.split("//")[-1].split("/")[0] if "//" in url else url,
            "original_url": url
        }
        
        # 如果文本太短，直接返回默认值
        if len(text) < 20:
            logger.warning("文本太短，无法提取有效信息")
            data["summary"] = "文本内容不足，无法提取有效信息。"
            return data
        
        # 分割成行进行处理
        lines = text.split('\n')
        
        # 首先尝试查找常见的字段标记
        title_patterns = [
            r'"title"\s*:\s*"([^"]+)"',
            r'"主题"\s*:\s*"([^"]+)"',
            r'主题[:：]\s*(.+)',
            r'标题[:：]\s*(.+)',
            r'title[:：]\s*(.+)'
        ]
        
        summary_patterns = [
            r'"summary"\s*:\s*"([^"]+)"',
            r'"摘要"\s*:\s*"([^"]+)"',
            r'摘要[:：]\s*(.+)',
            r'summary[:：]\s*(.+)'
        ]
        
        source_patterns = [
            r'"source"\s*:\s*"([^"]+)"',
            r'"来源"\s*:\s*"([^"]+)"',
            r'来源[:：]\s*(.+)',
            r'source[:：]\s*(.+)'
        ]
        
        # 提取标题
        for pattern in title_patterns:
            for line in lines:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    data["title"] = match.group(1).strip()
                    break
            if data["title"] != "未知标题":
                break
        
        # 提取摘要
        combined_text = " ".join(lines)
        for pattern in summary_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                data["summary"] = match.group(1).strip()
                break
        
        # 如果没有找到摘要，尝试查找摘要部分
        if not data["summary"]:
            summary_section_found = False
            summary_lines = []
            
            for i, line in enumerate(lines):
                if re.search(r'摘要[:：]|summary[:：]', line, re.IGNORECASE):
                    summary_section_found = True
                    continue
                
                if summary_section_found:
                    if re.search(r'关键点|key points|tags|标签|相关链接|related links', line, re.IGNORECASE):
                        summary_section_found = False
                    else:
                        clean_line = line.strip()
                        if clean_line and not clean_line.startswith('"') and not clean_line.startswith('{'):
                            summary_lines.append(clean_line)
            
            if summary_lines:
                data["summary"] = " ".join(summary_lines)
        
        # 提取来源
        for pattern in source_patterns:
            for line in lines:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    data["source"] = match.group(1).strip()
                    break
            if data["source"] != url.split("//")[-1].split("/")[0]:
                break
        
        # 提取关键点
        key_points_section = False
        for line in lines:
            line = line.strip()
            
            # 检查是否是关键点部分的开始
            if re.search(r'关键点[:：]|key[_ ]points[:：]', line, re.IGNORECASE):
                key_points_section = True
                continue
            
            # 检查是否到达了关键点部分的结束
            if key_points_section and re.search(r'tags|标签|相关链接|related links|来源|source', line, re.IGNORECASE):
                key_points_section = False
                continue
            
            # 提取关键点
            if key_points_section:
                # 检查是否是列表项
                if line.startswith('-') or line.startswith('*') or re.match(r'^\d+\.', line):
                    point = re.sub(r'^[-*\d.]+\s*', '', line).strip()
                    if point and len(point) > 5:  # 忽略太短的点
                        data["key_points"].append(point)
                # 检查是否在JSON数组格式中
                elif '"' in line and not (line.startswith('{') or line.startswith('[')):
                    # 提取引号中的内容
                    match = re.search(r'"([^"]+)"', line)
                    if match:
                        point = match.group(1).strip()
                        if point and len(point) > 5:
                            data["key_points"].append(point)
        
        # 提取标签
        tags_section = False
        for line in lines:
            line = line.strip()
            
            # 检查是否是标签部分的开始
            if re.search(r'标签[:：]|tags[:：]', line, re.IGNORECASE):
                tags_section = True
                
                # 检查是否在同一行包含标签
                tags_part = re.sub(r'^标签[:：]|^tags[:：]', '', line, flags=re.IGNORECASE).strip()
                if tags_part:
                    # 尝试从JSON数组格式提取
                    if '[' in tags_part and ']' in tags_part:
                        try:
                            tags_str = tags_part[tags_part.find('['):tags_part.find(']')+1]
                            tags_list = json.loads(tags_str)
                            if isinstance(tags_list, list):
                                data["tags"] = [str(tag).strip() for tag in tags_list if tag]
                                tags_section = False  # 已找到标签，停止搜索
                        except:
                            pass
                    
                    # 否则尝试按逗号分割
                    if not data["tags"]:
                        data["tags"] = [tag.strip() for tag in re.split(r'[,，、]', tags_part) if tag.strip()]
                        if data["tags"]:
                            tags_section = False  # 已找到标签，停止搜索
                
                continue
            
            # 检查是否到达了标签部分的结束
            if tags_section and re.search(r'相关链接|related links|来源|source|key[_ ]points|关键点', line, re.IGNORECASE):
                tags_section = False
                continue
            
            # 提取标签
            if tags_section:
                # 检查是否在JSON数组格式中
                if '[' in line and ']' in line:
                    try:
                        tags_str = line[line.find('['):line.find(']')+1]
                        tags_list = json.loads(tags_str)
                        if isinstance(tags_list, list):
                            data["tags"] = [str(tag).strip() for tag in tags_list if tag]
                            tags_section = False  # 已找到标签，停止搜索
                    except:
                        pass
                
                # 否则尝试按逗号分割或提取引号中的内容
                elif '"' in line or ',' in line:
                    # 提取所有引号中的内容
                    tag_matches = re.findall(r'"([^"]+)"', line)
                    if tag_matches:
                        data["tags"].extend([tag.strip() for tag in tag_matches if tag.strip()])
                    else:
                        # 按逗号分割
                        parts = re.split(r'[,，、]', line)
                        data["tags"].extend([part.strip() for part in parts if part.strip()])
        
        # 提取相关链接
        links_section = False
        for i, line in enumerate(lines):
            line = line.strip()
            
            # 检查是否是相关链接部分的开始
            if re.search(r'相关链接[:：]|related[_ ]links[:：]', line, re.IGNORECASE):
                links_section = True
                continue
            
            # 检查是否到达了相关链接部分的结束
            if links_section and re.search(r'来源|source', line, re.IGNORECASE):
                links_section = False
                continue
            
            # 提取相关链接
            if links_section or "http" in line:
                # 查找URL
                url_matches = re.findall(r'https?://\S+', line)
                for url_match in url_matches:
                    url_clean = url_match.rstrip(',.，。;；:：')
                    
                    # 尝试提取描述
                    description = ""
                    desc_match = re.search(r'"description"\s*:\s*"([^"]+)"', line)
                    if desc_match:
                        description = desc_match.group(1)
                    else:
                        # 尝试获取URL前后的文字作为描述
                        parts = line.split(url_clean)
                        if len(parts) > 1:
                            if parts[0].strip():
                                description = parts[0].strip()
                            elif parts[1].strip():
                                description = parts[1].strip()
                    
                    if not description:
                        # 尝试从前一行或后一行获取描述
                        if i > 0 and not re.search(r'https?://', lines[i-1]) and len(lines[i-1].strip()) > 0:
                            description = lines[i-1].strip()
                        elif i < len(lines)-1 and not re.search(r'https?://', lines[i+1]) and len(lines[i+1].strip()) > 0:
                            description = lines[i+1].strip()
                    
                    # 清理描述
                    description = re.sub(r'^[-*:]|\s*[-:：]\s*$', '', description).strip()
                    
                    # 添加到相关链接
                    if url_clean != url:  # 不要包含原始URL
                        data["related_links"].append({
                            "url": url_clean,
                            "description": description if description else "相关链接"
                        })
        
        # 确保所有字段都有合理的默认值
        if not data["title"] or data["title"] == "未知标题":
            # 尝试使用第一行非空文本作为标题
            for line in lines:
                if line.strip() and len(line.strip()) > 5 and len(line.strip()) < 100:
                    data["title"] = line.strip()
                    break
        
        if not data["summary"]:
            # 提取前100-200个字符作为摘要
            combined_text = " ".join(line.strip() for line in lines if line.strip())
            data["summary"] = combined_text[:min(len(combined_text), 200)] + "..."
        
        if not data["key_points"] or len(data["key_points"]) < 2:
            # 添加默认关键点
            data["key_points"] = ["无法从文本中提取关键点，请查看原文了解详细内容。"]
        
        if not data["tags"] or len(data["tags"]) == 0:
            # 提取内容中以$和#开头的文本作为标签
            extracted_special_tags = []
            
            # 提取#标签
            general_hashtag_matches = re.findall(r'#(\w+)', text)
            if general_hashtag_matches:
                for tag in general_hashtag_matches:
                    if tag and len(tag) > 1 and tag.lower() not in [t.lower() for t in extracted_special_tags]:
                        extracted_special_tags.append(tag)
                        
            # 提取$标签
            dollar_tag_matches = re.findall(r'\$(\w+)', text)
            if dollar_tag_matches:
                for tag in dollar_tag_matches:
                    if tag and len(tag) > 1 and tag.lower() not in [t.lower() for t in extracted_special_tags]:
                        extracted_special_tags.append(tag)
            
            # 如果找到了特殊标签，使用它们
            if extracted_special_tags:
                data["tags"] = extracted_special_tags
                logger.info(f"从文本中提取到的特殊标签(#和$): {data['tags']}")
            else:
                # 检查是否是Twitter/X.com链接
                is_twitter = "twitter.com" in url or "x.com" in url
                
                if is_twitter:
                    # 尝试从文本中提取Twitter标签
                    hashtag_matches = re.findall(r'#(\w+)', text)
                    if hashtag_matches:
                        data["tags"] = list(set([tag.lower() for tag in hashtag_matches if tag]))[:5]
                        logger.info(f"从Twitter/X文本中提取到标签: {data['tags']}")
                
                # 如果仍然没有标签，使用域名
                if not data["tags"]:
                    domain = url.split("//")[-1].split("/")[0]
                    data["tags"] = [domain.split(".")[-2] if len(domain.split(".")) > 1 else domain]
                    
                    # 添加"其他"标签
                    data["tags"].append("其他")
        
        logger.info(f"从文本提取数据完成，标题: {data['title']}, 标签数量: {len(data['tags'])}")
        
        return data
