import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from typing import List, Dict

@tool
def web_search(query: str) -> str:
    """
    Search the web for information related to the query.
    Returns relevant web search results with citations.
    """
    try:
        # Simple DuckDuckGo search (replace with your preferred search API)
        search_url = f"https://duckduckgo.com/html/?q={query}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        results = []
        for i, result in enumerate(soup.find_all('div', class_='result'), 1):
            if i > 3:  # Limit to top 3 results
                break
                
            title_elem = result.find('h2')
            snippet_elem = result.find('span', class_='result-snippet')
            
            if title_elem and snippet_elem:
                title = title_elem.get_text().strip()
                snippet = snippet_elem.get_text().strip()
                results.append(f"[{i}] {title}: {snippet}")
        
        return "\n".join(results) if results else "No relevant results found"
        
    except Exception as e:
        return f"Error performing web search: {str(e)}"

