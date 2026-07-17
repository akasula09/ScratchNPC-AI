import os
import threading
import sys
from flask import Flask
import scratchattach as sa
from scratchattach import Encoding
from groq import Groq

# --- 1. SET UP FLASK ---
app = Flask('')

# Track if the background thread has started
bot_started = False

@app.route('/')
def home():
    return "NPC Brain is active and running!"

# This helper function guarantees your prints show up in Render logs instantly
def log(message):
    print(message, flush=True)

# --- 2. SET UP CREDENTIALS ---
GROQ_API_KEY = "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"
SCRATCH_USER = "Pyroshape"
# Updated with your corrected password
SCRATCH_PASS = "Grandmaster@17"
PROJECT_ID = "1362701122"

groq_client = Groq(api_key=GROQ_API_KEY)

# --- 3. THE CLOUD VARIABLE LISTENER ---
def run_scratch_bot():
    log("Starting Scratch bot connection thread...")
    try:
        session = sa.login(SCRATCH_USER, SCRATCH_PASS)
        cloud = session.connect_cloud(PROJECT_ID)
        events = cloud.events()

        @events.event
        def on_set(activity):
            # activity.var comes without the "☁" cloud emoji prefix
            if activity.var == "AI_PROMPT":
                encoded_prompt = activity.value
                
                # Ignore empty, reset, or null values
                if not encoded_prompt or encoded_prompt == "0":
                    return

                log(f"New encoded prompt received: {encoded_prompt}")
                
                try:
                    # 1. Decode the numeric string back into normal text
                    decoded_prompt = Encoding.decode(encoded_prompt)
                    log(f"Decoded Prompt: {decoded_prompt}")

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
                    log(f"Groq AI Reply: {ai_reply}")

                    # 3. Encode the reply back into numbers
                    encoded_reply = Encoding.encode(ai_reply)
                    
                    # 4. Set the cloud variable 'AI_RESPONSE' 
                    cloud.set_var("AI_RESPONSE", encoded_reply)
                    log("Successfully updated ☁ AI_RESPONSE")

                except Exception as e:
                    log(f"Processing Error: {e}")
                    cloud.set_var("AI_RESPONSE", Encoding.encode("Error!"))

        @events.event
        def on_ready():
            log("Scratch Event Listener is live! Monitoring ☁ AI_PROMPT...")

        events.start()

    except Exception as e:
        log(f"Failed to start Scratch bot: {e}")

# --- 4. START SCRATCH BOT SECURELY INSIDE GUNICORN ---
# This decorator runs right before Flask handles its very first web request.
# Render automatically hits your server with a web request as soon as it launches
# to make sure it's alive, which safely kicks off your Scratch thread.
@app.before_request
def start_bot_on_first_request():
    global bot_started
    if not bot_started:
        bot_started = True
        bot_thread = threading.Thread(target=run_scratch_bot)
        bot_thread.daemon = True
        bot_thread.start()

# For running locally on your computer
if __name__ == "__main__":
    # If running locally, start the thread and web server manually
    bot_thread = threading.Thread(target=run_scratch_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
