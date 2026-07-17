import os
import sys
import multiprocessing
import time
from flask import Flask
import scratchattach as sa
from scratchattach import Encoding
from groq import Groq

# --- 1. SET UP FLASK ---
app = Flask('')

@app.route('/')
def home():
    return "NPC Brain is active and running!"

def log(message):
    print(message, flush=True)

# --- 2. SET UP CREDENTIALS ---
GROQ_API_KEY = "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"
SCRATCH_USER = "Pyroshape"
SCRATCH_PASS = "Grandmaster@17"
PROJECT_ID = "1362701122"

groq_client = Groq(api_key=GROQ_API_KEY)

# --- 3. THE CLOUD VARIABLE LISTENER ---
def run_scratch_bot():
    log("=== [Scratch Bot Process] Starting Up ===")
    try:
        session = sa.login(SCRATCH_USER, SCRATCH_PASS)
        cloud = session.connect_cloud(PROJECT_ID)
        events = cloud.events()

        @events.event
        def on_set(activity):
            if activity.var == "AI_PROMPT":
                encoded_prompt = activity.value
                if not encoded_prompt or encoded_prompt == "0":
                    return

                log(f"[Scratch Bot] New encoded prompt received: {encoded_prompt}")
                
                try:
                    decoded_prompt = Encoding.decode(encoded_prompt)
                    log(f"[Scratch Bot] Decoded Prompt: {decoded_prompt}")

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

                    encoded_reply = Encoding.encode(ai_reply)
                    cloud.set_var("AI_RESPONSE", encoded_reply)
                    log("[Scratch Bot] Successfully updated ☁ AI_RESPONSE")

                except Exception as e:
                    log(f"[Scratch Bot] Processing Error: {e}")
                    try:
                        cloud.set_var("AI_RESPONSE", Encoding.encode("Error!"))
                    except:
                        pass

        @events.event
        def on_ready():
            log("=== [Scratch Bot] Live & Monitoring ☁ AI_PROMPT ===")

        events.start()

    except Exception as e:
        log(f"[Scratch Bot] FAILED TO START: {e}")

# --- 4. THE MAGIC: SPAWN INDEPENDENT PROCESS ON IMPORT ---
# Because Gunicorn imports main.py to get the 'app' object, this block runs
# once when Gunicorn loads. This safely spins up the bot in a totally separate OS process.
if os.environ.get("RENDERS_BOT_SPAWNED") != "true":
    os.environ["RENDERS_BOT_SPAWNED"] = "true"
    # multiprocessing is much safer than threading inside WSGI servers like Gunicorn
    bot_process = multiprocessing.Process(target=run_scratch_bot)
    bot_process.daemon = True
    bot_process.start()
    log("=== [Main Web] Spawned Scratch Bot Process successfully ===")

# Local execution fallbacks
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
