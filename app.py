from flask import Flask, render_template, request, jsonify
import time
from openai import OpenAI
import logging
import datetime
import re

# app will run at: http://127.0.0.1:5000/

# set up logging in the assistant.log file
log = logging.getLogger("assistant")
 
logging.basicConfig(filename = "assistant.log", level = logging.INFO)

from openai import OpenAI

client = OpenAI()

app = Flask(__name__)

# Initialize the Assistant and Thread globally so all functions have access to the assistant_id and thread_id
assistant_id = ""
thread_id = ""

# The array that will hold the chat history as the user and the assistant interact
chat_history = [
    {"role": "system", 
     "content": "Hey there! How can I assist you with your learning today?"},
]

# Start by getting the assistant_id and thread_id and returning them
# these are passed to the JS
@app.route("/get_ids", methods=["GET"])
def get_ids():
    return jsonify(assistant_id=assistant_id, thread_id=thread_id)

# If there is a message thread, send it to the the JavaScript using msg.role to render it to the UI.
# If there isn't a thread, return an error
@app.route("/get_messages", methods=["GET"])
def get_messages():
    if thread_id != "":
        thread_messages = client.beta.threads.messages.list(thread_id, order="asc")
        messages = [
            {
                "role": msg.role,
                "content": msg.content[0].text.value,
            }
            for msg in thread_messages.data
        ]
 
        return jsonify(success=True, messages=messages)
    else:
        return jsonify(success=False, message="No thread ID")

# Create the assistant
# Add the ID to the global assistant_id variable
# Use your assitant_id to retrieve your a assistant from the openai playground
def create_assistant():
    global assistant_id
    my_assistant = client.beta.assistants.retrieve(assistant_id = "asst_9SxN5GRAoLRY67C2XnFXRWhI")
    assistant_id = my_assistant.id
    return my_assistant

# Create a thread if there isn't one
def create_thread():
    global thread_id
    if thread_id == "":
        thread = client.beta.threads.create()
        thread_id = thread.id
    else:
        thread = client.beta.threads.retrieve(thread_id)
        thread_id = thread.id
    return thread

# Function to add to the log in the assistant.log file
def log_run(run_status):
    if run_status in ["cancelled", "failed", "expired"]:
        log.error(str(datetime.datetime.now()) + " Run " + run_status + "\n")

# Render the HTML template and pass in the chat_history array
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", chat_history=chat_history)

# POST route for the chat. 
# Adds the chat to the chat_history array 
# Sends it to the assistant playground on openai
@app.route("/chat", methods=["POST"])
# message user adds passed in
def chat():
    user_input = request.json["message"]
    moderation_result = client.moderations.create(
        input = user_input
    )
    while moderation_result.results[0].flagged == True:
        moderation_result = client.moderations.create(
        input = user_input
        )
 
        chat_history.append({"role": "assistant", "content": user_input})
        return jsonify(success=True, message="Assistant: Sorry, your message violated our community guidelines. Please try another prompt.")
    
    chat_history.append({"role": "user", "content": user_input})
    
    # Send the message to the assistant
    # Create dictionary of message params
    message_params = {"thread_id": thread_id, "role": "user", "content": user_input}
    # Pass message parameters to the method that creates the thread
    # The ** is a Python shortcut that allows you to pass multiple arguements within a dictionary, list, or tuple to a function
    thread_message = client.beta.threads.messages.create(**message_params)
    run = client.beta.threads.runs.create(
        thread_id = thread_id,
        assistant_id = assistant_id
    )
    # Display "..." to the user while thinking
    while run.status != "completed":
        time.sleep(0.5)
        run = client.beta.threads.runs.retrieve(thread_id = thread_id, run_id = run.id)
    # Add message to chat history
    thread_messages = client.beta.threads.messages.list(thread_id)
    message = thread_messages.data[0].content[0].text.value
    if run.status in ["cancelled", "failed", "expired"]:
        message = "An error has occurred, please try again."
    chat_history.append({"role": "assistant", "content": message})
    log_run(run.status)
    return jsonify(success=True, message=message)   

# Reset the chat
@app.route("/reset", methods=["POST"])
def reset_chat():
    global chat_history
    chat_history = [{"role": "system", "content": "Hey there! How can I assist you with your learning today?"}]
    global thread_id
    thread_id = ""
    create_thread()
    return jsonify(success=True)


# Create the assistants and thread when we first load the flask server
@app.before_request
def initialize():
    app.before_request_funcs[None].remove(initialize)
    create_assistant()
    create_thread()
    
    
# Run the flask server
if __name__ == "__main__":
    app.run()
