"""
Backend Server لتطبيق تفوق التعليمي
Tafawuq Educational App Backend Server
"""

from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import os
import logging
import uuid
import traceback
import certifi

# استيراد النماذج والمصادقة
from models import *
from auth import (
    get_password_hash,
    verify_password,
    create_user_token,
    get_current_user_id
)

# إعداد البيئة
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# إعداد MongoDB
try:
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(
        mongo_url,
        tlsCAFile=certifi.where(),
        tlsAllowInvalidCertificates=True
    )
    db = client[os.environ.get('DB_NAME', 'tafawuq_db')]
except Exception as e:
    raise RuntimeError(f"Failed to connect to MongoDB: {e}")

app = FastAPI(title="Tafawuq API", version="1.0.0")
@app.get("/debug/routes")
async def get_routes():
    # هذا سيعرض لنا كل الروابط التي يعترف بها السيرفر حالياً
    return {"routes": [route.path for route in app.routes]}
api_router = APIRouter(prefix="/api")

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# إعداد CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== Helper Functions =====
def generate_id() -> str:
    return str(uuid.uuid4())

async def get_user_by_email(email: str) -> Optional[UserInDB]:
    user_data = await db.users.find_one({"email": email})
    return UserInDB(**user_data) if user_data else None

# ===== Authentication Routes =====

@api_router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """تسجيل مستخدم جديد مع إنشاء سجل تقدم"""
    try:
        existing_user = await get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="هذا البريد الإلكتروني مسجل مسبقاً")

        user_id = generate_id()
        now = datetime.utcnow()
        hashed_password = get_password_hash(user_data.password)

        user_in_db = UserInDB(
            id=user_id,
            email=user_data.email,
            full_name=user_data.full_name,
            role=user_data.role or UserRole.STUDENT,
            grade=user_data.grade,
            subscription_type=user_data.subscription_type or SubscriptionType.FREE,
            profile_image=user_data.profile_image,
            hashed_password=hashed_password,
            created_at=now,
            updated_at=now
        )

        await db.users.insert_one(user_in_db.dict())

        # إنشاء سجل التقدم للطالب
        if user_in_db.role == UserRole.STUDENT:
            progress = UserProgressInDB(
                id=generate_id(),
                user_id=user_id,
                completed_lesson_ids=[],
                bookmarked_lesson_ids=[]
            )
            await db.user_progress.insert_one(progress.dict())

        # الرد للفرونت اند برسالة نجاح
        return {"message": "تم التسجيل بنجاح، يمكنك الآن تسجيل الدخول"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Register error: {e}")
        raise HTTPException(status_code=500, detail="حدث خطأ أثناء التسجيل")

@api_router.post("/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    user = await get_user_by_email(credentials.email)
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="البريد أو كلمة المرور غير صحيحة")

    access_token = create_user_token(user.id, user.email)
    return Token(access_token=access_token, user=UserResponse(**user.dict()))
    # ===== Admin Routes =====

@api_router.get("/admin/students")
async def get_all_students():
    """جلب قائمة جميع الطلاب (للمدير)"""
    try:
        students = await db.users.find({"role": "student"}).to_list(length=100)
        # تحويل المعرفات لـ string لتجنب مشاكل JSON
        for student in students:
            student["_id"] = str(student["_id"])
        return students
    except Exception as e:
        logger.error(f"Error fetching students: {e}")
        raise HTTPException(status_code=500, detail="خطأ في جلب بيانات الطلاب")

@api_router.get("/subjects")
async def get_subjects():
    """جلب قائمة المواد التعليمية"""
    try:
        subjects = await db.subjects.find().to_list(length=100)
        for subject in subjects:
            subject["_id"] = str(subject["_id"])
        return subjects
    except Exception as e:
        logger.error(f"Error fetching subjects: {e}")
        raise HTTPException(status_code=500, detail="خطأ في جلب المواد")

app.include_router(api_router)