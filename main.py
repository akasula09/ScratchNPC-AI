import os
import time
import threading
import requests
from flask import Flask
import scratchattach as sa

app = Flask(__name__)

# --- CONFIGURATION (Load from Environment Variables for Security) ---
# It is highly recommended to set these in your Render Dashboard Environment Variables!
PROJECT_ID = os.environ.get("PROJECT_ID", "YOUR_PROJECT_ID")
USERNAME = os.environ.get("SCRATCH_USERNAME", "YourScratchUsername")
PASSWORD = os.environ.get("SCRATCH_PASSWORD", "YourScratchPassword")
VARIABLE_NAME = "YOUR_VARIABLE_NAME" # Do not include the cloud emoji
RENDER_APP_URL = os.environ.get("RENDER_APP_URL", "") # e.g. "https://scratchnpc-ai.onrender.com"

# Global state to keep track of the latest data safely across threads
shared_data = {
    "latest_value": None,
    "last_updated": 0,
    "websocket_connected": False
}

# --- FLASK WEB SERVER ROUTES ---
@app.route("/")
def home():
    status = "Connected" if shared_data["websocket_connected"] else "Polling Fallback Active"
    return {
        "status": "NPC Brain is active and running!",
        "scratch_connection": status,
        "last_tracked_value": shared_data["latest_value"],
        "last_updated_epoch": shared_data["last_updated"]
    }

@app.route("/get_var")
def get_var():
    # An endpoint you can call to instantly see what the server has stored
    return {
        "variable": VARIABLE_NAME,
        "value": shared_data["latest_value"],
        "last_updated": shared_data["last_updated"]
    }


# --- THE FOOLPROOF SCRATCH LISTENER & RECONNECTOR ---
def start_scratch_services():
    """
    Main supervisor thread. It initializes the websocket listener and 
    continually checks to ensure the connection is healthy.
    """
    print("[Supervisor] Initializing Scratch services...")
    
    while True:
        try:
            # 1. Login & Establish Cloud Connection
            session = sa.login(USERNAME, PASSWORD)
            cloud = session.connect_scratch_cloud(PROJECT_ID)
            
            # 2. Grab initial value via HTTP request immediately so we aren't blank on startup
            try:
                initial_val = sa.get_var(PROJECT_ID, VARIABLE_NAME)
                shared_data["latest_value"] = initial_val
                shared_data["last_updated"] = time.time()
                print(f"[Supervisor] Successfully pulled initial value: {initial_val}")
            except Exception as e:
                print(f"[Warning] Direct API fetch failed on start: {e}")

            # 3. Setup WebSocket event listeners
            events = cloud.events()

            @events.event
            def on_set(activity):
                if activity.var == VARIABLE_NAME:
                    shared_data["latest_value"] = activity.value
                    shared_data["last_updated"] = time.time()
                    print(f"[WebSocket] Cloud Update Detected: {activity.value}")

            @events.event
            def on_ready():
                shared_data["websocket_connected"] = True
                print("[WebSocket] Connected and listening live to Scratch cloud!")

            # Start event listener in a non-blocking thread
            # ignore_exceptions=True keeps the thread alive if a single message is malformed
            events.start(thread=True, ignore_exceptions=True)
            
            # 4. Connection Health Watchdog Loop
            # This loops forever. If the websocket goes dead, it breaks out and triggers a reconnect.
            missed_pings = 0
            while True:
                time.sleep(15) # Check health every 15 seconds
                
                # Check if the connection dropped
                if not events.running:
                    print("[Watchdog] WebSocket has stopped running. Initiating reconnection...")
                    shared_data["websocket_connected"] = False
                    break
                
                # Double-check fallback: Force a direct variable pull every 60 seconds
                # This guarantees that even if the WebSocket is silently dead, we still get updates.
                try:
                    fresh_val = sa.get_var(PROJECT_ID, VARIABLE_NAME)
                    if fresh_val != shared_data["latest_value"]:
                        shared_data["latest_value"] = fresh_val
                        shared_data["last_updated"] = time.time()
                        print(f"[Fallback Pull] Caught missing value change: {fresh_val}")
                except Exception as e:
                    print(f"[Watchdog] Fallback API check failed: {e}")

        except Exception as e:
            print(f"[Supervisor] Connection error: {e}. Retrying in 10 seconds...")
            shared_data["websocket_connected"] = False
            time.sleep(10)


# --- ANTI-SLEEP PINGER (Keep Render Free Tier Awake) ---
def self_ping_loop():
    """
    If RENDER_APP_URL is provided, this pings the server every 10 minutes
    so Render doesn't spin down the container due to inactivity.
    """
    if not RENDER_APP_URL:
        print("[Pinger] No RENDER_APP_URL provided. Self-pinging disabled.")
        return
        
    print(f"[Pinger] Active. Target: {RENDER_APP_URL}")
    while True:
        time.sleep(600) # Ping every 10 minutes (600 seconds)
        try:
            response = requests.get(RENDER_APP_URL, timeout=10)
            print(f"[Pinger] Ping sent. Status code: {response.status_code}")
        except Exception as e:
            print(f"[Pinger] Ping failed: {e}")


# --- APPLICATION ENTRY POINT ---
if __name__ == "__main__":
    # 1. Start the Scratch supervisor in a background daemon thread
    scratch_thread = threading.Thread(target=start_scratch_services, daemon=True)
    scratch_thread.start()
    
    # 2. Start the self-ping loop in a background daemon thread
    ping_thread = threading.Thread(target=self_ping_loop, daemon=True)
    ping_thread.start()
    
    # 3. Start Flask on the main thread
    # Render binds to port 10000 by default
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
