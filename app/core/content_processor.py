import re
import json
import requests
import logging
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from app.config import (
    DEEPSEEK_API_KEY, 
    HAS_TWITTER_CONFIG, 
    CAN_USE_TWITTER_API,
    DEEPSEEK_API_TIMEOUT, 
    DEEPSEEK_API_MAX_RETRIES,
    DEEPSEEK_API_RETRY_DELAY,
    RAPIDAPI_KEY
)

# 不再进行网页模拟访问与UA伪装

# 引入Twitter API模块（如果配置了Twitter API）
try:
    from app.services.twitter_service import TwitterAPI, twitter_api
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

MAX_CONTENT_LENGTH = 10000  # 大文本最大长度

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
        if not HAS_TWEEPY:
            logger.info("未安装tweepy库，无法使用API获取推文")
            return None
            
        # 即便未配置官方API (CAN_USE_TWITTER_API=False)，
        # 只要安装了tweepy，我们仍尝试调用 twitter_api.get_tweet_data()，
        # 因为该模块内部封装了 Scraper.tech 的备用抓取逻辑。
        
        try:
            # 使用Twitter API获取推文
            logger.info(f"尝试使用Twitter API模块获取推文: {url}")
            tweet_data = twitter_api.get_tweet_data(url)
            
            if tweet_data and isinstance(tweet_data, dict) and 'content' in tweet_data:
                logger.info(f"成功使用Twitter API模块获取推文内容")
                return tweet_data
            else:
                logger.warning("Twitter API模块返回数据为空或格式不正确")
                return None
        except Exception as e:
            logger.error(f"使用Twitter API模块获取推文时出错: {str(e)}")
            return None
    
    def _fetch_webpage_content(self, url, max_length=MAX_CONTENT_LENGTH):
        """仅通过官方 Twitter API 或 RapidAPI 获取推文数据；不再抓取网页。"""
        try:
            is_twitter = "twitter.com" in url or "x.com" in url
            if not is_twitter:
                # 非 Twitter 链接不再抓取网页
                return {
                    "title": "不支持的链接",
                    "content": "",
                    "url": url,
                    "source": url.split("//")[-1].split("/")[0] if "//" in url else url
                }

            # 1) 尝试使用 Twitter API 模块 (含 Scraper.tech 备用)
            if HAS_TWEEPY:
                api_result = self._get_twitter_content_via_api(url)
                if api_result:
                    return api_result

            # 2) RapidAPI 兜底（需 RAPIDAPI_KEY 且能提取ID）
            twitter_id = None
            username = None
            if "/status/" in url:
                parts = url.split('/')
                try:
                    status_index = parts.index("status")
                except ValueError:
                    status_index = -1
                if status_index > 0 and status_index + 1 < len(parts):
                    username = parts[status_index - 1]
                    twitter_id = parts[status_index + 1].split("?")[0]

            if RAPIDAPI_KEY and twitter_id and twitter_id.isalnum():
                rapidapi_url = "https://twitter-api45.p.rapidapi.com/tweet.php"
                rapidapi_headers = {
                    "x-rapidapi-key": RAPIDAPI_KEY,
                    "x-rapidapi-host": "twitter-api45.p.rapidapi.com"
                }
                rapidapi_querystring = {"id": twitter_id}
                resp = requests.get(rapidapi_url, headers=rapidapi_headers, params=rapidapi_querystring, timeout=20)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        tweet_text = data.get('display_text', '') or data.get('text', '') or ""
                        user_info = data.get('author', {}) if isinstance(data.get('author', {}), dict) else {}
                        if not user_info and isinstance(data.get('user', {}), dict):
                            user_info = data.get('user', {})
                        user_name = user_info.get('screen_name', '') or ""
                        user_display_name = user_info.get('name', '') or ""

                        hashtags = []
                        entities = data.get('entities', {}) if isinstance(data.get('entities', {}), dict) else {}
                        if 'hashtags' in entities and entities['hashtags']:
                            for tag in entities['hashtags']:
                                if isinstance(tag, dict) and 'text' in tag:
                                    hashtags.append(tag['text'])

                        # 计算完整推文链接（用于缺失或替代）
                        full_url = url
                        try:
                            if user_name and twitter_id:
                                full_url = f"https://twitter.com/{user_name}/status/{twitter_id}"
                            elif twitter_id:
                                full_url = f"https://twitter.com/i/web/status/{twitter_id}"
                        except Exception:
                            pass

                        title = (
                            f"{user_display_name} (@{user_name}): {tweet_text[:30] + ('...' if len(tweet_text) > 30 else '')}"
                            if user_display_name and user_name else (tweet_text[:30] + ('...' if len(tweet_text) > 30 else '')) or "Twitter推文"
                        )

                        return {
                            "title": title,
                            "content": tweet_text,
                            "url": full_url or url,
                            "source": f"Twitter (@{user_name})" if user_name else "Twitter",
                            "extracted_tags": hashtags or [],
                            "tweet_meta": {
                                "platform": "Twitter" if "twitter.com" in url else "X",
                                "author": user_display_name or "",
                                "username": user_name or "",
                                "date": data.get('created_at', '') or "",
                                "tags": hashtags or [],
                                "via": "RapidAPI"
                            }
                        }
                    except Exception as e:
                        logger.error(f"解析RapidAPI返回数据时出错: {str(e)}")

            # Twitter 获取失败
            return {
                "title": "获取失败",
                "content": "",
                "url": url,
                "source": "Twitter" if "twitter.com" in url else "X"
            }
        except Exception as e:
            logger.error(f"获取内容失败: {str(e)}")
            return {
                "title": "获取失败",
                "content": f"无法获取内容: {str(e)}",
                "url": url,
                "source": url.split("//")[-1].split("/")[0] if "//" in url else url
            }
    
    def fetch_webpage_content(self, url, max_length=MAX_CONTENT_LENGTH):
        """同步方式抓取网页内容（非x.com）"""
        try:
            logger.info(f"开始抓取网页: {url}")
            # 添加 User-Agent 防止被简单拦截
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=15)
            logger.info(f"网页抓取状态码: {resp.status_code}, 原始长度: {len(resp.content)}")
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.content, 'html.parser')
            title = soup.title.string.strip() if soup.title and soup.title.string else '未知标题'
            content = soup.get_text(separator='\n', strip=True)
            
            logger.info(f"解析后标题: {title}, 内容长度: {len(content)}")
            if len(content) < 100:
                 logger.warning(f"内容过短，前100字符: {content[:100]!r}")

            # 限制最大长度
            if len(content) > max_length:
                content = content[:max_length]
            return {
                'title': title,
                'content': content,
                'url': url,
                'source': url.split('//')[-1].split('/')[0]
            }
        except Exception as e:
            return {
                'title': '获取失败',
                'content': f'无法获取内容: {str(e)}',
                'url': url,
                'source': url.split('//')[-1].split('/')[0]
            }

    async def fetch_webpage_content_async(self, url, session, max_length=MAX_CONTENT_LENGTH):
        """异步方式抓取网页内容（非x.com）"""
        try:
            async with session.get(url, timeout=15) as resp:
                text = await resp.text()
                soup = BeautifulSoup(text, 'html.parser')
                title = soup.title.string.strip() if soup.title and soup.title.string else '未知标题'
                content = soup.get_text(separator='\n', strip=True)
                if len(content) > max_length:
                    content = content[:max_length]
                return {
                    'title': title,
                    'content': content,
                    'url': url,
                    'source': url.split('//')[-1].split('/')[0]
                }
        except Exception as e:
            return {
                'title': '获取失败',
                'content': f'无法获取内容: {str(e)}',
                'url': url,
                'source': url.split('//')[-1].split('/')[0]
            }

    async def batch_fetch_webpages(self, urls, max_length=MAX_CONTENT_LENGTH):
        """批量异步抓取网页内容（非x.com）"""
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_webpage_content_async(url, session, max_length) for url in urls]
            return await asyncio.gather(*tasks)

    def process_link(self, url):
        """处理链接并返回结构化内容（支持x.com和普通网页）"""
        is_twitter = "twitter.com" in url or "x.com" in url or "nitter" in url
        # 只要安装了 tweepy 库，就尝试使用 twitter_api 模块处理
        # 该模块内部会自动判断使用官方 API 还是 Scraper.tech 备用
        if is_twitter and HAS_TWEEPY:
            webpage_data = self._get_twitter_content_via_api(url)
            if not webpage_data:
                logger.error(f"无法通过Twitter API/Scraper获取内容: {url}")
                return {
                    "title": "获取失败",
                    "summary": "无法获取推文内容。可能是API配置问题、密钥失效或链接无效。",
                    "key_points": ["无法获取内容", "请检查URL是否正确", "API/Scraper配置是否有效"],
                    "tags": ["访问失败", "内容缺失"],
                    "related_links": [],
                    "source": "Twitter",
                    "original_url": url
                }
        else:
            # 普通网页抓取
            webpage_data = self.fetch_webpage_content(url)
            if not webpage_data.get("content") or len(webpage_data["content"]) < 10:
                logger.warning(f"网页内容不足或为空: {url}")
                return {
                    "title": webpage_data.get("title", "无法获取标题"),
                    "summary": "未能获取足够内容进行分析。请检查链接。",
                    "key_points": ["无法获取内容", "请检查URL是否正确"],
                    "tags": ["访问失败", "内容缺失"],
                    "related_links": [],
                    "source": webpage_data.get("source", url.split("//")[-1].split("/")[0] if "//" in url else url),
                    "original_url": url
                }
        # 检查是否成功获取内容
        # 对于Twitter/X内容，放宽长度限制，因为推文通常较短
        min_length = 10 if is_twitter else 100
        
        if not webpage_data.get("content") or len(webpage_data["content"]) < min_length:
            logger.warning(f"获取网页内容不足或为空 (长度: {len(webpage_data.get('content', ''))}, 最小要求: {min_length}): {url}")
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
        
        # 确保标题字段存在
        if not webpage_data.get("title"):
            # 如果缺失标题，先尝试从tweet_meta中获取
            if is_twitter and webpage_data.get("tweet_meta"):
                tweet_meta = webpage_data["tweet_meta"]
                username = tweet_meta.get("username", "")
                author = tweet_meta.get("author", "")
                if author and username:
                    webpage_data["title"] = f"{author} (@{username})的推文"
                elif author:
                    webpage_data["title"] = f"{author}的推文"
                elif username:
                    webpage_data["title"] = f"@{username}的推文"
                else:
                    webpage_data["title"] = "Twitter推文"
            else:
                # 非Twitter内容或无法从tweet_meta获取，使用display_text生成标题
                display_text = webpage_data.get("content", "")[:50].strip()
                if display_text:
                    webpage_data["title"] = f"{display_text}..."
                else:
                    webpage_data["title"] = "未知标题"
                    
            # 记录我们生成的标题
            logger.info(f"为缺失标题生成替代标题: {webpage_data['title']}")
        
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
                    # 检查原始标题是否有"未知"或"推文"等通用标记，如果是则保留DeepSeek生成的标题
                    original_title = webpage_data.get("title", "")
                    generic_title_indicators = ["未知标题", "推文", "Twitter推文"]
                    
                    if any(indicator in original_title for indicator in generic_title_indicators):
                        if is_twitter:
                            # 尝试用DeepSeek的摘要生成一个更好的标题
                            summary = parsed_data.get("summary", "")
                            if summary:
                                parsed_data["title"] = summary[:50] + "..." if len(summary) > 50 else summary
                            else:
                                parsed_data["title"] = original_title
                        else:
                            parsed_data["title"] = original_title
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
            r'"title"\s*:\s*"([^"]+)",?'
        ]