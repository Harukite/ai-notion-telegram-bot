from notion_client import Client
import requests
import json
import logging
from datetime import datetime
from config import NOTION_API_TOKEN, NOTION_DATABASE_ID

logger = logging.getLogger(__name__)

class NotionManager:
    def __init__(self):
        self.token = NOTION_API_TOKEN
        self.database_id = NOTION_DATABASE_ID
        
        # 使用直接的请求而不是客户端库
        self.api_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        # 检查数据库ID是否有效
        if not self.database_id:
            logger.error("数据库ID不能为空")
            raise ValueError("数据库ID不能为空")
        
    def add_content_to_database(self, processed_data):
        """将处理后的内容添加到Notion数据库"""
        try:
            # 准备Notion页面属性
            properties = {
                "标题": {
                    "title": [
                        {
                            "text": {
                                "content": processed_data["title"]
                            }
                        }
                    ]
                },
                "摘要": {
                    "rich_text": [
                        {
                            "text": {
                                "content": processed_data["summary"][:2000] if len(processed_data["summary"]) > 2000 else processed_data["summary"]
                            }
                        }
                    ]
                },
                "标签": {
                    "multi_select": [
                        {"name": tag} for tag in processed_data["tags"][:10]  # Notion限制，最多10个标签
                    ]
                },
                "来源": {
                    "url": processed_data["source"]
                },
                "链接": {
                    "url": processed_data["original_url"]
                },
                "添加时间": {
                    "date": {
                        "start": datetime.now().isoformat()
                    }
                },
                "状态": {
                    "status": {
                        "name": "未处理"  # 默认状态
                    }
                },
                "是否提醒": {
                    "checkbox": False  # 默认不提醒
                },
                "今日是否打卡": {
                    "status": {
                        "name": "否"  # 默认未打卡
                    }
                },
                "打卡次数": {
                    "number": 0  # 默认打卡次数为0
                }
            }
            
            # 创建页面内容
            children = [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": "关键点"}}]
                    }
                }
            ]
            
            # 添加关键点
            for point in processed_data["key_points"]:
                children.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": point}}]
                    }
                })
                
            # 添加相关链接部分
            if processed_data["related_links"]:
                children.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": "相关链接"}}]
                    }
                })
                
                for link in processed_data["related_links"]:
                    children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": f"{link['description']}: ",
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": {
                                        "content": link["url"],
                                        "link": {"url": link["url"]}
                                    }
                                }
                            ]
                        }
                    })
            
            # 创建页面
            data = {
                "parent": {"database_id": self.database_id},
                "properties": properties,
                "children": children
            }
            
            response = requests.post(
                f"{self.api_url}/pages",
                headers=self.headers,
                json=data
            )
            
            if response.status_code == 200:
                result = response.json()
                page_id = result.get("id", "unknown_id")
                logger.info(f"内容已成功添加到Notion数据库: {page_id}")
                return {"success": True, "page_id": page_id}
            else:
                error_msg = response.text
                logger.error(f"添加内容到Notion失败: HTTP {response.status_code}, {error_msg}")
                return {"success": False, "error": f"HTTP {response.status_code}: {error_msg}"}
            
        except Exception as e:
            logger.error(f"添加内容到Notion失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_entries_by_tag(self, tag):
        """根据标签获取数据库条目"""
        try:
            # 准备查询数据
            data = {
                "filter": {
                    "property": "标签",
                    "multi_select": {
                        "contains": tag
                    }
                }
            }
            
            response = requests.post(
                f"{self.api_url}/databases/{self.database_id}/query",
                headers=self.headers,
                json=data
            )
            
            if response.status_code != 200:
                logger.error(f"获取条目失败: HTTP {response.status_code}")
                return []
                
            result = response.json()
            entries = []
            
            for page in result.get("results", []):
                title = self._get_property_value(page, "标题", "title")
                status = self._get_property_value(page, "状态", "status")
                url = self._get_property_value(page, "链接", "url")
                
                entries.append({
                    "id": page.get("id", ""),
                    "title": title,
                    "status": status,
                    "url": url
                })
                
            return entries
        
        except Exception as e:
            logger.error(f"根据标签获取条目失败: {str(e)}")
            return []
    
    def update_entry_status(self, page_id, status):
        """更新条目状态"""
        try:
            data = {
                "properties": {
                    "状态": {
                        "status": {
                            "name": status
                        }
                    }
                }
            }
            
            response = requests.patch(
                f"{self.api_url}/pages/{page_id}",
                headers=self.headers,
                json=data
            )
            
            if response.status_code == 200:
                logger.info(f"条目状态已更新: {page_id} -> {status}")
                return {"success": True, "page_id": page_id, "status": status}
            else:
                error_msg = response.text
                logger.error(f"更新条目状态失败: HTTP {response.status_code}, {error_msg}")
                return {"success": False, "error": f"HTTP {response.status_code}: {error_msg}"}
            
        except Exception as e:
            logger.error(f"更新条目状态失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def add_tag_to_entry(self, page_id, tag):
        """为条目添加标签"""
        try:
            # 先获取当前标签
            response = requests.get(
                f"{self.api_url}/pages/{page_id}",
                headers=self.headers
            )
            
            if response.status_code != 200:
                logger.error(f"获取页面失败: HTTP {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            page = response.json()
            current_tags = []
            
            if "properties" in page and "标签" in page["properties"]:
                tag_prop = page["properties"]["标签"]
                if "multi_select" in tag_prop:
                    current_tags = [item.get("name", "") for item in tag_prop["multi_select"] if "name" in item]
            
            # 添加新标签
            if tag not in current_tags:
                current_tags.append(tag)
                
            # 更新标签
            data = {
                "properties": {
                    "标签": {
                        "multi_select": [{"name": t} for t in current_tags[:10]]  # Notion限制，最多10个标签
                    }
                }
            }
            
            response = requests.patch(
                f"{self.api_url}/pages/{page_id}",
                headers=self.headers,
                json=data
            )
            
            if response.status_code == 200:
                logger.info(f"条目标签已更新: {page_id} 添加标签 {tag}")
                return {"success": True, "page_id": page_id, "tags": current_tags}
            else:
                error_msg = response.text
                logger.error(f"更新条目标签失败: HTTP {response.status_code}, {error_msg}")
                return {"success": False, "error": f"HTTP {response.status_code}: {error_msg}"}
            
        except Exception as e:
            logger.error(f"为条目添加标签失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def delete_entry(self, page_id):
        """删除数据库条目"""
        try:
            # Notion API 通过"归档"来删除页面
            data = {
                "archived": True
            }
            
            response = requests.patch(
                f"{self.api_url}/pages/{page_id}",
                headers=self.headers,
                json=data
            )
            
            if response.status_code == 200:
                logger.info(f"条目已删除: {page_id}")
                return {"success": True, "page_id": page_id}
            else:
                error_msg = response.text
                logger.error(f"删除条目失败: HTTP {response.status_code}, {error_msg}")
                return {"success": False, "error": f"HTTP {response.status_code}: {error_msg}"}
            
        except Exception as e:
            logger.error(f"删除条目失败: {str(e)}")
            return {"success": False, "error": str(e)}
            
    def update_reminder_status(self, page_id, reminder_status):
        """更新是否提醒状态"""
        try:
            data = {
                "properties": {
                    "是否提醒": {
                        "checkbox": reminder_status
                    }
                }
            }
            
            response = requests.patch(
                f"{self.api_url}/pages/{page_id}",
                headers=self.headers,
                json=data
            )
            
            if response.status_code == 200:
                logger.info(f"提醒状态已更新: {page_id} -> {reminder_status}")
                return {"success": True, "page_id": page_id, "reminder_status": reminder_status}
            else:
                error_msg = response.text
                logger.error(f"更新提醒状态失败: HTTP {response.status_code}, {error_msg}")
                return {"success": False, "error": f"HTTP {response.status_code}: {error_msg}"}
            
        except Exception as e:
            logger.error(f"更新提醒状态失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def update_check_in_status(self, page_id, check_in_status):
        """更新今日是否打卡状态"""
        try:
            data = {
                "properties": {
                    "今日是否打卡": {
                        "status": {
                            "name": "是" if check_in_status else "否"
                        }
                    }
                }
            }
            
            response = requests.patch(
                f"{self.api_url}/pages/{page_id}",
                headers=self.headers,
                json=data
            )
            
            if response.status_code == 200:
                logger.info(f"打卡状态已更新: {page_id} -> {check_in_status}")
                return {"success": True, "page_id": page_id, "check_in_status": check_in_status}
            else:
                error_msg = response.text
                logger.error(f"更新打卡状态失败: HTTP {response.status_code}, {error_msg}")
                return {"success": False, "error": f"HTTP {response.status_code}: {error_msg}"}
            
        except Exception as e:
            logger.error(f"更新打卡状态失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def increment_check_in_count(self, page_id):
        """增加打卡次数"""
        try:
            # 首先获取当前打卡次数
            response = requests.get(
                f"{self.api_url}/pages/{page_id}",
                headers=self.headers
            )
            
            if response.status_code != 200:
                logger.error(f"获取页面失败: HTTP {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            page = response.json()
            current_count = 0
            
            if "properties" in page and "打卡次数" in page["properties"]:
                count_prop = page["properties"]["打卡次数"]
                if "number" in count_prop:
                    current_count = count_prop["number"] or 0
            
            # 增加打卡次数
            new_count = current_count + 1
            
            data = {
                "properties": {
                    "打卡次数": {
                        "number": new_count
                    }
                }
            }
            
            response = requests.patch(
                f"{self.api_url}/pages/{page_id}",
                headers=self.headers,
                json=data
            )
            
            if response.status_code == 200:
                logger.info(f"打卡次数已更新: {page_id} -> {new_count}")
                return {"success": True, "page_id": page_id, "check_in_count": new_count}
            else:
                error_msg = response.text
                logger.error(f"更新打卡次数失败: HTTP {response.status_code}, {error_msg}")
                return {"success": False, "error": f"HTTP {response.status_code}: {error_msg}"}
            
        except Exception as e:
            logger.error(f"更新打卡次数失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_reminder_entries(self):
        """获取设置了提醒的条目"""
        try:
            # 准备筛选条件
            filter_obj = {
                "property": "是否提醒",
                "checkbox": {
                    "equals": True
                }
            }
            
            data = {
                "filter": filter_obj,
                "page_size": 100  # 获取最多100条记录
            }
            
            response = requests.post(
                f"{self.api_url}/databases/{self.database_id}/query",
                headers=self.headers,
                json=data
            )
            
            if response.status_code != 200:
                logger.error(f"获取提醒条目失败: HTTP {response.status_code}")
                return []
                
            result = response.json()
            entries = []
            
            for page in result.get("results", []):
                title = self._get_property_value(page, "标题", "title")
                check_in_status = self._get_property_value(page, "今日是否打卡", "status")
                check_in_count = self._get_property_value(page, "打卡次数", "number")
                
                entries.append({
                    "id": page.get("id", ""),
                    "title": title,
                    "check_in_status": check_in_status,
                    "check_in_count": check_in_count
                })
                
            return entries
        
        except Exception as e:
            logger.error(f"获取提醒条目失败: {str(e)}")
            return []
            
    def reset_daily_check_in_status(self):
        """重置所有条目的今日打卡状态为'否'"""
        try:
            # 获取所有设置了提醒的条目
            reminder_entries = self.get_reminder_entries()
            
            success_count = 0
            failed_entries = []
            
            for entry in reminder_entries:
                result = self.update_check_in_status(entry["id"], False)
                if result["success"]:
                    success_count += 1
                else:
                    failed_entries.append(entry["id"])
            
            logger.info(f"每日打卡状态已重置: {success_count} 成功, {len(failed_entries)} 失败")
            return {"success": True, "reset_count": success_count, "failed_entries": failed_entries}
            
        except Exception as e:
            logger.error(f"重置每日打卡状态失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_all_tags(self):
        """获取数据库中所有使用的标签"""
        try:
            # 查询数据库
            response = requests.post(
                f"{self.api_url}/databases/{self.database_id}/query",
                headers=self.headers,
                json={}
            )
            
            if response.status_code != 200:
                logger.error(f"获取数据库数据失败: HTTP {response.status_code}")
                return []
                
            result = response.json()
            all_tags = set()
            
            # 从所有条目中提取标签
            for page in result.get("results", []):
                tags = self._get_property_value(page, "标签", "multi_select")
                if tags:
                    all_tags.update(tags)
            
            return sorted(list(all_tags))
        
        except Exception as e:
            logger.error(f"获取所有标签失败: {str(e)}")
            return []
    
    def get_entries_with_details(self, tag=None, status=None, limit=10):
        """获取数据库条目，带有摘要和更多详细信息"""
        try:
            # 准备筛选条件
            filter_obj = {}
            
            if tag:
                filter_obj = {
                    "property": "标签",
                    "multi_select": {
                        "contains": tag
                    }
                }
            elif status:
                filter_obj = {
                    "property": "状态",
                    "status": {
                        "equals": status
                    }
                }
            
            data = {}
            if filter_obj:
                data["filter"] = filter_obj
                
            # 添加页面大小限制
            data["page_size"] = limit
            
            # 按添加时间排序
            data["sorts"] = [
                {
                    "property": "添加时间",
                    "direction": "descending"
                }
            ]
            
            response = requests.post(
                f"{self.api_url}/databases/{self.database_id}/query",
                headers=self.headers,
                json=data
            )
            
            if response.status_code != 200:
                logger.error(f"获取条目失败: HTTP {response.status_code}")
                return []
                
            result = response.json()
            entries = []
            
            for page in result.get("results", []):
                title = self._get_property_value(page, "标题", "title")
                summary = self._get_property_value(page, "摘要", "rich_text")
                status = self._get_property_value(page, "状态", "status")
                tags = self._get_property_value(page, "标签", "multi_select")
                url = self._get_property_value(page, "链接", "url")
                source = self._get_property_value(page, "来源", "url")
                reminder = self._get_property_value(page, "是否提醒", "checkbox") or False
                check_in_status = self._get_property_value(page, "今日是否打卡", "status") or "否"
                check_in_count = self._get_property_value(page, "打卡次数", "number") or 0
                
                entries.append({
                    "id": page.get("id", ""),
                    "title": title,
                    "summary": summary,
                    "status": status,
                    "tags": tags,
                    "url": url,
                    "source": source,
                    "reminder": reminder,
                    "check_in_status": check_in_status,
                    "check_in_count": check_in_count
                })
                
            return entries
        
        except Exception as e:
            logger.error(f"获取条目失败: {str(e)}")
            return []
    
    def _get_property_value(self, page, property_name, property_type):
        """从页面属性中提取值"""
        if not page or "properties" not in page or property_name not in page["properties"]:
            return None
            
        prop = page["properties"][property_name]
        
        if property_type == "title" and "title" in prop and prop["title"]:
            if len(prop["title"]) > 0 and "text" in prop["title"][0] and "content" in prop["title"][0]["text"]:
                return prop["title"][0]["text"]["content"]
            return ""
        elif property_type == "rich_text" and "rich_text" in prop and prop["rich_text"]:
            if len(prop["rich_text"]) > 0 and "text" in prop["rich_text"][0] and "content" in prop["rich_text"][0]["text"]:
                return prop["rich_text"][0]["text"]["content"]
            return ""
        elif property_type == "select" and "select" in prop and prop["select"]:
            return prop["select"].get("name", "")
        elif property_type == "status" and "status" in prop and prop["status"]:
            return prop["status"].get("name", "")
        elif property_type == "multi_select" and "multi_select" in prop:
            return [item.get("name", "") for item in prop["multi_select"] if "name" in item]
        elif property_type == "url" and "url" in prop:
            return prop.get("url", "")
        elif property_type == "checkbox" and "checkbox" in prop:
            return prop.get("checkbox", False)
        elif property_type == "number" and "number" in prop:
            return prop.get("number", 0)
        else:
            return None
