import asyncio
from playwright.async_api import async_playwright
import os

class VisionAgent:
    """
    Autonomous UI Scanner.
    Detects visual glitches, broken elements, and console errors.
    """
    
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.reports_dir = "agents/reports/vision"
        os.makedirs(self.reports_dir, exist_ok=True)

    async def scan_page(self, path="/"):
        """Scans a specific page for errors and glitches."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Capture console errors
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            
            url = f"{self.base_url}{path}"
            print(f"Scanning {url}...")
            
            try:
                await page.goto(url, wait_until="networkidle")
                
                # Take screenshot for visual analysis
                screenshot_path = os.path.join(self.reports_dir, f"scan_{path.replace('/', '_')}.png")
                await page.screenshot(path=screenshot_path)
                
                # Simple DOM check for obvious glitches (e.g., empty buttons, broken images)
                glitches = await page.evaluate('''() => {
                    const findings = [];
                    // Check for images with no source or broken source
                    document.querySelectorAll('img').forEach(img => {
                        if (!img.src || img.naturalWidth === 0) {
                            findings.append(`Broken Image: ${img.src}`);
                        }
                    });
                    
                    // Check for buttons with no text or icons
                    document.querySelectorAll('button').forEach(btn => {
                        if (!btn.innerText.trim() && !btn.querySelector('i, svg')) {
                            findings.append(`Empty Button detected at ${btn.className}`);
                        }
                    });
                    
                    return findings;
                }''')
                
                return {
                    "url": url,
                    "screenshot": screenshot_path,
                    "console_errors": console_errors,
                    "glitches": glitches,
                    "status": "success"
                }
                
            except Exception as e:
                return {"url": url, "status": "error", "message": str(e)}
            finally:
                await browser.close()

if __name__ == "__main__":
    agent = VisionAgent()
    # Note: Requires local server running
    # asyncio.run(agent.scan_page())
