import os
import sys
import multiprocessing
import threading
import time
from flask import Flask
import scratchattach as sa
from groq import Groq

# --- 1. SET UP FLASK ---
app = Flask('')

@app.route('/')
def home():
    return "NPC Brain is active and running!"

def log(message):
    print(message, flush=True)

# --- 2. MATH-BASED ENCODER & DECODER ---
# Formula: Code = (Letter_Position * 2) + 19
# Space maps to '10'. Unrecognized characters default to '10'.

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

# --- 3. SET UP CREDENTIALS ---
GROQ_API_KEY = "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"
SCRATCH_USER = "Pyroshape"
SCRATCH_SESSION_ID = ".eJxVj8tOwzAQRf_F6zbYrvNwdiAkukCIdkHFKprYk8aktSvbVQSIf2ciddPd6J6Zo7m_7Jowejgja9n7dwxphAuyFevgmsdugZ2zxESllWzKpiLWg_dI4QCnhCuWMWUTwuQWxxziROxO0IOZ0C-WJUOfnYHsgi9uIBV7vJxu4dNtmbyBBjqSwG1pa9U0UqseuB4aY6CHAQYLmot2t09pFxU_rLeDnbfdy_j8GvX64zBPpDmFo_NrdyFTLQop60KUm0LUilgyEbIZMbI2xyt1sV_gj6HL7ow_wS-FHs8Y6bWHN5y7Typ3X22ENNJSwzmUVnIx2NrqjcBKGA2otKlVbSopBH1OOfv7B176eC0:1wkXce:FwGlqQDOV-bQNbjlX2geU5QCk2w"
PROJECT_ID = "1362701122"

groq_client = Groq(api_key=GROQ_API_KEY)

# --- 4. THE LIVE STATUS BACKGROUND LOOP ---
def monitor_cloud_variables(cloud_connection):
    log("[Monitor] Live telemetry monitoring thread started.")
    while True:
        try:
            # Grab the current states directly from Scratch's memory
            prompt_val = cloud_connection.get_var("AI_PROMPT")
            response_val = cloud_connection.get_var("AI_RESPONSE")
            
            # Decode them on the fly for your logs to see exactly what they mean
            decoded_prompt = custom_decode(prompt_val) if prompt_val else "None"
            decoded_response = custom_decode(response_val) if response_val else "None"
            
            log(f"[LIVE AND RUNNING] ☁ AI_PROMPT: {prompt_val} (Decoded: '{decoded_prompt}') | ☁ AI_RESPONSE: {response_val} (Decoded: '{decoded_response}')")
        except Exception as e:
            log(f"[Monitor Error] Telemetry update failed: {e}")
        
        time.sleep(5)

# --- 5. THE MAIN CLOUD VARIABLE LISTENER ---
def run_scratch_bot():
    log("=== [Scratch Bot Process] Starting Up ===")
    try:
        session = sa.login_by_id(SCRATCH_SESSION_ID, username=SCRATCH_USER)
        cloud = session.connect_cloud(PROJECT_ID)
        
        # Start our telemetry monitor in a background thread
        monitor_thread = threading.Thread(target=monitor_cloud_variables, args=(cloud,), daemon=True)
        monitor_thread.start()
        
        events = cloud.events()

        @events.event
        def on_set(activity):
            if activity.var == "AI_PROMPT":
                encoded_prompt = activity.value
                
                if not encoded_prompt or encoded_prompt == "0":
                    return

                log(f"[Scratch Bot] New encoded prompt received: {encoded_prompt}")
                
                try:
                    # 1. Decode incoming message
                    decoded_prompt = custom_decode(encoded_prompt)
                    log(f"[Scratch Bot] Decoded Prompt: {decoded_prompt}")

                    # 2. Query the AI
                    chat_completion = groq_client.chat.completions.create(
                        messages=[
                            {
                                "role": "system", 
                                "content": "You are a friendly wizard NPC in a Scratch game. Keep your response short, max 100 characters."
                            },
                            {"role": "user", "content": decoded_prompt}
                        ],
                        model="llama3-8b-8192",
                    )
                    ai_reply = chat_completion.choices[0].message.content
                    log(f"[Scratch Bot] Groq AI Reply: {ai_reply}")

                    # 3. Encode response using the math formula
                    encoded_reply = custom_encode(ai_reply)
                    
                    # 4. Push to Scratch Cloud
                    cloud.set_var("AI_RESPONSE", encoded_reply)
                    log(f"[Scratch Bot] Updated ☁ AI_RESPONSE to: {encoded_reply}")

                except Exception as e:
                    log(f"[Scratch Bot] Processing Error: {e}")
                    try:
                        cloud.set_var("AI_RESPONSE", custom_encode("error"))
                    except Exception as cloud_err:
                        log(f"[Scratch Bot] Failed to write error to cloud: {cloud_err}")

        @events.event
        def on_ready():
            log("=== [Scratch Bot] Live & Monitoring ☁ AI_PROMPT ===")

        events.start()

    except Exception as e:
        log(f"[Scratch Bot] FAILED TO START: {e}")

# --- 6. SECURE BACKGROUND INITIALIZATION ---
if os.environ.get("RENDERS_BOT_SPAWNED") != "true":
    os.environ["RENDERS_BOT_SPAWNED"] = "true"
    bot_process = multiprocessing.Process(target=run_scratch_bot)
    bot_process.daemon = True
    bot_process.start()
    log("=== [Main Web] Spawned Scratch Bot Process successfully ===")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
