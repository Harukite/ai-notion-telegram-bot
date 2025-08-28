"""
Twitter API 模块 - 使用官方API获取推文数据
作为内容抓取的备用方案
"""

import re
import logging
import tweepy
from config import (
    TWITTER_API_KEY, 
    TWITTER_API_SECRET, 
    TWITTER_ACCESS_TOKEN, 
    TWITTER_ACCESS_SECRET,
    TWITTER_BEARER_TOKEN,
    HAS_TWITTER_CONFIG,
    CAN_USE_TWITTER_API
)

logger = logging.getLogger(__name__)

class TwitterAPI:
    def __init__(self):
        """初始化Twitter API客户端"""
        self.api_v1 = None
        self.client_v2 = None
        self.is_initialized = False
        
        # 检查是否启用且配置完整
        if not CAN_USE_TWITTER_API:
            if not HAS_TWITTER_CONFIG:
                logger.warning("Twitter API配置不完整，无法使用官方API获取推文")
            else:
                logger.info("Twitter API已禁用，若要启用请将USE_TWITTER_API设置为true")
            return
            
        try:
            # 初始化API v1.1客户端
            auth = tweepy.OAuth1UserHandler(
                TWITTER_API_KEY, 
                TWITTER_API_SECRET,
                TWITTER_ACCESS_TOKEN, 
                TWITTER_ACCESS_SECRET
            )
            self.api_v1 = tweepy.API(auth)
            
            # 初始化API v2客户端
            self.client_v2 = tweepy.Client(
                bearer_token=TWITTER_BEARER_TOKEN,
                consumer_key=TWITTER_API_KEY,
                consumer_secret=TWITTER_API_SECRET,
                access_token=TWITTER_ACCESS_TOKEN,
                access_token_secret=TWITTER_ACCESS_SECRET,
                # wait_on_rate_limit=True
            )
            
            self.is_initialized = True
            logger.info("Twitter API客户端初始化成功")
        except Exception as e:
            logger.error(f"初始化Twitter API客户端失败: {str(e)}")
            
    def extract_tweet_id_from_url(self, url):
        """从URL中提取推文ID"""
        # 处理标准Twitter/X URL
        status_pattern = r'(?:twitter\.com|x\.com)/[^/]+/status/(\d+)'
        match = re.search(status_pattern, url)
        if match:
            return match.group(1)
            
        # 处理Twitter短链接
        short_pattern = r'(?:t\.co)/(\w+)'
        match = re.search(short_pattern, url)
        if match:
            try:
                # 尝试使用requests展开短链接
                import requests
                response = requests.head(url, allow_redirects=True, timeout=10)
                return self.extract_tweet_id_from_url(response.url)
            except Exception as e:
                logger.warning(f"展开短链接失败: {str(e)}")
                
        return None
        
    def get_tweet_data(self, url):
        """获取指定URL的推文数据
        
        返回格式:
        {
            "title": "推文标题",
            "content": "推文内容",
            "url": "原始URL",
            "source": "Twitter" or "X",
            "extracted_tags": ["标签1", "标签2"],
            "tweet_meta": {
                "author": "作者",
                "username": "用户名",
                "date": "发布日期",
                "tags": ["标签1", "标签2"],
                "mentions": ["提及1", "提及2"]
            }
        }
        """
        if not self.is_initialized:
            logger.warning("Twitter API未初始化，无法获取推文数据")
            return None
            
        try:
            # 从URL中提取推文ID
            tweet_id = self.extract_tweet_id_from_url(url)
            if not tweet_id:
                logger.warning(f"无法从URL中提取推文ID: {url}")
                return None
                
            logger.info(f"尝试使用官方API获取推文: {tweet_id}")
            
            # 使用API v2获取推文数据
            tweet = self.client_v2.get_tweet(
                id=tweet_id,
                expansions=[
                    "author_id", 
                    "referenced_tweets.id", 
                    "attachments.media_keys"
                ],
                tweet_fields=[
                    "created_at", 
                    "public_metrics", 
                    "entities", 
                    "context_annotations", 
                    "conversation_id"
                ],
                user_fields=[
                    "name", 
                    "username", 
                    "profile_image_url", 
                    "verified", 
                    "description"
                ],
                media_fields=["preview_image_url", "url"]
            )
            
            if not tweet or not tweet.data:
                logger.warning(f"使用API v2获取推文失败，尝试使用API v1.1: {tweet_id}")
                
                # 尝试使用API v1.1作为备选
                try:
                    tweet_v1 = self.api_v1.get_status(
                        tweet_id, 
                        tweet_mode="extended", 
                        include_entities=True
                    )
                    return self._parse_tweet_v1(tweet_v1, url)
                except Exception as e:
                    logger.error(f"使用API v1.1获取推文失败: {str(e)}")
                    return None
            
            # 解析API v2返回的数据
            return self._parse_tweet_v2(tweet, url)
            
        except Exception as e:
            logger.error(f"获取推文数据失败: {str(e)}")
            return None
            
    def _parse_tweet_v2(self, tweet_response, original_url):
        """解析API v2返回的推文数据"""
        if not tweet_response or not tweet_response.data:
            return None
            
        tweet = tweet_response.data
        users = {user.id: user for user in tweet_response.includes.get("users", [])} if hasattr(tweet_response.includes, "users") else {}
        
        # 获取作者信息
        author = None
        username = None
        if tweet.author_id and tweet.author_id in users:
            author = users[tweet.author_id].name
            username = users[tweet.author_id].username
            
        # 获取推文内容
        content = tweet.text
            
        # 提取标签和提及
        hashtags = []
        mentions = []
        if hasattr(tweet, "entities") and tweet.entities:
            if "hashtags" in tweet.entities and tweet.entities["hashtags"]:
                hashtags = [tag["tag"] for tag in tweet.entities["hashtags"]]
            if "mentions" in tweet.entities and tweet.entities["mentions"]:
                mentions = [mention["username"] for mention in tweet.entities["mentions"]]
                
        # 组装返回数据
        tweet_data = {
            "title": f"{author or '未知作者'}的推文" if author else "推文",
            "content": content,
            "url": original_url,
            "source": "Twitter" if "twitter.com" in original_url else "X",
            "extracted_tags": hashtags,
            "tweet_meta": {
                "platform": "Twitter" if "twitter.com" in original_url else "X",
                "author": author,
                "username": username,
                "date": tweet.created_at.isoformat() if hasattr(tweet, "created_at") else None,
                "tags": hashtags,
                "mentions": mentions,
                "via": "twitter_api_v2"
            }
        }
        
        logger.info(f"成功解析推文数据: {tweet.id}")
        return tweet_data
        
    def _parse_tweet_v1(self, tweet, original_url):
        """解析API v1.1返回的推文数据"""
        if not tweet:
            return None
            
        # 获取作者信息
        author = tweet.user.name if hasattr(tweet, "user") else None
        username = tweet.user.screen_name if hasattr(tweet, "user") else None
        
        # 获取推文内容 (v1中是full_text或text)
        content = tweet.full_text if hasattr(tweet, "full_text") else tweet.text
            
        # 提取标签和提及
        hashtags = []
        mentions = []
        if hasattr(tweet, "entities"):
            if "hashtags" in tweet.entities and tweet.entities["hashtags"]:
                hashtags = [tag["text"] for tag in tweet.entities["hashtags"]]
            if "user_mentions" in tweet.entities and tweet.entities["user_mentions"]:
                mentions = [mention["screen_name"] for mention in tweet.entities["user_mentions"]]
                
        # 组装返回数据
        tweet_data = {
            "title": f"{author or '未知作者'}的推文" if author else "推文",
            "content": content,
            "url": original_url,
            "source": "Twitter" if "twitter.com" in original_url else "X",
            "extracted_tags": hashtags,
            "tweet_meta": {
                "platform": "Twitter" if "twitter.com" in original_url else "X",
                "author": author,
                "username": username,
                "date": tweet.created_at.isoformat() if hasattr(tweet, "created_at") else None,
                "tags": hashtags,
                "mentions": mentions,
                "via": "twitter_api_v1"
            }
        }
        
        logger.info(f"成功解析推文数据: {tweet.id}")
        return tweet_data

# 创建单例实例
twitter_api = TwitterAPI()
