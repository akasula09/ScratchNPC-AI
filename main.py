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
SCRATCH_SESSION_ID = ".eJxVj8tOwzAQRf_F6zbYrvNwdiAkukCIdkHFKprYk8aktSvbVQSIf2ciddPd6J6Zo7m_7Jowejgja9n7dwxphAuyFevgmsdugZ2zxESllWzKpiLWg_dI4QCnhCuWMWUTwuQWxxziROxO0IOZ0C-WJUOfnYHsgi9uIBV7vJxu4dNtmbyBBjqSwG1pa9U0UqseuB4aY6CHAQYLmot2t09pFxU_rLeDnbfdy_j8GvX64zBPpDmFo_NrdyFTLQop60KUm0LUilgyEbIZMbI2xyt1sV_gj6HL7ow_wS-FHs8Y6bWHN5y7Typ3X22ENNJSwzmUVnIx2NrqjcBKGA2otKlVbSopBH1OOfv7B176eC0:1wkXce:FwGlqQDOV-bQNbjlX2geU5QCk2w"
PROJECT_ID = "1362701122"

groq_client = Groq(api_key=GROQ_API_KEY)

# --- 3. THE CLOUD VARIABLE LISTENER ---
def run_scratch_bot():
    log("=== [Scratch Bot Process] Starting Up ===")
    try:
        # Modern scratchattach syntax for logging in via Session Cookie:
        session = sa.login_by_id(SCRATCH_SESSION_ID, username=SCRATCH_USER)
        cloud = session.connect_cloud(PROJECT_ID)
        events = cloud.events()

        @events.event
        def on_set(activity):
            # Only trigger if the variable updated is 'AI_PROMPT'
            if activity.var == "AI_PROMPT":
                encoded_prompt = activity.value
                
                # If the variable is set to 0, empty, or a reset code, ignore it
                if not encoded_prompt or encoded_prompt == "0":
                    return

                log(f"[Scratch Bot] New encoded prompt received: {encoded_prompt}")
                
                try:
                    # 1. Decode the numeric string back into normal text
                    decoded_prompt = Encoding.decode(encoded_prompt)
                    log(f"[Scratch Bot] Decoded Prompt: {decoded_prompt}")

                    # 2. Get the response from Groq
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

                    # 3. Encode the reply back into numbers
                    encoded_reply = Encoding.encode(ai_reply)
                    
                    # 4. Set the cloud variable 'AI_RESPONSE' 
                    cloud.set_var("AI_RESPONSE", encoded_reply)
                    log("[Scratch Bot] Successfully updated ☁ AI_RESPONSE")

                except Exception as e:
                    log(f"[Scratch Bot] Processing Error: {e}")
                    try:
                        cloud.set_var("AI_RESPONSE", Encoding.encode("Error!"))
                    except Exception as cloud_err:
                        log(f"[Scratch Bot] Failed to set error on cloud: {cloud_err}")

        @events.event
        def on_ready():
            log("=== [Scratch Bot] Live & Monitoring ☁ AI_PROMPT ===")

        events.start()

    except Exception as e:
        log(f"[Scratch Bot] FAILED TO START: {e}")

# --- 4. START PROCESS SECURELY INSIDE GUNICORN ---
if os.environ.get("RENDERS_BOT_SPAWNED") != "true":
    os.environ["RENDERS_BOT_SPAWNED"] = "true"
    bot_process = multiprocessing.Process(target=run_scratch_bot)
    bot_process.daemon = True
    bot_process.start()
    log("=== [Main Web] Spawned Scratch Bot Process successfully ===")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
