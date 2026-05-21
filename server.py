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
from datetime import datetime, timedelta
import os
import logging
import uuid
import traceback

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
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get('DB_NAME', 'tafawuq_db')]
except KeyError:
    raise RuntimeError("MONGO_URL not found in environment variables!")
except Exception as e:
    raise RuntimeError(f"Failed to connect to MongoDB: {e}")

# إنشاء التطبيق
app = FastAPI(title="Tafawuq API", version="1.0.0")
api_router = APIRouter(prefix="/api")
# استدعاء دالة إضافة البيانات عند بدء تشغيل السيرفر تلقائياً
@app.on_event("startup")
async def startup_event():
    try:
        # الفحص إذا كان هناك مستخدمين في قاعدة البيانات
        user_count = await db.users.count_documents({})
        if user_count == 0:
            print("📭 قاعدة البيانات فارغة! جاري تشغيل seed_data تلقائياً...")
            from seed_data import seed_database
            await seed_database()
            print("✅ تم تجهيز البيانات التجريبية بنجاح!")
        else:
            print(f"📊 قاعدة البيانات تحتوي على {user_count} مستخدمين بالفعل. لن يتم التكرار.")
    except Exception as e:
        print(f"❌ خطأ أثناء فحص البيانات التجريبية: {e}")
# إعداد CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# معالج الأخطاء العام (بعد إنشاء app)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """معالج أخطاء عام لرؤية الأخطاء بوضوح"""
    error_detail = str(exc)
    traceback_str = traceback.format_exc()
    logger.error(f"ERROR: {error_detail}\n{traceback_str}")
    return JSONResponse(
        status_code=500,
        content={"detail": error_detail, "traceback": traceback_str}
    )

# إعداد السجلات
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== Helper Functions =====

def generate_id() -> str:
    """توليد معرف فريد"""
    return str(uuid.uuid4())

async def get_user_by_id(user_id: str) -> Optional[UserInDB]:
    """الحصول على المستخدم من قاعدة البيانات"""
    user_data = await db.users.find_one({"id": user_id})
    if user_data:
        return UserInDB(**user_data)
    return None

async def get_user_by_email(email: str) -> Optional[UserInDB]:
    """الحصول على المستخدم من خلال البريد الإلكتروني"""
    user_data = await db.users.find_one({"email": email})
    if user_data:
        return UserInDB(**user_data)
    return None

# ===== Authentication Routes =====

@api_router.post("/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """تسجيل مستخدم جديد"""
    try:
        logger.info(f"Register attempt: {user_data.email}")

        # التحقق من وجود المستخدم
        existing_user = await get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="البريد الإلكتروني مستخدم بالفعل"
            )

        # إنشاء المستخدم
        user_id = generate_id()
        hashed_password = get_password_hash(user_data.password)

        # استخدام القيم الافتراضية إذا لم تُرسل
        now = datetime.utcnow()
        user_in_db = UserInDB(
            id=user_id,
            email=user_data.email,
            full_name=user_data.full_name,
            role=user_data.role or UserRole.STUDENT,  # افتراضي: طالب
            grade=user_data.grade,
            subscription_type=user_data.subscription_type or SubscriptionType.FREE,  # افتراضي: مجاني
            profile_image=user_data.profile_image,
            hashed_password=hashed_password,
            created_at=now,
            updated_at=now
        )

        await db.users.insert_one(user_in_db.dict())
        logger.info(f"User created: {user_id}")

        # إنشاء سجل التقدم للطالب
        if user_in_db.role == UserRole.STUDENT:
            progress = UserProgressInDB(
                id=generate_id(),
                user_id=user_id,
                completed_lesson_ids=[],
                bookmarked_lesson_ids=[]
            )
            await db.user_progress.insert_one(progress.dict())
            logger.info(f"Progress created for student: {user_id}")

        # إنشاء الرمز
        access_token = create_user_token(user_id, user_data.email)

        user_response = UserResponse(
            id=user_in_db.id,
            email=user_in_db.email,
            full_name=user_in_db.full_name,
            role=user_in_db.role,
            grade=user_in_db.grade,
            subscription_type=user_in_db.subscription_type,
            profile_image=user_in_db.profile_image,
            created_at=user_in_db.created_at,
            updated_at=user_in_db.updated_at
        )

        logger.info(f"Register successful: {user_id}")
        return Token(access_token=access_token, user=user_response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Register error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"خطأ في التسجيل: {str(e)}")


@api_router.post("/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    """تسجيل الدخول"""
    try:
        logger.info(f"Login attempt: {credentials.email}")

        user = await get_user_by_email(credentials.email)

        if not user or not verify_password(credentials.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="البريد الإلكتروني أو كلمة المرور غير صحيحة"
            )

        access_token = create_user_token(user.id, user.email)

        user_response = UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            grade=user.grade,
            subscription_type=user.subscription_type,
            profile_image=user.profile_image,
            created_at=user.created_at,
            updated_at=user.updated_at
        )

        logger.info(f"Login successful: {user.id}")
        return Token(access_token=access_token, user=user_response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"خطأ في تسجيل الدخول: {str(e)}")


@api_router.get("/auth/me", response_model=UserResponse)
async def get_current_user(user_id: str = Depends(get_current_user_id)):
    """الحصول على بيانات المستخدم الحالي"""
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        grade=user.grade,
        subscription_type=user.subscription_type,
        profile_image=user.profile_image,
        created_at=user.created_at,
        updated_at=user.updated_at
    )
app.include_router(api_router)
