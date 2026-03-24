import json
from langchain.tools import tool
from deerflow.config import get_app_config
from ddgs import DDGS

@tool("web_search", parse_docstring=True)
def web_search_tool(query: str) -> str:
    """Search the web.

    Args:
        query: The query to search for.
    """
    config = get_app_config().get_tool_config("web_search")
    max_results = 5
    if config is not None and "max_results" in config.model_extra:
        max_results = config.model_extra.get("max_results")

    try:
        results = DDGS().text(query, max_results=max_results)
        normalized_results = [
            {
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "snippet": result.get("body", ""),
            }
            for result in results
        ]
        return json.dumps(normalized_results, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool("web_fetch", parse_docstring=True)
def web_fetch_tool(url: str) -> str:
    """Fetch the contents of a web page at a given URL.
    Only fetch EXACT URLs that have been provided directly by the user or have been returned in results from the web_search and web_fetch tools.

    Args:
        url: The URL to fetch the contents of.
    """
    import httpx
    import re
    try:
        response = httpx.get(url, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
        
        # Naive HTML stripping to return clean text chunks safely
        text = re.sub(r'<style.*?>.*?</style>', '', response.text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        return f"# {url}\n\n{text[:6000]}"
    except Exception as e:
        return f"Error: {str(e)}"
