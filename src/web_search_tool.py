from ddgs import DDGS
import requests
from bs4 import BeautifulSoup
import trafilatura  # 专门用于提取网页正文

def web_search(query: str, max_results: int = 5) -> str:
    """搜索并获取完整网页内容"""
    
    results = []
    
    # 1. 先用 DuckDuckGo 搜索，获取 URL
    with DDGS() as ddgs:
        search_results = list(ddgs.text(f"{query} 菜谱 做法", max_results=max_results))
    
    for i, sr in enumerate(search_results, 1):
        title = sr.get("title", "")
        url = sr.get("href", "")
        snippet = sr.get("body", "")
        
        # 2. 尝试获取完整网页内容
        full_content = fetch_page_content(url)
        
        if full_content:
            # 有完整内容，使用完整内容
            content = full_content
        else:
            # 爬取失败，降级使用 snippet
            content = snippet
        
        results.append({
            "title": title,
            "url": url,
            "content": content
        })
    
    if not results:
        return "网络访问出错，未找到相关菜谱信息"

    return format_search_results(results)

def fetch_page_content(url: str, timeout: int = 10) -> str:
    """获取网页的正文内容"""
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # 方法1：使用 trafilatura（推荐，专门提取正文）
        content = trafilatura.extract(response.text, include_comments=False, include_tables=True)
        if content and len(content) > 200:
            return content[:3000]  # 限制长度，避免 token 过多
        
        # 方法2：降级到 BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 移除 script 和 style 标签
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # 尝试找到主要内容区域
        main_content = None
        for selector in ['article', 'main', '.content', '.post-content', '.recipe-content', '#content']:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
        else:
            text = soup.get_text(separator='\n', strip=True)
        
        # 清理多余空行
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        result = '\n'.join(lines[:100])  # 限制行数
        
        return result[:3000] if result else None
        
    except Exception as e:
        print(f"爬取失败 {url}: {e}")
        return None

def format_search_results(results: list) -> str:
    """格式化搜索结果"""
    
    if not results:
        return "未找到相关菜谱信息"
    
    formatted = []
    for r in results:
        formatted.append(f"【菜名】{r['title']}")
        formatted.append(f"内容：")
        formatted.append(r['content'])
        formatted.append("\n" + "-"*40 + "\n")
    
    return "\n".join(formatted)

if __name__ == "__main__":
    query = "清淡的鸡肉菜谱"
    print(web_search(query))