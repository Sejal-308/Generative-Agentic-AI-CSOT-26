"""
Paper search and read tools — Hugging Face Papers API (arXiv index).

Implement:
  - paper_search(query, limit) -> {papers: [{arxiv_id, title, abstract, url}, ...]}
  - read_paper(arxiv_id) -> {title, abstract, content, url, ...}

API docs: week_3/3_paper_tools.md
"""
"""
Paper search and read tools — Hugging Face Papers API (arXiv index).
"""

import requests
import re
def paper_search(query: str, limit: int = 5) -> dict:
    """
    Search for papers on Hugging Face Papers.
    Returns: {"papers": [{"arxiv_id", "title", "abstract", "url"}, ...]}
    """
    base_url = "https://huggingface.co/api/papers/search"
    params = {"q": query}
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        results = response.json()
        
        # Limit results manually if the API doesn't support a limit parameter
        results = results[:limit]
        
        normalized_papers = []
        for item in results:
            # Handle potential variance in API response shape (flat vs nested "paper" key)
            paper_data = item.get("paper", item) if isinstance(item, dict) else item
            
            arxiv_id = paper_data.get("id") or paper_data.get("arxivId")
            
            normalized_papers.append({
                "arxiv_id": arxiv_id,
                "title": paper_data.get("title", ""),
                "abstract": paper_data.get("summary", paper_data.get("abstract", "")),
                "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
            })
            
        return {"papers": normalized_papers}
        
    except Exception as e:
        print(f"Error during paper search: {e}")
        return {"papers": []}



def normalize_arxiv_id(raw_id: str) -> str:
    """Strips URL prefixes, version numbers (e.g., v2), or paths."""
    # Extract something resembling an arXiv ID (e.g., 2205.14135 or cs/0123456)
    match = re.search(r'(?:abs/|papers/)?([a-zA-Z\-]+(?:\.[a-zA-Z\-]+)?/\d{7}|\d{4}\.\d{4,5})', raw_id)
    if match:
        return match.group(1)
    return raw_id.split('/')[-1].strip()

def read_paper(arxiv_id: str) -> dict:
    """
    Fetch full details for a specific paper by its arXiv ID.
    Returns: {"title", "abstract", "content", "url"}
    """
    clean_id = normalize_arxiv_id(arxiv_id)
    
    # Endpoints to hit
    meta_url = f"https://huggingface.co/api/papers/{clean_id}"
    md_url = f"https://huggingface.co/papers/{clean_id}.md"
    
    result = {
        "title": "",
        "abstract": "",
        "content": "",
        "url": f"https://arxiv.org/abs/{clean_id}"
    }
    
    # 1. Fetch metadata
    try:
        meta_resp = requests.get(meta_url)
        if meta_resp.status_code == 200:
            meta_data = meta_resp.json()
            # Handle standard format or wrapper nested objects
            paper_data = meta_data.get("paper", meta_data)
            result["title"] = paper_data.get("title", "")
            result["abstract"] = paper_data.get("summary", paper_data.get("abstract", ""))
    except Exception as e:
        print(f"Metadata fetch failed: {e}")

    # 2. Fetch markdown content
    try:
        md_resp = requests.get(md_url)
        if md_resp.status_code == 200:
            # Cap tokens/characters here to prevent context window blowouts
            result["content"] = md_resp.text[:20000] 
        else:
            # Fallback to abstract if Markdown endpoint returns 404
            result["content"] = result["abstract"]
    except Exception as e:
        result["content"] = result["abstract"]
        
    return result