import os
import sys
import multiprocessing
import threading
import time
import warnings
import requests
from flask import Flask
import scratchattach as sa
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

# --- 2. MATH-BASED ENCODER & DECODER ---
def custom_encode(text):
    encoded_string = ""
    text = text.lower()
    for char in text:
        if 'a' <= char <= 'z':
            position = ord(char) - ord('a') + 1
            code = (position * 2) + 19
            encoded_string += str(code)
        elif char == ' ':
            encoded_string += "10"
        else:
            encoded_string += "10"
    return encoded_string

def custom_decode(numeric_string):
    decoded_string = ""
    for i in range(0, len(numeric_string), 2):
        pair = numeric_string[i:i+2]
        if pair:
            try:
                code = int(pair)
                if 21 <= code <= 71 and code % 2 != 0:
                    position = (code - 19) // 2
                    char = chr(position + ord('a') - 1)
                    decoded_string += char
                elif code == 10:
                    decoded_string += " "
                else:
                    decoded_string += "?"
            except ValueError:
                pass
    return decoded_string

# --- 3. CREDENTIALS & CONSTANTS ---
GROQ_API_KEY = "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"
SCRATCH_USER = "Pyroshape"
SCRATCH_SESSION_ID = ".eJxVj8tOwzAQRf_F6zbYrvNwdiAkukCIdkHFKprYk8aktSvbVQSIf2ciddPd6J6Zo7m_7Jowejgja9n7dwxphAuyFevgmsdugZ2zxESllWzKpiLWg_dI4QCnhCuWMWUTwuQWxxziROxO0IOZ0C-WJUOfnYHsgi9uIBV7vJxu4dNtmbyBBjqSwG1pa9U0UqseuB4aY6CHAQYLmot2t09pFxU_rLeDnbfdy_j8GvX64zBPpDmFo_NrdyFTLQop60KUm0LUilgyEbIZMbI2xyt1sV_gj6HL7ow_wS-FHs8Y6bWHN5y7Typ3X22ENNJSwzmUVnIx2NrqjcBKGA2otKlVbSopBH1OOfv7B176eC0:1wkXce:FwGlqQDOV-bQNbjlX2geU5QCk2w"
PROJECT_ID = "1362701122"
RENDER_APP_URL = "https://scratchnpc-ai.onrender.com"

groq_client = Groq(api_key=GROQ_API_KEY)
cloud_monitor = None

# --- 4. THE LIVE STATUS BACKGROUND LOOP ---
# Runs in its own thread to constantly check variable health, update telemetry,
# and provide a clean connection we can write to safely.
def monitor_cloud_variables(session):
    global cloud_monitor
    log("[Monitor] Live telemetry monitoring thread starting...")
    
    while True:
        try:
            # Create a fresh, non-blocking connection
            cloud_monitor = session.connect_cloud(PROJECT_ID)
            log("[Monitor] Live telemetry connection established.")
            
            while True:
                # Direct API pull bypasses websocket cache and forces live data
                prompt_val = cloud_monitor.get_var("AI_PROMPT")
                response_val = cloud_monitor.get_var("AI_RESPONSE")
                
                decoded_prompt = custom_decode(prompt_val) if prompt_val else "None"
                decoded_response = custom_decode(response_val) if response_val else "None"
                
                log(f"[LIVE STATUS] ☁ AI_PROMPT: {prompt_val} ('{decoded_prompt}') | ☁ AI_RESPONSE: {response_val} ('{decoded_response}')")
                time.sleep(5)
                
        except Exception as e:
            log(f"[Monitor Error] Telemetry update or connection failed: {e}. Reconnecting in 10s...")
            time.sleep(10)

# --- 5. THE MAIN CLOUD VARIABLE LISTENER ---
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
                        # Decode incoming message
                        decoded_prompt = custom_decode(encoded_prompt)
                        log(f"[Scratch Bot] Decoded Prompt: {decoded_prompt}")

                        # Query Groq using the correct current Llama 3.1 model
                        chat_completion = groq_client.chat.completions.create(
                            messages=[
                                {
                                    "role": "system", 
                                    "content": "You are a friendly wizard NPC in a Scratch game. Keep your response short, max 100 characters."
                                },
                                {"role": "user", "content": decoded_prompt}
                            ],
                            model="llama-3.1-8b-instant",
                        )
                        ai_reply = chat_completion.choices[0].message.content
                        log(f"[Scratch Bot] Groq AI Reply: {ai_reply}")

                        # Encode response
                        encoded_reply = custom_encode(ai_reply)
                        
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
                                cloud_monitor.set_var("AI_RESPONSE", custom_encode("error"))
                        except Exception as cloud_err:
                            log(f"[Scratch Bot] Failed to write error to cloud: {cloud_err}")

            @events.event
            def on_ready():
                log("=== [Scratch Bot] Live & Monitoring ☁ AI_PROMPT ===")

            # Run event loop. If it crashes, the outer loop will catch it and restart the session.
            events.start(thread=False)

        except Exception as e:
            log(f"[Scratch Bot Connection Error] {e}. Restarting bot connection in 10 seconds...")
            time.sleep(10)

# --- 6. ANTI-SLEEP PINGER ---
def self_ping_loop():
    log(f"[Pinger] Active. Target: {RENDER_APP_URL}")
    while True:
        time.sleep(600)  # Ping Render once every 10 minutes (600s)
        try:
            response = requests.get(RENDER_APP_URL, timeout=10)
            log(f"[Pinger] Ping sent. Status code: {response.status_code}")
        except Exception as e:
            log(f"[Pinger] Ping failed: {e}")

# --- 7. SECURE BACKGROUND INITIALIZATION ---
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
