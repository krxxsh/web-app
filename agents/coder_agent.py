import os
import google.generativeai as genai

class CoderAgent:
    """
    Autonomous Code Generation & Repair Engine.
    Takes vision reports and applies fixes to the codebase.
    """
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None

    def analyze_glitch(self, report, source_code=""):
        """
        Analyzes a VisionAgent report and determines the root cause.
        """
        # --- MOCK MODE FOR DEMO ---
        if not self.api_key:
            print("DEBUG: CoderAgent running in MOCK MODE (No API Key).")
            glitches = report.get('glitches', [])
            console_errors = report.get('console_errors', [])
            
            new_code = source_code
            
            # 1. Fix Contrast/Opacity
            if any("Invisible Text" in g for g in glitches) or "Contrast glitch" in str(report):
                print("DEBUG: Mocking fix for Contrast/Opacity...")
                new_code = new_code.replace('opacity: 0.1;', 'opacity: 1;')
                new_code = new_code.replace('color: #fafafa; background: #fff;', 'color: #333; background: #fff;')
            
            # 2. Fix Overlapping Sections (The overlapping card)
            if "Overlapping" in str(report) or "overlap" in str(report).lower():
                print("DEBUG: Mocking fix for Overlapping Card...")
                new_code = new_code.replace('margin-top: -150px;', 'margin-top: 20px;')
                new_code = new_code.replace('position: absolute;', 'position: relative;')

            # 3. Fix Hidden Submit Button
            if any("Submit Button" in g for g in glitches) or "button" in str(report).lower():
                print("DEBUG: Mocking fix for Hidden Submit Button...")
                new_code = new_code.replace('display: none !important;', 'display: block;')
                new_code = new_code.replace('visibility: hidden;', 'visibility: visible;')
            
            # Simple fallback if no specific mock matched but glitches exist
            if new_code == source_code and (glitches or console_errors):
                 print("DEBUG: Generic mock fix applied.")
                 new_code = new_code.replace('/* CHAOS_START */', '').replace('/* CHAOS_END */', '')

            return new_code
        # --------------------------

        prompt = f"""
        You are an expert Frontend Developer.
        Analyze the following UI Glitch Report and the provided source code.
        Propose a specific code fix for the file.
        
        URL: {report['url']}
        Console Errors: {report['console_errors']}
        Detected Glitches: {report['glitches']}
        
        SOURCE CODE:
        {source_code}
        
        Provide ONLY the corrected code for the relevant file.
        Do not explain. Surround the code with Triple Backticks.
        """
        
        print(f"Analyzing report for {report['url']}...")
        try:
            response = self.model.generate_content(prompt)
            # Simple parsing for the code block
            fix = response.text.strip()
            if "```" in fix:
                fix = fix.split("```")[1]
                if fix.startswith("python") or fix.startswith("html") or fix.startswith("css") or fix.startswith("javascript"):
                    fix = "\n".join(fix.split("\n")[1:])
            return fix
        except Exception as e:
            return f"Error during analysis: {str(e)}"

    def apply_fix(self, file_path, fix_content):
        """
        Applies a generated fix to a file.
        """
        if not fix_content or "Error" in fix_content:
            print(f"Skipping fix application for {file_path} due to error or empty content.")
            return False

        print(f"Applying fix to {file_path}...")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fix_content)
            print("Fix applied successfully.")
            return True
        except Exception as e:
            print(f"Failed to apply fix: {str(e)}")
            return False

if __name__ == "__main__":
    agent = CoderAgent()
    # agent.analyze_glitch({"url": "http://localhost:5000", "console_errors": [], "glitches": []})
