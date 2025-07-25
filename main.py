import os
import uvicorn
import google.generativeai as genai
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from statemachine import TherapistStateMachine
from fastapi import HTTPException
load_dotenv()
app = FastAPI()

class StartRequest(BaseModel):
    user_id: str

class ChatRequest(BaseModel):
    user_id: str
    message: str

sessions = {}

try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    print("GOOGLE_API_KEY")
    exit()


YAML_PATH = "statemachine.yaml"
DIRECTOR_MODEL = "gemini-2.5-flash" 
GENERATOR_MODEL = "gemini-2.5-flash-lite-preview-06-17" 
DB_PATH=r'db/'

@app.post("/start")
async def start_session_endpoint(request: StartRequest):
    user_id = request.user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID is required.")

    user_db_file = os.path.join(DB_PATH, f"{user_id}.json")
    if os.path.exists(user_db_file):
        yaml_path = "statemachine2.yaml"
        print(f"Returning user '{user_id}'. Loading returning session state machine.")
    else:
        yaml_path = "statemachine.yaml"
        print(f"New user '{user_id}'. Loading first session state machine.")
    print(f"Creating new session for user: {user_id}")
    machine = TherapistStateMachine(
        yaml_path=yaml_path,
        director_model_name=DIRECTOR_MODEL,
        generator_model_name=GENERATOR_MODEL,
    )
    initial_message = machine.get_initial_message(user_id)
    

    initial_history = [{'role': 'model', 'parts': [initial_message]}]
    director_session = machine.director_model.start_chat(history=initial_history.copy())
    generator_session = machine.generator_model.start_chat(history=initial_history.copy())
    
    sessions[user_id] = {
        "machine": machine,
        "director_session": director_session,
        "generator_session": generator_session
    }

    return {"user_id": user_id, "initial_message": initial_message}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    user_id = request.user_id
    user_input = request.message

    if user_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found. Please refresh the page to start a new session.")
    
    session_data = sessions[user_id]
    machine = session_data["machine"]
    director_session = session_data["director_session"]
    generator_session = session_data["generator_session"]

    bot_response, is_session_over = await machine.step(
        director_session, 
        generator_session, 
        user_input
    )
    
    if is_session_over:
        del sessions[user_id]

    return {"response": bot_response, "is_session_over": is_session_over}


app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=1000)