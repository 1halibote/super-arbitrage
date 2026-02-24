import subprocess
import os
import sys
import time
import webbrowser
import shutil

# ================= Configuration =================
JAVA_HOME = r"C:\tools\java\jdk-21.0.2+13"
JAVA_BIN = os.path.join(JAVA_HOME, "bin", "java.exe")
# Java Memory Limit (Max 512MB)
JAVA_OPTS = ["-Xmx512m", "-Xms256m"]

ENGINE_SCRIPT = os.path.join("trading-engine", "build", "install", "trading-engine", "bin", "trading-engine.bat")
# =================================================

def kill_processes():
    print("[0/3] Cleaning up old processes...")
    current_pid = os.getpid()
    subprocess.run("taskkill /F /IM java.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("taskkill /F /IM node.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(f"wmic process where \"name='python.exe' and processid!={current_pid}\" delete", 
                   shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    print("      Cleaned.")

def clean_frontend_cache():
    """Remove .next folder to fix memory leaks caused by corrupt cache"""
    frontend_next = os.path.join("frontend", ".next")
    if os.path.exists(frontend_next):
        print("      ⚠️ Clearing frontend cache (.next)...")
        try:
            shutil.rmtree(frontend_next)
            print("      Cache cleared.")
        except Exception as e:
            print(f"      Failed to clear cache: {e}")

def start_java():
    print("[1/3] Starting Java Engine (Max 512MB)...")
    env = os.environ.copy()
    env["JAVA_HOME"] = JAVA_HOME
    env["PATH"] = os.path.join(JAVA_HOME, "bin") + os.pathsep + env["PATH"]
    env["JAVA_OPTS"] = " ".join(JAVA_OPTS)
    
    if not os.path.exists(ENGINE_SCRIPT):
        print(f"Error: Java script not found at {ENGINE_SCRIPT}")
        return

    subprocess.Popen(ENGINE_SCRIPT, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
    print("      Java starting (waiting 3s)...")
    time.sleep(3)

def start_python():
    print("[2/3] Starting Python Backend...")
    # Use backend/run.py for Windows stability
    subprocess.Popen([sys.executable, "backend/run.py"], 
                     creationflags=subprocess.CREATE_NEW_CONSOLE)
    print("      Python starting (waiting 3s)...")
    time.sleep(3)

def start_frontend():
    print("[3/3] Starting Frontend (Max 512MB)...")
    
    # 1. Clean cache first
    clean_frontend_cache()
    
    frontend_dir = os.path.join(os.getcwd(), "frontend")
    
    # 2. Set strict memory limit
    env = os.environ.copy()
    env["NODE_OPTIONS"] = "--max-old-space-size=512"
    
    subprocess.Popen("npm run dev", shell=True, cwd=frontend_dir, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
    print("      Frontend starting...")

def main():
    print("=== BN-BY System Launcher (Safe Mode) ===")
    kill_processes()
    # start_java() -> Removed
    start_python()
    start_frontend()
    
    print("\nSystem started!")
    print("UI: http://localhost:3000")
    print("API: http://localhost:8000/docs")

if __name__ == "__main__":
    main()
