from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from app.database import db
from app.services.ai_chat import analyze_image_diet

class ImageRequest(BaseModel):
    image_base64: str
    disease: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect()
    yield
    db.close()

app = FastAPI(lifespan=lifespan)

# --- QUAN TRỌNG: PHẦN MỞ CỬA CHO FRONTEND ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Cho phép tất cả các nguồn truy cập
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --------------------------------------------

@app.get("/")
def read_root():
    return {"status": "Backend is running"}

@app.post("/api/vision")
async def vision_endpoint(req: ImageRequest):
    if not req.image_base64:
        raise HTTPException(status_code=400, detail="Thiếu ảnh")
    
    # Gọi AI phân tích
    answer = analyze_image_diet(req.image_base64, req.disease)
    return {"bot_response": answer}