import httpx
import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from urllib.parse import urljoin

# Special token for splitting content
IMG_TOKEN_PATTERN = re.compile(r"\[\[IMGTOKEN:(.*?)\]\]")

# Elements to exclude from rendering
BLOCK_LIST = [
    {"name": "div", "attrs": {"data-testid": "toolbar"}},
    {"class_": "mw-jump-link"},
    {"class_": "mw-editsection"},
    {"class_": "navbox"},
    {"class_": "hatnote"},
    {"id": "siteSub"},
    {"id": "contentSub"},
]

async def fetch_and_parse(url: str, readability_mode: bool = False) -> list[dict]:
    """
    Fetches the URL and returns a list of content segments.
    Returns: List of dicts with keys 'type' ('text' or 'image') and 'content'/'url'.
    """
    # 1. Normalize URL
    target_url = url.strip()
    fallback_url = None

    if not target_url.lower().startswith(("http://", "https://")):
        fallback_url = f"http://{target_url}"
        target_url = f"https://{target_url}"

    try:
        html, final_url = await _perform_request(target_url, readability_mode)
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        if fallback_url:
            try:
                html, final_url = await _perform_request(fallback_url, readability_mode)
            except Exception:
                return [{"type": "text", "content": f"## Error fetching {target_url}"}]
        else:
             return [{"type": "text", "content": f"## Error fetching {target_url}"}]
    except Exception as e:
        return [{"type": "text", "content": f"## Error: {str(e)}"}]

    # 2. Process HTML (Resolve Links & Tokenize Images)
    soup = BeautifulSoup(html, "html.parser")
    
    # --- Apply Block List ---
    for selector in BLOCK_LIST:
        for tag in soup.find_all(**selector):
            tag.decompose()
    
    # Remove junk
    for script in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        script.decompose()

    # Resolve Links

    # Resolve Links
    for tag in soup.find_all('a', href=True):
         tag['href'] = urljoin(final_url, tag['href'])

    # Unwrap <picture> tags to expose the fallback <img>
    for picture in soup.find_all("picture"):
        img = picture.find("img")
        if img:
            # Prioritize <source> tags if present (often higher quality or real image vs placeholder)
            found_source = False
            for source in picture.find_all("source"):
                srcset = source.get("srcset")
                if srcset:
                    # Take the first URL from srcset (e.g. "foo.jpg 1x, bar.jpg 2x")
                    # We strip to handle " url 1x"
                    candidates = srcset.split(",")
                    if candidates:
                        first_candidate = candidates[0].strip().split(" ")[0]
                        if first_candidate:
                            img["src"] = first_candidate
                            found_source = True
                            break
            
            # If no source found, we keep the original img['src'] (if any)
            # Then replace picture with the updated img
            picture.replace_with(img)
        else:
            # If no img found, try to find a source with srcset
            # For now, just decompose if no fallback
            picture.decompose()

    # Tokenize Images (Replace <img> with text token)
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
            
        # Handle Data URIs
        if src.startswith("data:"):
            # We preserve the data URI as is. 
            # Note: This might create very large tokens.
            img.replace_with(f"[[IMGTOKEN:{src}]]")
            continue

        # Handle Standard URLs
        abs_url = urljoin(final_url, src)
        if abs_url.startswith(("http", "https")):
            img.replace_with(f"[[IMGTOKEN:{abs_url}]]")

    # Readability Logic
    content_root = soup
    if readability_mode:
        candidate = soup.find("article") or soup.find("main") or soup.find(role="main")
        if candidate:
            content_root = candidate

    # 3. Convert to Markdown
    text_content = md(str(content_root), heading_style="ATX")

    # 4. Split into Segments
    segments = []
    last_pos = 0
    
    # We use a pattern that allows for escaped characters (like \_) within the token
    for match in IMG_TOKEN_PATTERN.finditer(text_content):
        # Add text before the image
        text_part = text_content[last_pos:match.start()].strip()
        if text_part:
            segments.append({"type": "text", "content": text_part})
        
        # Add the image, cleaning up any markdown escapes in the URL
        img_url = match.group(1).replace("\\", "")
        segments.append({"type": "image", "url": img_url})
        
        last_pos = match.end()

    # Add remaining text
    remaining_text = text_content[last_pos:].strip()
    if remaining_text:
        segments.append({"type": "text", "content": remaining_text})

    return segments

async def _perform_request(url: str, readability_mode: bool) -> tuple[str, str]:
    """Returns (html_content, final_url)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=10.0, verify=False, headers=headers) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text, str(response.url)