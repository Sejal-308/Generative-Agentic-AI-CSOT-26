"""
Web search and fetch tools — carry forward from Week 2.

Implement or copy from your week_2/project/:
  - web_search(query) — Serper
  - web_fetch(url) — requests + trafilatura/markdownify
"""

# TODO: copy from Week 2 project
"""
Web search and fetch tools — carry forward from Week 2 using Trafilatura.
"""
import os
import requests
import trafilatura

def search_web(query: str) -> dict:
    """
    Search the web using the Serper API.
    """
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        raise ValueError("SERPER_API_KEY environment variable not set")
        
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    payload = {"q": query}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Web search failed: {e}")
        return {"organic": []}

def read_page(url: str) -> str:
    """
    Fetch the content of a URL and convert it to clean text using trafilatura.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Trafilatura extracts clean main text content perfectly
        downloaded = response.text
        clean_text = trafilatura.extract(downloaded)
        
        if not clean_text:
            return "Error: Could not extract readable text content from this webpage."
            
        # Cap text length to prevent context blowout for your agent
        return clean_text[:15000]
        
    except Exception as e:
        return f"Error fetching web page: {e}"