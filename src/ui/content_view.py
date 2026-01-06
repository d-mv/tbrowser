from textual.app import ComposeResult
from textual.widgets import Markdown, Static
from textual.containers import VerticalScroll, Center
from textual_image.widget import Image
from textual.message import Message
from PIL import Image as PILImage
import httpx
import io
import logging
import base64

# Configure logging to file for debugging
logging.basicConfig(filename='debug_tbrowser.log', level=logging.INFO)

class BrowserContent(VerticalScroll):
    """
    A scrolling container that renders a mix of Markdown text and Images.
    """

    async def load_segments(self, segments: list[dict], show_images: bool = False):
        """
        Async version that fetches images if necessary and mounts them.
        """
        self.remove_children()
        
        # Standard headers to avoid 403s
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }

        for segment in segments:
            if segment["type"] == "text":
                await self.mount(Markdown(segment["content"]))
            
            elif segment["type"] == "image":
                if not show_images:
                    # Render a placeholder or nothing. 
                    # Let's render a small text indicator so user knows there's an image.
                    await self.mount(Static(f"[Image: {segment.get('url', 'Unknown')}]", classes="image-placeholder"))
                    continue

                try:
                    url = segment["url"]
                    pil_img = None
                    
                    # Handle Data URI
                    if url.startswith("data:"):
                        try:
                            # Format: data:image/png;base64,iVBORw0KGgo...
                            header, encoded = url.split(",", 1)
                            if "base64" in header:
                                img_data = base64.b64decode(encoded)
                                pil_img = PILImage.open(io.BytesIO(img_data))
                        except Exception as e:
                            logging.error(f"Failed to decode base64 image: {e}")
                            await self.mount(Static(f"[Base64 Image Error]"))
                            continue
                            
                    # Handle Remote URL
                    else:
                        # reuse headers!
                        async with httpx.AsyncClient(verify=False, headers=headers) as client:
                            resp = await client.get(url)
                            if resp.status_code == 200:
                                pil_img = PILImage.open(io.BytesIO(resp.content))
                            else:
                                await self.mount(Static(f"[Image Error {resp.status_code}: {url}]"))
                                continue

                    if pil_img:
                        # Convert to grayscale ('L')
                        pil_img = pil_img.convert("L")
                        
                        # Filter out tiny images (likely tracking pixels)
                        if pil_img.width < 5 or pil_img.height < 5:
                            continue

                        # Create Widget
                        w = Image(pil_img)
                        w.classes = "browser-image"
                        
                        # Center the image
                        await self.mount(w)
                        
                except Exception as e:
                    logging.error(f"Error loading image {segment.get('url')}: {e}")
                    await self.mount(Static(f"[Image Failed: {segment.get('url')} - {str(e)}]"))