import asyncio
import os
from agents.vision_agent import VisionAgent
from agents.coder_agent import CoderAgent

class AutonomousOrchestrator:
    """
    Orchestrates the autonomous cycle: Analyze -> Fix -> Verify.
    """
    
    def __init__(self, base_url="http://localhost:5000"):
        self.vision = VisionAgent(base_url=base_url)
        self.coder = CoderAgent()
        self.base_url = base_url
        self.fix_history = []

    def map_url_to_file(self, path):
        """
        Maps a URL path to a physical file in the codebase.
        This is a heuristic for demonstration.
        """
        if path == "/" or path == "/index":
            return "frontend/templates/index.html"
        elif path == "/chaos":
            return "backend/templates/chaos_dashboard.html"
        
        # Try finding in templates
        template_name = path.strip("/") + ".html"
        potential_path = os.path.join("frontend/templates", template_name)
        if os.path.exists(potential_path):
            return potential_path
        
        return None

    async def run_cycle(self, path="/"):
        """
        Runs one iteration of the autonomous repair cycle.
        """
        url = self.base_url + path
        print(f"\n--- Starting Autonomous Cycle for {url} ---")
        
        # 1. SCAN
        print("[1/4] Scanning page for glitches...")
        report = await self.vision.scan_page(url)
        
        if report.get('status') == 'error':
            print(f"Scan failed: {report.get('message')}")
            return False

        if not report.get('glitches') and not report.get('console_errors'):
            print("No issues detected. Site is healthy.")
            return True

        print(f"Issues detected: {len(report.get('glitches', []))} glitches, {len(report.get('console_errors', []))} errors.")

        # 2. ANALYZE & PROPOSE FIX
        print("[2/4] Analyzing issues and generating fix...")
        target_file = self.map_url_to_file(path)
        if not target_file:
            print(f"Could not map URL {path} to a file. Aborting.")
            return False

        source_code = ""
        if os.path.exists(target_file):
            with open(target_file, 'r', encoding='utf-8') as f:
                source_code = f.read()

        fix_proposal = self.coder.analyze_glitch(report, source_code)
        
        # 3. APPLY FIX
        print("[3/4] Applying proposed fix...")
        success = self.coder.apply_fix(target_file, fix_proposal)
        
        if success:
            self.fix_history.append({"url": url, "file": target_file, "fix": fix_proposal})
            
            # 4. VERIFY
            print("[4/4] Verifying fix...")
            await asyncio.sleep(2) # Give server time to reload if needed
            new_report = await self.vision.scan_page(url)
            
            if len(new_report.get('glitches', [])) < len(report.get('glitches', [])):
                print("Verification SUCCESS: Issues reduced.")
                return True
            else:
                print("Verification FAILED: Issues still present.")
                return False
        
        return False

if __name__ == "__main__":
    orchestrator = AutonomousOrchestrator()
    asyncio.run(orchestrator.run_cycle("/chaos"))
