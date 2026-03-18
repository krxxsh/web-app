import asyncio
from playwright.async_api import async_playwright
import os
import traceback

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
        # Ensure path starts with /
        if not path.startswith("/") and not path.startswith("http"):
            path = f"/{path}"
            
        if path.startswith("http"):
            url = path.strip()
        else:
            url = f"{self.base_url.rstrip('/')}{path}".strip()
            
        print(f"DEBUG: Constructing URL from base={self.base_url} and path={path} -> {url}")
        
        async with async_playwright() as p:
            try:
                print("DEBUG: Launching browser...")
                browser = await p.chromium.launch(headless=True)
                print("DEBUG: Browser launched. Creating page...")
                page = await browser.new_page()
                
                # Capture console errors
                console_errors = []
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                
                print(f"Scanning {url}...")
                await page.goto(url, wait_until="networkidle")
                print("DEBUG: Page loaded.")
                # Prepare reporting directory
                os.makedirs("agents/reports", exist_ok=True)
                sanitized_url = url.replace("://", "_").replace("/", "_").replace(":", "_")
                screenshot_path = f"agents/reports/vision_scan_{sanitized_url}.png"
                
                await page.screenshot(path=screenshot_path)
                
                # Advanced DOM check for glitches
                glitches = await page.evaluate('''() => {
                    const findings = [];
                    
                    // 1. Check for broken images
                    document.querySelectorAll('img').forEach(img => {
                        if (!img.src || img.naturalWidth === 0) {
                            findings.push(`Broken Image: ${img.src || 'No Source'}`);
                        }
                    });
                    
                    // 2. Check for empty buttons
                    document.querySelectorAll('button').forEach(btn => {
                        if (!btn.innerText.trim() && !btn.querySelector('i, svg') && !btn.getAttribute('aria-label')) {
                            findings.push(`Empty Button detected at class: "${btn.className}"`);
                        }
                    });

                    // 3. Check for overlapping elements (Simple bounding box check)
                    const elements = Array.from(document.querySelectorAll('div, section, main, header, footer'));
                    for (let i = 0; i < Math.min(elements.length, 100); i++) {
                        for (let j = i + 1; j < Math.min(elements.length, 100); j++) {
                            const rect1 = elements[i].getBoundingClientRect();
                            const rect2 = elements[j].getBoundingClientRect();
                            if (rect1.width > 0 && rect1.height > 0 && rect2.width > 0 && rect2.height > 0) {
                                if (!(rect1.right < rect2.left || rect1.left > rect2.right || rect1.bottom < rect2.top || rect1.top > rect2.bottom)) {
                                    // Overlap detected - check if one is inside another
                                    const isContained = (rect1.left >= rect2.left && rect1.right <= rect2.right && rect1.top >= rect2.top && rect1.bottom <= rect2.bottom) ||
                                                        (rect2.left >= rect1.left && rect2.right <= rect1.right && rect2.top >= rect1.top && rect2.bottom <= rect1.bottom);
                                    if (!isContained && (rect1.width * rect1.height) > 100 && (rect2.width * rect2.height) > 100) {
                                        // findings.push(`Potential Overlap: ${elements[i].tagName}.${elements[i].className} and ${elements[j].tagName}.${elements[j].className}`);
                                    }
                                }
                            }
                        }
                    }

                    // 4. Check for invisible text / font-size: 0
                    document.querySelectorAll('*').forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (el.innerText.trim().length > 0 && (style.fontSize === '0px' || style.visibility === 'hidden' || (style.opacity === '0' && style.position !== 'absolute'))) {
                             findings.push(`Invisible Text detected in ${el.tagName} at ${el.className || 'no-class'}`);
                        }
                    });

                    // 5. Check for inputs without labels or aria-labels
                    document.querySelectorAll('input, select, textarea').forEach(input => {
                        if (input.type !== 'hidden' && input.type !== 'submit') {
                            const hasLabel = document.querySelector(`label[for="${input.id}"]`) || input.closest('label');
                            if (!hasLabel && !input.getAttribute('aria-label') && !input.getAttribute('placeholder')) {
                                findings.push(`Input without label/placeholder: id="${input.id}", name="${input.name}"`);
                            }
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
                print(f"ERROR in VisionAgent: {str(e)}")
                traceback.print_exc()
                return {"url": url, "status": "error", "message": str(e)}
            finally:
                await browser.close()

if __name__ == "__main__":
    agent = VisionAgent()
    # Note: Requires local server running
    # asyncio.run(agent.scan_page())
