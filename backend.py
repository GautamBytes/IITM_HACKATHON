from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from uuid import uuid4
from fastapi.responses import HTMLResponse

app = FastAPI()
data_store = {}

class ChatHistory(BaseModel):
    history: list

@app.post("/save_chat/")
def save_chat(chat_history: ChatHistory):
    session_id = str(uuid4())
    data_store[session_id] = chat_history.history
    return {"url": f"http://localhost:8000/chat/{session_id}"}

@app.get("/chat/{session_id}", response_class=HTMLResponse)
def get_chat(session_id: str):
    if session_id in data_store:
        history = data_store[session_id]
        html_content = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; background-color: #1e1e1e; color: #c0c0c0; }
                .question { font-weight: bold; font-size: 1.2em; margin-top: 20px; color: #76c7c0; }
                .answer { margin-bottom: 20px; color: #f5f5f5; }
            </style>
        </head>
        <body>
        """
        for qa in history:
            html_content += f'<div class="question">Q: {qa["question"]}</div>'
            html_content += f'<div class="answer">A: {qa["answer"]}</div>'
        html_content += """
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=200)
    else:
        raise HTTPException(status_code=404, detail="Chat session not found")

if __name__ == "_main_":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


