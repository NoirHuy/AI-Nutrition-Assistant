from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from app.services.ai_chat import analyze_image_diet, generate_response

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str
    disease: str

class VisionRequest(BaseModel):
    image_base64: str
    disease: str

@app.get("/")
def read_root():
    return {"status": "AI Nutrition System Ready"}

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    response = generate_response(request.question, request.disease)
    return {"bot_response": response}

@app.post("/api/vision")
async def vision_endpoint(request: VisionRequest):
    response = analyze_image_diet(request.image_base64, request.disease)
    return {"bot_response": response}