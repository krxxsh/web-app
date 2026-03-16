import asyncio
import os
from agents.autonomous_orchestrator import AutonomousOrchestrator

async def run_verification():
    """
    Test the Autonomous Framework.
    Simulates a UI issue by providing a reports object manually
    (since a live server might not be running).
    """
    orchestrator = AutonomousOrchestrator()
    
    # Simulate a detected glitch
    simulated_report = {
        "url": "http://localhost:5000/booking",
        "status": "success",
        "console_errors": ["Uncaught ReferenceError: submitBooking is not defined"],
        "glitches": ["Empty Button detected at btn-book-now"],
        "screenshot": "agents/reports/vision/simulated_glitch.png"
    }
    
    print("--- Autonomous Verification Demo ---")
    print(f"Issue: {simulated_report['console_errors'][0]}")
    
    # Analyze the issue
    fix = orchestrator.coder.analyze_glitch(simulated_report)
    print(f"Agent's Analysis & Fix: {fix}")
    
    print("Verification complete.")

if __name__ == "__main__":
    asyncio.run(run_verification())
