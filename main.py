import os
import sys
import multiprocessing
import threading
import time
import warnings
import re
import requests
from flask import Flask
import scratchattach as sa
from scratchattach import Encoding
from groq import Groq

# Suppress the scratchattach credentials warning to keep logs clean
warnings.filterwarnings('ignore', category=sa.LoginDataWarning)

# --- 1. SET UP FLASK ---
app = Flask('')

@app.route('/')
def home():
    return "NPC Brain is active and running!"

def log(message):
    print(message, flush=True)

# --- 2. CREDENTIALS & CONSTANTS (HARDCODED DUMMY VALUES) ---
GROQ_API_KEY = "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"
SCRATCH_USER = "Pyroshape"
SCRATCH_SESSION_ID = ".eJxVj8luwyAURf-FdeyayUN2ddetOqiLrqwHPGISGyJDmjRV_71YyiY7dO95R9xfcoq4eJiRbElR9BNcnd-9ugtOsSjIhgxwSuOwQoMzmaGCtZVkFc2dAu8xhxamiBuSMCYdwsGtrnNYDrm7EyjQB_SrZc3QJ6chueDLWxHLdzxOt7C_wdkb8iMfCdkybuu2QqkEmLatKGdGWqtE14Bst11Qe_4xzP2n8OpJT3O_jD8Ov58vb1kzhZ3zhTtmU0NLxpqSSl7SRuQu6gWSHnEh27Sc8hazB78LQ3IzXoNfBz3OuOSvPbzgefjK4-6njRDHDJkGtWCmriVDgVZKXRngNe3QcA4WQVlsOi3J3z9M_3uL:1wkmHZ:3leSxp6FZvU0nv-pFEklw1E1jcM"
PROJECT_ID = "1362701122"
RENDER_APP_URL = "https://scratchnpc-ai.onrender.com"

groq_client = Groq(api_key=GROQ_API_KEY)
cloud_monitor = None

# --- 3. THE LIVE STATUS BACKGROUND LOOP ---
def monitor_cloud_variables(session):
    global cloud_monitor
    log("[Monitor] Live telemetry monitoring thread starting...")
    
    while True:
        try:
            cloud_monitor = session.connect_cloud(PROJECT_ID)
            log("[Monitor] Live telemetry connection established.")
            
            while True:
                # Direct API pull bypasses websocket cache and forces live data
                prompt_val = cloud_monitor.get_var("AI_PROMPT")
                response_val = cloud_monitor.get_var("AI_RESPONSE")
                
                # Decode values using scratchattach's built-in decoder
                decoded_prompt = Encoding.decode(prompt_val) if prompt_val else "None"
                decoded_response = Encoding.decode(response_val) if response_val else "None"
                
                log(f"[LIVE STATUS] ☁ AI_PROMPT: {prompt_val} ('{decoded_prompt}') | ☁ AI_RESPONSE: {response_val} ('{decoded_response}')")
                time.sleep(5)
                
        except Exception as e:
            log(f"[Monitor Error] Telemetry update failed: {e}. Reconnecting in 10s...")
            time.sleep(10)

# --- 4. THE MAIN CLOUD VARIABLE LISTENER ---
def run_scratch_bot():
    global cloud_monitor
    log("=== [Scratch Bot Process] Starting Up ===")
    
    while True:
        try:
            session = sa.login_by_id(SCRATCH_SESSION_ID, username=SCRATCH_USER)
            
            # Start/Restart telemetry monitoring thread with this session
            monitor_thread = threading.Thread(target=monitor_cloud_variables, args=(session,), daemon=True)
            monitor_thread.start()
            
            # Connection A: Strictly for listening to incoming updates live
            cloud_events = session.connect_cloud(PROJECT_ID)
            events = cloud_events.events()

            @events.event
            def on_set(activity):
                if activity.var == "AI_PROMPT":
                    encoded_prompt = activity.value
                    
                    if not encoded_prompt or encoded_prompt == "0" or encoded_prompt == "":
                        return

                    log(f"[Scratch Bot] New encoded prompt received: {encoded_prompt}")
                    
                    try:
                        # Decode incoming message using built-in scratchattach
                        decoded_prompt = Encoding.decode(encoded_prompt)
                        log(f"[Scratch Bot] Decoded Prompt: {decoded_prompt}")

                        # Query Groq with strict formatting instructions
                        chat_completion = groq_client.chat.completions.create(
                            messages=[
                                {
                                    "role": "system", 
                                    "content": "You are a friendly wizard NPC in a Scratch game. "
                                               "Keep your response short, max 100 characters. "
                                               "CRITICAL: You must only use lowercase letters (a-z) and spaces. "
                                               "Do not use ANY punctuation, periods, commas, apostrophes, or capital letters."
                                },
                                {"role": "user", "content": decoded_prompt}
                            ],
                            model="llama-3.1-8b-instant",
                        )
                        raw_reply = chat_completion.choices[0].message.content
                        log(f"[Scratch Bot] Raw Groq AI Reply: {raw_reply}")

                        # Force strict filter: absolute insurance against symbols or capitals
                        clean_reply = raw_reply.lower()
                        clean_reply = re.sub(r'[^a-z ]', '', clean_reply)
                        log(f"[Scratch Bot] Filtered AI Reply: {clean_reply}")

                        # Encode response using built-in scratchattach
                        encoded_reply = Encoding.encode(clean_reply)
                        
                        # Push to Scratch using our separate write pipeline
                        if cloud_monitor is not None:
                            cloud_monitor.set_var("AI_RESPONSE", encoded_reply)
                            log(f"[Scratch Bot] Updated ☁ AI_RESPONSE to: {encoded_reply}")
                        else:
                            log("[Scratch Bot] Write postponed: cloud_monitor connection is warming up...")

                    except Exception as e:
                        log(f"[Scratch Bot] Processing Error: {e}")
                        try:
                            if cloud_monitor is not None:
                                cloud_monitor.set_var("AI_RESPONSE", Encoding.encode("error"))
                        except Exception as cloud_err:
                            log(f"[Scratch Bot] Failed to write error to cloud: {cloud_err}")

            @events.event
            def on_ready():
                log("=== [Scratch Bot] Live & Monitoring ☁ AI_PROMPT ===")

            events.start(thread=False)

        except Exception as e:
            log(f"[Scratch Bot Connection Error] {e}. Restarting bot connection in 10 seconds...")
            time.sleep(10)

# --- 5. ANTI-SLEEP PINGER ---
def self_ping_loop():
    log(f"[Pinger] Active. Target: {RENDER_APP_URL}")
    while True:
        time.sleep(600)  # Ping Render once every 10 minutes
        try:
            response = requests.get(RENDER_APP_URL, timeout=10)
            log(f"[Pinger] Ping sent. Status code: {response.status_code}")
        except Exception as e:
            log(f"[Pinger] Ping failed: {e}")

# --- 6. SECURE BACKGROUND INITIALIZATION ---
if os.environ.get("RENDERS_BOT_SPAWNED") != "true":
    os.environ["RENDERS_BOT_SPAWNED"] = "true"
    
    # Run the main Scratch bot process
    bot_process = multiprocessing.Process(target=run_scratch_bot)
    bot_process.daemon = True
    bot_process.start()
    
    # Run the anti-sleep self-pinger thread
    ping_thread = threading.Thread(target=self_ping_loop, daemon=True)
    ping_thread.start()
    
    log("=== [Main Web] Spawned Scratch Bot & Keep-Alive Systems ===")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
