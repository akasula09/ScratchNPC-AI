import os
import threading
from flask import Flask
import scratchattach as sa
from scratchattach import Encoding
from groq import Groq

# --- 1. SET UP FLASK (To keep Render happy) ---
app = Flask('')

@app.route('/')
def home():
    return "NPC Brain is active and running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 2. SET UP CREDENTIALS ---
GROQ_API_KEY = "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"
SCRATCH_USER = "Pyroshape"
SCRATCH_PASS = "Grandmaster@17"
PROJECT_ID = "1362701122"

groq_client = Groq(api_key=GROQ_API_KEY)

# --- 3. THE CLOUD VARIABLE LISTENER ---
def run_scratch_bot():
    try:
        session = sa.login(SCRATCH_USER, SCRATCH_PASS)
        cloud = session.connect_cloud(PROJECT_ID)
        events = cloud.events()

        @events.event
        def on_set(activity):
            # Only trigger if the variable updated is 'AI_PROMPT'
            # Note: activity.var comes without the "☁" cloud emoji prefix
            if activity.var == "AI_PROMPT":
                encoded_prompt = activity.value
                
                # If the variable is set to 0, empty, or a reset code, ignore it
                if not encoded_prompt or encoded_prompt == "0":
                    return

                print(f"New encoded prompt received: {encoded_prompt}")
                
                try:
                    # 1. Decode the numeric string back into normal text
                    decoded_prompt = Encoding.decode(encoded_prompt)
                    print(f"Decoded Prompt: {decoded_prompt}")

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
                    print(f"Groq AI Reply: {ai_reply}")

                    # 3. Encode the reply back into numbers
                    encoded_reply = Encoding.encode(ai_reply)
                    
                    # 4. Set the cloud variable 'AI_RESPONSE' 
                    # Note: Set variable names without the ☁ symbol in scratchattach
                    cloud.set_var("AI_RESPONSE", encoded_reply)
                    print("Successfully updated ☁ AI_RESPONSE")

                except Exception as e:
                    print(f"Processing Error: {e}")
                    # Write an encoded error message so the game doesn't hang
                    cloud.set_var("AI_RESPONSE", Encoding.encode("Error!"))

        @events.event
        def on_ready():
            print("Scratch Event Listener is live! Monitoring ☁ AI_PROMPT...")

        events.start()

    except Exception as e:
        print(f"Failed to start Scratch bot: {e}")

# --- 4. START BOTH THREADS ---
if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_scratch_bot)
    bot_thread.daemon = True
    bot_thread.start()

    run_web_server()
