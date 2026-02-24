import sys
import os
import asyncio
import logging

# Ensure we're running from the project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
os.chdir(project_root)
sys.path.insert(0, project_root)

# FIX: aiodns requires SelectorEventLoop on Windows.
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    # Log that we are using the custom runner
    print(">>> Starting Backend (Custom Runner) <<<")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
