import asyncio
import os
import sys
# Add project root to path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from runner.browser_manager import BrowserManager
from runner.session_manager import SessionManager
from runner.perception.yolo_perception import YOLOPerception
from reasoner.reasoner import Reasoner
from reasoner.schemas import ActionSchema
from runner.action_executor import ActionExecutor
from runner.logger import log

# Re-implementing the loop logic locally to avoid API overhead for CLI usage
async def run_agent(goal: str, url: str = None):
    print(f"Starting agent with goal: {goal}")
    
    # Init services
    bm = BrowserManager()
    await bm.start()
    sm = SessionManager(bm)
    perception = YOLOPerception() # Uses config default or env var
    reasoner = Reasoner()
    
    try:
        # Create session
        session_id = await sm.create_session(video=True)
        print(f"Session created: {session_id}")
        
        meta = sm.get_session(session_id)
        page = meta.page
        executor = ActionExecutor(page, session_id=session_id)
        
        # Initial navigation if provided
        if url:
            print(f"Navigating to {url}...")
            await executor.navigate(url, timeout_ms=30000)
        
        # Loop
        max_steps = 10
        history = []
        
        for step in range(1, max_steps + 1):
            print(f"\n--- Step {step} ---")
            
            # 1. Snapshot
            screenshot_path = await sm.snapshot(session_id, f"step_{step}.png")
            
            # 2. Perception
            elements = perception.analyze(screenshot_path)
            elements_list = [e.dict() for e in elements]
            print(f"Perception: Found {len(elements)} elements")
            
            # 3. Reasoner
            print("Reasoning...")
            action_schema = reasoner.plan_one(goal, elements_list, last_actions=history)
            print(f"Action: {action_schema.action} {action_schema.target} {action_schema.value or ''}")
            
            if action_schema.action == "noop":
                print("Goal achieved or no action possible.")
                break
                
            # 4. Execute
            # (Simplified execution logic matching plan_execute.py)
            # ... (I'll implement the mapping logic here briefly or import if possible, 
            # but for a standalone script it's safer to copy the critical bits or refactor. 
            # I'll copy the mapping logic for now to keep it self-contained)
            
            # ... execution logic ...
            # For brevity in this thought process, I will assume the user wants to see it run.
            # I will implement the basic execution mapping.
            
            target = action_schema.target
            val = action_schema.value
            
            if action_schema.action == "navigate":
                await executor.navigate(val)
            elif action_schema.action == "click":
                if target.by == "coords":
                    x, y = map(int, target.value.split(","))
                    await executor.click_xy(x, y)
                elif target.by == "id":
                    # find element
                    el = next((e for e in elements_list if e["id"] == target.value), None)
                    if el:
                        x1, y1, x2, y2 = el["bbox"]
                        await executor.click_xy((x1+x2)//2, (y1+y2)//2)
                elif target.by == "selector":
                    await executor.click_selector(target.value)
            elif action_schema.action == "type":
                if target.by == "selector":
                    await executor.type_selector(target.value, val)
                elif target.by == "id":
                     el = next((e for e in elements_list if e["id"] == target.value), None)
                     if el:
                        x1, y1, x2, y2 = el["bbox"]
                        await executor.type_xy((x1+x2)//2, (y1+y2)//2, val)
            # ... add other actions as needed ...
            
            history.append({"action": action_schema.dict()})
            await asyncio.sleep(1) # brief pause
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Stopping BrowserManager...")
        try:
            if 'sm' in locals():
                await sm.close_session(session_id, keep_artifacts=True)
            if 'bm' in locals():
                await bm.stop()
        except RuntimeError:
            # Ignore event loop closed errors during cleanup
            pass
        except Exception as e:
            print(f"Error during cleanup: {e}")
        print("Session closed.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("goal", help="Goal for the agent")
    parser.add_argument("--url", help="Starting URL")
    args = parser.parse_args()
    
    try:
        asyncio.run(run_agent(args.goal, args.url))
    except RuntimeError as e:
        if str(e) == "Event loop is closed":
            pass
        else:
            raise
