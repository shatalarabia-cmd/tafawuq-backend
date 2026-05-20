"""
Backend Server لتطبيق تفوق التعليمي
Tafawuq Educational App Backend Server
"""

from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Optional
import os
import logging
import uuid

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
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'tafawuq_db')]

# إنشاء التطبيق
app = FastAPI(title="Tafawuq API", version="1.0.0")
api_router = APIRouter(prefix="/api")

# إعداد CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
    
    user_in_db = UserInDB(
        id=user_id,
        email=user_data.email,
        full_name=user_data.full_name,
        role=user_data.role,
        grade=user_data.grade,
        subscription_type=user_data.subscription_type,
        profile_image=user_data.profile_image,
        hashed_password=hashed_password,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    await db.users.insert_one(user_in_db.dict())
    
    # إنشاء سجل التقدم للطالب
    if user_data.role == UserRole.STUDENT:
        progress = UserProgressInDB(
            id=generate_id(),
            user_id=user_id,
            completed_lesson_ids=[],
            bookmarked_lesson_ids=[]
        )
        await db.user_progress.insert_one(progress.dict())
    
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
    
    return Token(access_token=access_token, user=user_response)


@api_router.post("/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    """تسجيل الدخول"""
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
    
    return Token(access_token=access_token, user=user_response)


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

# ===== Subject Routes =====

@api_router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(subject: SubjectCreate, user_id: str = Depends(get_current_user_id)):
    """إنشاء مادة جديدة (للمدراء فقط)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    subject_id = generate_id()
    subject_in_db = SubjectInDB(
        id=subject_id,
        **subject.dict()
    )
    
    await db.subjects.insert_one(subject_in_db.dict())
    
    return SubjectResponse(
        **subject_in_db.dict(),
        lesson_count=0,
        quiz_count=0
    )


@api_router.get("/subjects", response_model=List[SubjectResponse])
async def get_subjects(grade: Optional[Grade] = None, user_id: str = Depends(get_current_user_id)):
    """الحصول على جميع المواد (حسب الصف اختيارياً)"""
    query = {}
    if grade:
        query["grade"] = grade
    
    subjects = await db.subjects.find(query).sort("order", 1).to_list(100)
    
    result = []
    for subject in subjects:
        # حساب عدد الدروس والاختبارات
        lesson_count = await db.lessons.count_documents({"subject_id": subject["id"]})
        quiz_count = await db.quizzes.count_documents({"subject_id": subject["id"]})
        
        result.append(SubjectResponse(
            **subject,
            lesson_count=lesson_count,
            quiz_count=quiz_count
        ))
    
    return result


@api_router.get("/subjects/{subject_id}", response_model=SubjectResponse)
async def get_subject(subject_id: str, user_id: str = Depends(get_current_user_id)):
    """الحصول على مادة واحدة"""
    subject = await db.subjects.find_one({"id": subject_id})
    if not subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")
    
    lesson_count = await db.lessons.count_documents({"subject_id": subject_id})
    quiz_count = await db.quizzes.count_documents({"subject_id": subject_id})
    
    return SubjectResponse(**subject, lesson_count=lesson_count, quiz_count=quiz_count)


@api_router.put("/subjects/{subject_id}", response_model=SubjectResponse)
async def update_subject(subject_id: str, subject: SubjectCreate, user_id: str = Depends(get_current_user_id)):
    """تحديث مادة (للمدراء فقط)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    existing = await db.subjects.find_one({"id": subject_id})
    if not existing:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")
    
    update_data = subject.dict()
    update_data["updated_at"] = datetime.utcnow()
    
    await db.subjects.update_one({"id": subject_id}, {"$set": update_data})
    
    updated_subject = await db.subjects.find_one({"id": subject_id})
    lesson_count = await db.lessons.count_documents({"subject_id": subject_id})
    quiz_count = await db.quizzes.count_documents({"subject_id": subject_id})
    
    return SubjectResponse(**updated_subject, lesson_count=lesson_count, quiz_count=quiz_count)


@api_router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(subject_id: str, user_id: str = Depends(get_current_user_id)):
    """حذف مادة (للمدراء فقط)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    result = await db.subjects.delete_one({"id": subject_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")
    
    # حذف الدروس والاختبارات المرتبطة
    await db.lessons.delete_many({"subject_id": subject_id})
    await db.quizzes.delete_many({"subject_id": subject_id})
    await db.questions.delete_many({"subject_id": subject_id})

# ===== Lesson Routes =====

@api_router.post("/lessons", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
async def create_lesson(lesson: LessonCreate, user_id: str = Depends(get_current_user_id)):
    """إنشاء درس جديد (للمدراء فقط)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    lesson_id = generate_id()
    lesson_in_db = LessonInDB(id=lesson_id, **lesson.dict())
    
    await db.lessons.insert_one(lesson_in_db.dict())
    
    return LessonResponse(**lesson_in_db.dict())


@api_router.get("/lessons", response_model=List[LessonResponse])
async def get_lessons(subject_id: Optional[str] = None, user_id: str = Depends(get_current_user_id)):
    """الحصول على الدروس"""
    query = {}
    if subject_id:
        query["subject_id"] = subject_id
    
    lessons = await db.lessons.find(query).sort("order", 1).to_list(1000)
    return [LessonResponse(**lesson) for lesson in lessons]


@api_router.get("/lessons/{lesson_id}", response_model=LessonResponse)
async def get_lesson(lesson_id: str, user_id: str = Depends(get_current_user_id)):
    """الحصول على درس واحد"""
    lesson = await db.lessons.find_one({"id": lesson_id})
    if not lesson:
        raise HTTPException(status_code=404, detail="الدرس غير موجود")
    
    # التحقق من الاشتراك إذا كان الدرس مدفوعاً
    if lesson.get("is_premium", False):
        user = await get_user_by_id(user_id)
        if user.subscription_type != SubscriptionType.PREMIUM and user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="يتطلب اشتراك مميز")
    
    return LessonResponse(**lesson)


@api_router.put("/lessons/{lesson_id}", response_model=LessonResponse)
async def update_lesson(lesson_id: str, lesson: LessonCreate, user_id: str = Depends(get_current_user_id)):
    """تحديث درس (للمدراء فقط)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    existing = await db.lessons.find_one({"id": lesson_id})
    if not existing:
        raise HTTPException(status_code=404, detail="الدرس غير موجود")
    
    update_data = lesson.dict()
    update_data["updated_at"] = datetime.utcnow()
    
    await db.lessons.update_one({"id": lesson_id}, {"$set": update_data})
    
    updated = await db.lessons.find_one({"id": lesson_id})
    return LessonResponse(**updated)


@api_router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson(lesson_id: str, user_id: str = Depends(get_current_user_id)):
    """حذف درس (للمدراء فقط)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    result = await db.lessons.delete_one({"id": lesson_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الدرس غير موجود")

# ===== Question Routes =====

@api_router.post("/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def create_question(question: QuestionCreate, user_id: str = Depends(get_current_user_id)):
    """إنشاء سؤال جديد (للمدراء فقط)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    question_id = generate_id()
    question_in_db = QuestionInDB(id=question_id, **question.dict())
    
    await db.questions.insert_one(question_in_db.dict())
    
    return QuestionResponse(**question_in_db.dict())


@api_router.get("/questions", response_model=List[QuestionResponse])
async def get_questions(
    subject_id: Optional[str] = None,
    lesson_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id)
):
    """الحصول على الأسئلة"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    query = {}
    if subject_id:
        query["subject_id"] = subject_id
    if lesson_id:
        query["lesson_id"] = lesson_id
    
    questions = await db.questions.find(query).to_list(1000)
    return [QuestionResponse(**q) for q in questions]


@api_router.get("/questions/{question_id}", response_model=QuestionResponse)
async def get_question(question_id: str, user_id: str = Depends(get_current_user_id)):
    """الحصول على سؤال واحد"""
    question = await db.questions.find_one({"id": question_id})
    if not question:
        raise HTTPException(status_code=404, detail="السؤال غير موجود")
    
    return QuestionResponse(**question)


@api_router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(question_id: str, user_id: str = Depends(get_current_user_id)):
    """حذف سؤال (للمدراء فقط)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    result = await db.questions.delete_one({"id": question_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="السؤال غير موجود")

# ===== Quiz Routes =====

@api_router.post("/quizzes", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
async def create_quiz(quiz: QuizCreate, user_id: str = Depends(get_current_user_id)):
    """إنشاء اختبار جديد (للمدراء فقط)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    quiz_id = generate_id()
    quiz_in_db = QuizInDB(id=quiz_id, **quiz.dict())
    
    await db.quizzes.insert_one(quiz_in_db.dict())
    
    return QuizResponse(
        **quiz_in_db.dict(),
        question_count=len(quiz.question_ids)
    )


@api_router.get("/quizzes", response_model=List[QuizResponse])
async def get_quizzes(subject_id: Optional[str] = None, user_id: str = Depends(get_current_user_id)):
    """الحصول على الاختبارات"""
    query = {}
    if subject_id:
        query["subject_id"] = subject_id
    
    quizzes = await db.quizzes.find(query).to_list(1000)
    
    result = []
    for quiz in quizzes:
        result.append(QuizResponse(
            **quiz,
            question_count=len(quiz.get("question_ids", []))
        ))
    
    return result


@api_router.get("/quizzes/{quiz_id}", response_model=QuizResponse)
async def get_quiz(quiz_id: str, user_id: str = Depends(get_current_user_id)):
    """الحصول على اختبار واحد"""
    quiz = await db.quizzes.find_one({"id": quiz_id})
    if not quiz:
        raise HTTPException(status_code=404, detail="الاختبار غير موجود")
    
    return QuizResponse(
        **quiz,
        question_count=len(quiz.get("question_ids", []))
    )


@api_router.get("/quizzes/{quiz_id}/questions", response_model=List[QuestionResponse])
async def get_quiz_questions(quiz_id: str, user_id: str = Depends(get_current_user_id)):
    """الحصول على أسئلة الاختبار"""
    quiz = await db.quizzes.find_one({"id": quiz_id})
    if not quiz:
        raise HTTPException(status_code=404, detail="الاختبار غير موجود")
    
    # التحقق من الاشتراك
    if quiz.get("is_premium", False):
        user = await get_user_by_id(user_id)
        if user.subscription_type != SubscriptionType.PREMIUM and user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="يتطلب اشتراك مميز")
    
    question_ids = quiz.get("question_ids", [])
    questions = await db.questions.find({"id": {"$in": question_ids}}).to_list(1000)
    
    return [QuestionResponse(**q) for q in questions]


@api_router.post("/quizzes/{quiz_id}/submit", response_model=QuizResult)
async def submit_quiz(
    quiz_id: str,
    submission: QuizSubmission,
    user_id: str = Depends(get_current_user_id)
):
    """تسليم الاختبار وحساب النتيجة"""
    quiz = await db.quizzes.find_one({"id": quiz_id})
    if not quiz:
        raise HTTPException(status_code=404, detail="الاختبار غير موجود")
    
    # الحصول على الأسئلة
    question_ids = quiz.get("question_ids", [])
    questions = await db.questions.find({"id": {"$in": question_ids}}).to_list(1000)
    
    # تنظيم الأسئلة حسب المعرف
    questions_dict = {q["id"]: q for q in questions}
    
    # حساب النتائج
    total_questions = len(questions)
    correct_answers = 0
    total_points = sum(q["points"] for q in questions)
    earned_points = 0
    question_results = []
    
    for answer in submission.answers:
        question = questions_dict.get(answer.question_id)
        if not question:
            continue
        
        is_correct = False
        user_answer = ""
        correct_answer = ""
        
        # التحقق من الإجابة حسب نوع السؤال
        if question["question_type"] == QuestionType.MULTIPLE_CHOICE:
            correct_index = next(
                (i for i, choice in enumerate(question["choices"]) if choice["is_correct"]),
                None
            )
            is_correct = answer.selected_choice_index == correct_index
            user_answer = question["choices"][answer.selected_choice_index]["text_ar"] if answer.selected_choice_index is not None else ""
            correct_answer = question["choices"][correct_index]["text_ar"] if correct_index is not None else ""
        
        elif question["question_type"] == QuestionType.TRUE_FALSE:
            is_correct = answer.boolean_answer == question["correct_answer_boolean"]
            user_answer = "صح" if answer.boolean_answer else "خطأ"
            correct_answer = "صح" if question["correct_answer_boolean"] else "خطأ"
        
        elif question["question_type"] == QuestionType.FILL_BLANK:
            is_correct = answer.text_answer and answer.text_answer.strip().lower() == question["correct_answer_text"].strip().lower()
            user_answer = answer.text_answer or ""
            correct_answer = question["correct_answer_text"]
        
        if is_correct:
            correct_answers += 1
            earned_points += question["points"]
        
        question_results.append(QuestionResult(
            question_id=question["id"],
            question_text_ar=question["question_text_ar"],
            user_answer=user_answer,
            correct_answer=correct_answer,
            is_correct=is_correct,
            points_earned=question["points"] if is_correct else 0,
            explanation_ar=question["explanation_ar"]
        ))
    
    # حساب النسبة المئوية
    score_percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0
    passed = score_percentage >= quiz.get("passing_score", 60)
    
    # حفظ محاولة الاختبار
    attempt = QuizAttemptInDB(
        id=generate_id(),
        user_id=user_id,
        quiz_id=quiz_id,
        subject_id=quiz["subject_id"],
        answers=submission.answers,
        score_percentage=score_percentage,
        total_questions=total_questions,
        correct_answers=correct_answers,
        passed=passed,
        time_taken_minutes=submission.time_taken_minutes
    )
    
    await db.quiz_attempts.insert_one(attempt.dict())
    
    return QuizResult(
        quiz_id=quiz_id,
        quiz_title_ar=quiz["title_ar"],
        total_questions=total_questions,
        correct_answers=correct_answers,
        wrong_answers=total_questions - correct_answers,
        score_percentage=score_percentage,
        total_points=total_points,
        earned_points=earned_points,
        passed=passed,
        time_taken_minutes=submission.time_taken_minutes,
        question_results=question_results
    )


@api_router.delete("/quizzes/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(quiz_id: str, user_id: str = Depends(get_current_user_id)):
    """حذف اختبار (للمدراء فقط)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    result = await db.quizzes.delete_one({"id": quiz_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الاختبار غير موجود")

# ===== User Progress & Statistics Routes =====

@api_router.get("/stats/me", response_model=UserStats)
async def get_my_stats(user_id: str = Depends(get_current_user_id)):
    """الحصول على إحصائيات الطالب"""
    user = await get_user_by_id(user_id)
    if not user or user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="للطلاب فقط")
    
    # الحصول على جميع محاولات الاختبار
    attempts = await db.quiz_attempts.find({"user_id": user_id}).sort("attempted_at", -1).to_list(1000)
    
    # حساب الإحصائيات
    total_quizzes = len(attempts)
    average_score = sum(a["score_percentage"] for a in attempts) / total_quizzes if total_quizzes > 0 else 0
    total_study_time = sum(a["time_taken_minutes"] for a in attempts)
    recent_scores = [a["score_percentage"] for a in attempts[:10]]
    
    # حساب التقدم في كل مادة
    subjects = await db.subjects.find({"grade": user.grade}).to_list(100)
    subjects_progress = []
    
    weak_subjects = []
    strong_subjects = []
    
    for subject in subjects:
        subject_attempts = [a for a in attempts if a["subject_id"] == subject["id"]]
        total_subject_quizzes = await db.quizzes.count_documents({"subject_id": subject["id"]})
        completed_quizzes = len(subject_attempts)
        avg_score = sum(a["score_percentage"] for a in subject_attempts) / completed_quizzes if completed_quizzes > 0 else 0
        
        total_lessons = await db.lessons.count_documents({"subject_id": subject["id"]})
        progress_doc = await db.user_progress.find_one({"user_id": user_id})
        completed_lesson_ids = progress_doc.get("completed_lesson_ids", []) if progress_doc else []
        completed_lessons = len([lid for lid in completed_lesson_ids if await db.lessons.find_one({"id": lid, "subject_id": subject["id"]})])
        
        subjects_progress.append(SubjectProgress(
            subject_id=subject["id"],
            subject_name_ar=subject["name_ar"],
            total_quizzes=total_subject_quizzes,
            completed_quizzes=completed_quizzes,
            average_score=avg_score,
            total_lessons=total_lessons,
            completed_lessons=completed_lessons
        ))
        
        if completed_quizzes > 0:
            if avg_score < 60:
                weak_subjects.append(subject["name_ar"])
            elif avg_score >= 80:
                strong_subjects.append(subject["name_ar"])
    
    return UserStats(
        total_quizzes_taken=total_quizzes,
        average_score=average_score,
        total_study_time_minutes=total_study_time,
        weak_subjects=weak_subjects,
        strong_subjects=strong_subjects,
        subjects_progress=subjects_progress,
        recent_quiz_scores=recent_scores
    )


@api_router.post("/progress/complete-lesson/{lesson_id}")
async def mark_lesson_complete(lesson_id: str, user_id: str = Depends(get_current_user_id)):
    """تعليم الدرس كمكتمل"""
    lesson = await db.lessons.find_one({"id": lesson_id})
    if not lesson:
        raise HTTPException(status_code=404, detail="الدرس غير موجود")
    
    progress = await db.user_progress.find_one({"user_id": user_id})
    if not progress:
        new_progress = UserProgressInDB(
            id=generate_id(),
            user_id=user_id,
            completed_lesson_ids=[lesson_id],
            bookmarked_lesson_ids=[]
        )
        await db.user_progress.insert_one(new_progress.dict())
        return {"message": "تم تعليم الدرس كمكتمل"}
    
    completed_ids = progress.get("completed_lesson_ids", [])
    if lesson_id not in completed_ids:
        completed_ids.append(lesson_id)
        await db.user_progress.update_one(
            {"user_id": user_id},
            {"$set": {"completed_lesson_ids": completed_ids, "updated_at": datetime.utcnow()}}
        )
    
    return {"message": "تم تعليم الدرس كمكتمل"}


@api_router.post("/progress/bookmark-lesson/{lesson_id}")
async def bookmark_lesson(lesson_id: str, user_id: str = Depends(get_current_user_id)):
    """إضافة الدرس للمفضلة"""
    lesson = await db.lessons.find_one({"id": lesson_id})
    if not lesson:
        raise HTTPException(status_code=404, detail="الدرس غير موجود")
    
    progress = await db.user_progress.find_one({"user_id": user_id})
    if not progress:
        new_progress = UserProgressInDB(
            id=generate_id(),
            user_id=user_id,
            completed_lesson_ids=[],
            bookmarked_lesson_ids=[lesson_id]
        )
        await db.user_progress.insert_one(new_progress.dict())
        return {"message": "تمت إضافة الدرس للمفضلة"}
    
    bookmarked_ids = progress.get("bookmarked_lesson_ids", [])
    if lesson_id not in bookmarked_ids:
        bookmarked_ids.append(lesson_id)
        await db.user_progress.update_one(
            {"user_id": user_id},
            {"$set": {"bookmarked_lesson_ids": bookmarked_ids, "updated_at": datetime.utcnow()}}
        )
    
    return {"message": "تمت إضافة الدرس للمفضلة"}


@api_router.get("/admin/dashboard")
async def get_admin_dashboard(user_id: str = Depends(get_current_user_id)):
    """لوحة تحكم المدير"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="للمدراء فقط")
    
    total_students = await db.users.count_documents({"role": UserRole.STUDENT})
    total_subjects = await db.subjects.count_documents({})
    total_lessons = await db.lessons.count_documents({})
    total_quizzes = await db.quizzes.count_documents({})
    total_questions = await db.questions.count_documents({})
    total_quiz_attempts = await db.quiz_attempts.count_documents({})
    
    # أحدث الطلاب
    recent_students = await db.users.find(
        {"role": UserRole.STUDENT}
    ).sort("created_at", -1).limit(10).to_list(10)
    
    return {
        "total_students": total_students,
        "total_subjects": total_subjects,
        "total_lessons": total_lessons,
        "total_quizzes": total_quizzes,
        "total_questions": total_questions,
        "total_quiz_attempts": total_quiz_attempts,
        "recent_students": [
            {
                "id": s["id"],
                "full_name": s["full_name"],
                "email": s["email"],
                "grade": s["grade"],
                "created_at": s["created_at"]
            }
            for s in recent_students
        ]
    }


# ===== Admin: Student Management =====

@api_router.get("/admin/students")
async def get_all_students(
    grade: Optional[Grade] = None,
    search: Optional[str] = None,
    user_id: str = Depends(get_current_user_id)
):
    """الحصول على جميع الطلاب"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="للمدراء فقط")
    
    query = {"role": UserRole.STUDENT}
    if grade:
        query["grade"] = grade
    if search:
        query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    
    students = await db.users.find(query).sort("created_at", -1).to_list(1000)
    
    result = []
    for student in students:
        # حساب عدد محاولات الاختبار للطالب
        quiz_attempts_count = await db.quiz_attempts.count_documents({"user_id": student["id"]})
        
        # حساب المعدل
        attempts = await db.quiz_attempts.find({"user_id": student["id"]}).to_list(1000)
        avg_score = sum(a["score_percentage"] for a in attempts) / len(attempts) if attempts else 0
        
        result.append({
            "id": student["id"],
            "full_name": student["full_name"],
            "email": student["email"],
            "grade": student.get("grade"),
            "subscription_type": student.get("subscription_type", "free"),
            "profile_image": student.get("profile_image"),
            "created_at": student["created_at"],
            "updated_at": student["updated_at"],
            "quiz_attempts_count": quiz_attempts_count,
            "average_score": round(avg_score, 1),
        })
    
    return result


@api_router.get("/admin/students/{student_id}")
async def get_student_details(student_id: str, user_id: str = Depends(get_current_user_id)):
    """الحصول على تفاصيل طالب محدد"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="للمدراء فقط")
    
    student = await db.users.find_one({"id": student_id, "role": UserRole.STUDENT})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    # محاولات الاختبارات
    attempts = await db.quiz_attempts.find(
        {"user_id": student_id}
    ).sort("attempted_at", -1).to_list(100)
    
    # حساب الإحصائيات
    total_attempts = len(attempts)
    avg_score = sum(a["score_percentage"] for a in attempts) / total_attempts if total_attempts else 0
    passed_count = sum(1 for a in attempts if a["passed"])
    total_time = sum(a["time_taken_minutes"] for a in attempts)
    
    # الحصول على معلومات الاختبارات
    quiz_attempts_details = []
    for attempt in attempts[:20]:  # آخر 20 محاولة
        quiz = await db.quizzes.find_one({"id": attempt["quiz_id"]})
        subject = await db.subjects.find_one({"id": attempt["subject_id"]}) if attempt.get("subject_id") else None
        quiz_attempts_details.append({
            "id": attempt["id"],
            "quiz_title": quiz["title_ar"] if quiz else "محذوف",
            "subject_name": subject["name_ar"] if subject else "محذوف",
            "score_percentage": attempt["score_percentage"],
            "correct_answers": attempt["correct_answers"],
            "total_questions": attempt["total_questions"],
            "passed": attempt["passed"],
            "time_taken_minutes": attempt["time_taken_minutes"],
            "attempted_at": attempt["attempted_at"],
        })
    
    # تقدم المواد
    subjects = await db.subjects.find({"grade": student.get("grade")}).to_list(100)
    subjects_progress = []
    weak_subjects = []
    strong_subjects = []
    
    for subject in subjects:
        subject_attempts = [a for a in attempts if a.get("subject_id") == subject["id"]]
        completed = len(subject_attempts)
        subject_avg = sum(a["score_percentage"] for a in subject_attempts) / completed if completed else 0
        total_subject_quizzes = await db.quizzes.count_documents({"subject_id": subject["id"]})
        
        subjects_progress.append({
            "subject_id": subject["id"],
            "subject_name_ar": subject["name_ar"],
            "subject_icon": subject.get("icon"),
            "subject_color": subject.get("color"),
            "total_quizzes": total_subject_quizzes,
            "completed_quizzes": completed,
            "average_score": round(subject_avg, 1),
        })
        
        if completed > 0:
            if subject_avg < 60:
                weak_subjects.append(subject["name_ar"])
            elif subject_avg >= 80:
                strong_subjects.append(subject["name_ar"])
    
    # الحصول على التقدم
    progress = await db.user_progress.find_one({"user_id": student_id})
    completed_lessons = len(progress.get("completed_lesson_ids", [])) if progress else 0
    bookmarked_lessons = len(progress.get("bookmarked_lesson_ids", [])) if progress else 0
    
    return {
        "id": student["id"],
        "full_name": student["full_name"],
        "email": student["email"],
        "grade": student.get("grade"),
        "subscription_type": student.get("subscription_type", "free"),
        "profile_image": student.get("profile_image"),
        "created_at": student["created_at"],
        "updated_at": student["updated_at"],
        "stats": {
            "total_quizzes_taken": total_attempts,
            "average_score": round(avg_score, 1),
            "passed_quizzes": passed_count,
            "failed_quizzes": total_attempts - passed_count,
            "total_study_time_minutes": total_time,
            "completed_lessons": completed_lessons,
            "bookmarked_lessons": bookmarked_lessons,
            "weak_subjects": weak_subjects,
            "strong_subjects": strong_subjects,
        },
        "subjects_progress": subjects_progress,
        "recent_attempts": quiz_attempts_details,
    }


class StudentUpdateRequest(BaseModel):
    """تحديث بيانات الطالب"""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    grade: Optional[Grade] = None
    subscription_type: Optional[SubscriptionType] = None


@api_router.put("/admin/students/{student_id}")
async def update_student(
    student_id: str,
    data: StudentUpdateRequest,
    user_id: str = Depends(get_current_user_id)
):
    """تحديث بيانات الطالب"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="للمدراء فقط")
    
    student = await db.users.find_one({"id": student_id, "role": UserRole.STUDENT})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    update_data = {}
    if data.full_name is not None:
        update_data["full_name"] = data.full_name
    if data.email is not None:
        # التحقق من عدم استخدام البريد من قبل
        existing = await db.users.find_one({"email": data.email, "id": {"$ne": student_id}})
        if existing:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم بالفعل")
        update_data["email"] = data.email
    if data.grade is not None:
        update_data["grade"] = data.grade
    if data.subscription_type is not None:
        update_data["subscription_type"] = data.subscription_type
    
    if not update_data:
        raise HTTPException(status_code=400, detail="لا يوجد بيانات للتحديث")
    
    update_data["updated_at"] = datetime.utcnow()
    
    await db.users.update_one({"id": student_id}, {"$set": update_data})
    
    return {"message": "تم تحديث بيانات الطالب بنجاح"}


class PasswordResetRequest(BaseModel):
    """إعادة تعيين كلمة المرور"""
    new_password: str


@api_router.post("/admin/students/{student_id}/reset-password")
async def reset_student_password(
    student_id: str,
    data: PasswordResetRequest,
    user_id: str = Depends(get_current_user_id)
):
    """إعادة تعيين كلمة مرور الطالب"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="للمدراء فقط")
    
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تكون 6 أحرف على الأقل")
    
    student = await db.users.find_one({"id": student_id, "role": UserRole.STUDENT})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    hashed = get_password_hash(data.new_password)
    await db.users.update_one(
        {"id": student_id},
        {"$set": {"hashed_password": hashed, "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "تم إعادة تعيين كلمة المرور بنجاح"}


@api_router.delete("/admin/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(student_id: str, user_id: str = Depends(get_current_user_id)):
    """حذف طالب"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="للمدراء فقط")
    
    student = await db.users.find_one({"id": student_id, "role": UserRole.STUDENT})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    # حذف الطالب وكل بياناته
    await db.users.delete_one({"id": student_id})
    await db.user_progress.delete_many({"user_id": student_id})
    await db.quiz_attempts.delete_many({"user_id": student_id})


# ============================
# ===== Notifications =====
# ============================

@api_router.post("/notifications", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification: NotificationCreate,
    user_id: str = Depends(get_current_user_id)
):
    """إنشاء إشعار جديد (للمدير فقط)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="للمدراء فقط")
    
    notif_id = generate_id()
    notif_in_db = NotificationInDB(
        id=notif_id,
        title_ar=notification.title_ar,
        body_ar=notification.body_ar,
        notification_type=notification.notification_type,
        target_user_ids=notification.target_user_ids,
        target_grade=notification.target_grade,
        icon=notification.icon,
        sender_id=user_id,
    )
    
    await db.notifications.insert_one(notif_in_db.dict())
    
    return NotificationResponse(
        id=notif_id,
        title_ar=notification.title_ar,
        body_ar=notification.body_ar,
        notification_type=notification.notification_type,
        icon=notification.icon,
        is_read=False,
        created_at=notif_in_db.created_at,
    )


@api_router.get("/notifications", response_model=List[NotificationResponse])
async def get_my_notifications(user_id: str = Depends(get_current_user_id)):
    """الحصول على إشعارات المستخدم الحالي"""
    user = await get_user_by_id(user_id)
    
    # بناء الاستعلام: للجميع، أو لصف معين، أو محدد بمعرف
    query = {
        "$or": [
            {"target_user_ids": user_id},  # محدد بمعرف
            {"$and": [
                {"target_user_ids": {"$size": 0}},
                {"$or": [
                    {"target_grade": None},
                    {"target_grade": user.grade},
                ]}
            ]},
        ]
    }
    
    notifications = await db.notifications.find(query).sort("created_at", -1).to_list(100)
    
    return [
        NotificationResponse(
            id=n["id"],
            title_ar=n["title_ar"],
            body_ar=n["body_ar"],
            notification_type=n["notification_type"],
            icon=n.get("icon", "🔔"),
            is_read=user_id in n.get("read_by_user_ids", []),
            created_at=n["created_at"],
        )
        for n in notifications
    ]


@api_router.get("/notifications/unread-count")
async def get_unread_count(user_id: str = Depends(get_current_user_id)):
    """عدد الإشعارات غير المقروءة"""
    user = await get_user_by_id(user_id)
    
    query = {
        "$or": [
            {"target_user_ids": user_id},
            {"$and": [
                {"target_user_ids": {"$size": 0}},
                {"$or": [
                    {"target_grade": None},
                    {"target_grade": user.grade},
                ]}
            ]},
        ],
        "read_by_user_ids": {"$ne": user_id},
    }
    
    count = await db.notifications.count_documents(query)
    return {"unread_count": count}


@api_router.post("/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: str, user_id: str = Depends(get_current_user_id)):
    """تعليم الإشعار كمقروء"""
    notif = await db.notifications.find_one({"id": notif_id})
    if not notif:
        raise HTTPException(status_code=404, detail="الإشعار غير موجود")
    
    read_by = notif.get("read_by_user_ids", [])
    if user_id not in read_by:
        read_by.append(user_id)
        await db.notifications.update_one(
            {"id": notif_id},
            {"$set": {"read_by_user_ids": read_by}}
        )
    
    return {"message": "تم تعليم الإشعار كمقروء"}


@api_router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(user_id: str = Depends(get_current_user_id)):
    """تعليم جميع الإشعارات كمقروءة"""
    user = await get_user_by_id(user_id)
    
    query = {
        "$or": [
            {"target_user_ids": user_id},
            {"$and": [
                {"target_user_ids": {"$size": 0}},
                {"$or": [
                    {"target_grade": None},
                    {"target_grade": user.grade},
                ]}
            ]},
        ],
    }
    
    await db.notifications.update_many(
        query,
        {"$addToSet": {"read_by_user_ids": user_id}}
    )
    
    return {"message": "تم تعليم جميع الإشعارات كمقروءة"}


@api_router.get("/admin/notifications", response_model=List[dict])
async def get_all_notifications(user_id: str = Depends(get_current_user_id)):
    """الحصول على جميع الإشعارات (للمدير)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="للمدراء فقط")
    
    notifications = await db.notifications.find().sort("created_at", -1).to_list(500)
    
    result = []
    for n in notifications:
        target_info = "للجميع"
        if n.get("target_user_ids"):
            target_info = f"{len(n['target_user_ids'])} طالب محدد"
        elif n.get("target_grade"):
            grade_label = "الصف التاسع" if n["target_grade"] == "grade_9" else "الثالث الثانوي"
            target_info = grade_label
        
        result.append({
            "id": n["id"],
            "title_ar": n["title_ar"],
            "body_ar": n["body_ar"],
            "notification_type": n["notification_type"],
            "icon": n.get("icon", "🔔"),
            "target_info": target_info,
            "read_count": len(n.get("read_by_user_ids", [])),
            "created_at": n["created_at"],
        })
    
    return result


@api_router.delete("/admin/notifications/{notif_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(notif_id: str, user_id: str = Depends(get_current_user_id)):
    """حذف إشعار (للمدير)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="للمدراء فقط")
    
    result = await db.notifications.delete_one({"id": notif_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الإشعار غير موجود")


# ============================
# ===== Subscriptions =====
# ============================

def generate_subscription_code() -> str:
    """توليد كود اشتراك فريد"""
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    return "TAF-" + "".join(random.choices(chars, k=8))


def get_plan_duration(plan: SubscriptionPlan) -> int:
    """الحصول على مدة الخطة بالأيام"""
    if plan == SubscriptionPlan.MONTHLY:
        return 30
    elif plan == SubscriptionPlan.QUARTERLY:
        return 90
    elif plan == SubscriptionPlan.YEARLY:
        return 365
    return 30


@api_router.get("/subscription/plans")
async def get_subscription_plans(user_id: str = Depends(get_current_user_id)):
    """الحصول على باقات الاشتراك المتاحة"""
    return {
        "plans": [
            {
                "id": "monthly",
                "title_ar": "الباقة الشهرية",
                "duration_days": 30,
                "price": 9.99,
                "currency": "USD",
                "features": [
                    "✅ وصول كامل لجميع الدروس",
                    "✅ جميع الاختبارات المميزة",
                    "✅ ملخصات حصرية",
                    "✅ دعم فني",
                ],
                "is_popular": False,
                "icon": "📅",
                "color": "#2196F3",
            },
            {
                "id": "quarterly",
                "title_ar": "الباقة الفصلية",
                "duration_days": 90,
                "price": 24.99,
                "currency": "USD",
                "discount": "وفّر 17%",
                "features": [
                    "✅ كل مميزات الشهرية",
                    "✅ خصم 17%",
                    "✅ دعم أولوية",
                    "✅ تقارير أداء شهرية",
                ],
                "is_popular": True,
                "icon": "🌟",
                "color": "#FF9800",
            },
            {
                "id": "yearly",
                "title_ar": "الباقة السنوية",
                "duration_days": 365,
                "price": 79.99,
                "currency": "USD",
                "discount": "وفّر 33%",
                "features": [
                    "✅ كل المميزات",
                    "✅ خصم 33%",
                    "✅ دعم VIP",
                    "✅ شهادات إنجاز",
                    "✅ جلسات استشارة",
                ],
                "is_popular": False,
                "icon": "👑",
                "color": "#9C27B0",
            },
        ]
    }


@api_router.post("/subscription/activate")
async def activate_subscription(
    data: SubscriptionActivate,
    user_id: str = Depends(get_current_user_id)
):
    """تفعيل اشتراك بكود"""
    code = data.code.strip().upper()
    
    sub_code = await db.subscription_codes.find_one({"code": code, "is_active": True})
    if not sub_code:
        raise HTTPException(status_code=404, detail="الكود غير صحيح أو غير فعّال")
    
    if sub_code["used_count"] >= sub_code["max_uses"]:
        raise HTTPException(status_code=400, detail="تم استخدام هذا الكود بحد أقصى مرات الاستخدام")
    
    if user_id in sub_code.get("used_by_user_ids", []):
        raise HTTPException(status_code=400, detail="لقد استخدمت هذا الكود من قبل")
    
    # تفعيل الاشتراك
    duration = sub_code["duration_days"]
    expires_at = datetime.utcnow() + timedelta(days=duration)
    
    subscription = UserSubscriptionInDB(
        id=generate_id(),
        user_id=user_id,
        plan=sub_code["plan"],
        code_used=code,
        duration_days=duration,
        expires_at=expires_at,
    )
    await db.user_subscriptions.insert_one(subscription.dict())
    
    # تحديث حالة المستخدم
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"subscription_type": SubscriptionType.PREMIUM, "updated_at": datetime.utcnow()}}
    )
    
    # تحديث الكود
    used_by = sub_code.get("used_by_user_ids", [])
    used_by.append(user_id)
    await db.subscription_codes.update_one(
        {"code": code},
        {"$set": {
            "used_count": sub_code["used_count"] + 1,
            "used_by_user_ids": used_by,
        }}
    )
    
    # إنشاء إشعار للمستخدم
    notif = NotificationInDB(
        id=generate_id(),
        title_ar="🎉 تم تفعيل اشتراكك",
        body_ar=f"تم تفعيل اشتراك مميز لمدة {duration} يوم! استمتع بجميع المميزات",
        notification_type=NotificationType.SUBSCRIPTION,
        target_user_ids=[user_id],
        icon="👑",
    )
    await db.notifications.insert_one(notif.dict())
    
    return {
        "message": "تم تفعيل الاشتراك بنجاح! 🎉",
        "plan": sub_code["plan"],
        "duration_days": duration,
        "expires_at": expires_at,
    }


@api_router.get("/subscription/my")
async def get_my_subscription(user_id: str = Depends(get_current_user_id)):
    """الحصول على معلومات اشتراكي"""
    subscription = await db.user_subscriptions.find_one(
        {"user_id": user_id, "is_active": True},
        sort=[("expires_at", -1)]
    )
    
    if not subscription:
        return {"is_premium": False, "subscription": None}
    
    is_expired = subscription["expires_at"] < datetime.utcnow()
    
    if is_expired:
        # تحديث المستخدم إلى مجاني
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"subscription_type": SubscriptionType.FREE}}
        )
        return {"is_premium": False, "subscription": None, "expired": True}
    
    return {
        "is_premium": True,
        "subscription": {
            "id": subscription["id"],
            "plan": subscription["plan"],
            "duration_days": subscription["duration_days"],
            "activated_at": subscription["activated_at"],
            "expires_at": subscription["expires_at"],
            "days_remaining": (subscription["expires_at"] - datetime.utcnow()).days,
        }
    }


# ===== Admin: Subscription Codes Management =====

@api_router.post("/admin/subscription-codes")
async def create_subscription_codes(
    data: SubscriptionCodeCreate,
    user_id: str = Depends(get_current_user_id)
):
    """إنشاء أكواد اشتراك (للمدير)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="للمدراء فقط")
    
    duration = get_plan_duration(data.plan)
    codes = []
    
    for _ in range(max(1, data.quantity)):
        code = generate_subscription_code()
        # تأكد من فريد الكود
        while await db.subscription_codes.find_one({"code": code}):
            code = generate_subscription_code()
        
        sub_code = SubscriptionCodeInDB(
            id=generate_id(),
            code=code,
            plan=data.plan,
            duration_days=duration,
            description_ar=data.description_ar,
            max_uses=data.max_uses,
            created_by=user_id,
        )
        await db.subscription_codes.insert_one(sub_code.dict())
        codes.append({
            "id": sub_code.id,
            "code": code,
            "plan": data.plan,
            "duration_days": duration,
            "max_uses": data.max_uses,
        })
    
    return {"message": f"تم إنشاء {len(codes)} كود بنجاح", "codes": codes}


@api_router.get("/admin/subscription-codes", response_model=List[SubscriptionCodeResponse])
async def get_all_subscription_codes(user_id: str = Depends(get_current_user_id)):
    """الحصول على جميع أكواد الاشتراك (للمدير)"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="للمدراء فقط")
    
    codes = await db.subscription_codes.find().sort("created_at", -1).to_list(1000)
    return [SubscriptionCodeResponse(**code) for code in codes]


@api_router.delete("/admin/subscription-codes/{code_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription_code(code_id: str, user_id: str = Depends(get_current_user_id)):
    """حذف كود اشتراك"""
    user = await get_user_by_id(user_id)
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="للمدراء فقط")
    
    result = await db.subscription_codes.delete_one({"id": code_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الكود غير موجود")


# ============================
# ===== Achievements =====
# ============================

# تعريف الإنجازات المتاحة
ACHIEVEMENTS_LIBRARY = {
    AchievementType.FIRST_QUIZ: Achievement(
        type=AchievementType.FIRST_QUIZ,
        title_ar="البداية الموفقة",
        description_ar="أكملت أول اختبار",
        icon="🎯",
        points=10,
    ),
    AchievementType.FIRST_PASS: Achievement(
        type=AchievementType.FIRST_PASS,
        title_ar="النجاح الأول",
        description_ar="نجحت في أول اختبار",
        icon="🏆",
        points=20,
    ),
    AchievementType.PERFECT_SCORE: Achievement(
        type=AchievementType.PERFECT_SCORE,
        title_ar="العلامة الكاملة",
        description_ar="حصلت على 100% في اختبار",
        icon="💯",
        points=50,
    ),
    AchievementType.STREAK_5: Achievement(
        type=AchievementType.STREAK_5,
        title_ar="سلسلة النجاح",
        description_ar="5 اختبارات ناجحة متتالية",
        icon="🔥",
        points=30,
    ),
    AchievementType.STREAK_10: Achievement(
        type=AchievementType.STREAK_10,
        title_ar="سلسلة لا تُكسر",
        description_ar="10 اختبارات ناجحة متتالية",
        icon="⚡",
        points=60,
    ),
    AchievementType.QUIZ_MASTER: Achievement(
        type=AchievementType.QUIZ_MASTER,
        title_ar="معلم الاختبارات",
        description_ar="أكملت 20 اختبار",
        icon="🎓",
        points=100,
    ),
    AchievementType.HONOR_STUDENT: Achievement(
        type=AchievementType.HONOR_STUDENT,
        title_ar="طالب متفوق",
        description_ar="معدل 90% أو أعلى في 5 اختبارات",
        icon="⭐",
        points=80,
    ),
    AchievementType.EARLY_BIRD: Achievement(
        type=AchievementType.EARLY_BIRD,
        title_ar="مجتهد مبكر",
        description_ar="أكملت 5 دروس",
        icon="📚",
        points=25,
    ),
    AchievementType.DEDICATED: Achievement(
        type=AchievementType.DEDICATED,
        title_ar="مثابر ومجتهد",
        description_ar="درست 10 ساعات أو أكثر",
        icon="💪",
        points=40,
    ),
}


async def check_and_award_achievements(user_id: str):
    """التحقق من الإنجازات ومنحها للمستخدم"""
    user = await db.users.find_one({"id": user_id})
    if not user or user.get("role") != UserRole.STUDENT:
        return []
    
    # محاولات الاختبارات
    attempts = await db.quiz_attempts.find({"user_id": user_id}).sort("attempted_at", 1).to_list(1000)
    
    # الإنجازات المفتوحة حالياً
    unlocked = await db.user_achievements.find({"user_id": user_id}).to_list(100)
    unlocked_types = {u["achievement_type"] for u in unlocked}
    new_achievements = []
    
    async def grant_achievement(ach_type: AchievementType):
        if ach_type in unlocked_types:
            return None
        ach = ACHIEVEMENTS_LIBRARY[ach_type]
        user_ach = UserAchievementInDB(
            id=generate_id(),
            user_id=user_id,
            achievement_type=ach_type,
            title_ar=ach.title_ar,
            description_ar=ach.description_ar,
            icon=ach.icon,
            points=ach.points,
        )
        await db.user_achievements.insert_one(user_ach.dict())
        
        # إنشاء إشعار
        notif = NotificationInDB(
            id=generate_id(),
            title_ar=f"🎉 إنجاز جديد: {ach.title_ar}",
            body_ar=f"{ach.description_ar} +{ach.points} نقطة",
            notification_type=NotificationType.ACHIEVEMENT,
            target_user_ids=[user_id],
            icon=ach.icon,
        )
        await db.notifications.insert_one(notif.dict())
        
        return user_ach.dict()
    
    # 1. أول اختبار
    if len(attempts) >= 1:
        new_ach = await grant_achievement(AchievementType.FIRST_QUIZ)
        if new_ach:
            new_achievements.append(new_ach)
    
    # 2. أول نجاح
    if any(a["passed"] for a in attempts):
        new_ach = await grant_achievement(AchievementType.FIRST_PASS)
        if new_ach:
            new_achievements.append(new_ach)
    
    # 3. علامة كاملة
    if any(a["score_percentage"] >= 100 for a in attempts):
        new_ach = await grant_achievement(AchievementType.PERFECT_SCORE)
        if new_ach:
            new_achievements.append(new_ach)
    
    # 4. سلسلة 5 ناجحة متتالية
    passed_streak = 0
    max_streak = 0
    for a in attempts:
        if a["passed"]:
            passed_streak += 1
            max_streak = max(max_streak, passed_streak)
        else:
            passed_streak = 0
    
    if max_streak >= 5:
        new_ach = await grant_achievement(AchievementType.STREAK_5)
        if new_ach:
            new_achievements.append(new_ach)
    
    if max_streak >= 10:
        new_ach = await grant_achievement(AchievementType.STREAK_10)
        if new_ach:
            new_achievements.append(new_ach)
    
    # 5. 20 اختبار
    if len(attempts) >= 20:
        new_ach = await grant_achievement(AchievementType.QUIZ_MASTER)
        if new_ach:
            new_achievements.append(new_ach)
    
    # 6. طالب متفوق
    if len(attempts) >= 5:
        avg = sum(a["score_percentage"] for a in attempts) / len(attempts)
        if avg >= 90:
            new_ach = await grant_achievement(AchievementType.HONOR_STUDENT)
            if new_ach:
                new_achievements.append(new_ach)
    
    # 7. مجتهد مبكر - دروس مكتملة
    progress = await db.user_progress.find_one({"user_id": user_id})
    if progress and len(progress.get("completed_lesson_ids", [])) >= 5:
        new_ach = await grant_achievement(AchievementType.EARLY_BIRD)
        if new_ach:
            new_achievements.append(new_ach)
    
    # 8. مثابر - 10 ساعات
    total_minutes = sum(a["time_taken_minutes"] for a in attempts)
    if total_minutes >= 600:  # 10 hours
        new_ach = await grant_achievement(AchievementType.DEDICATED)
        if new_ach:
            new_achievements.append(new_ach)
    
    return new_achievements


@api_router.get("/achievements")
async def get_my_achievements(user_id: str = Depends(get_current_user_id)):
    """الحصول على إنجازات المستخدم"""
    # تحديث الإنجازات
    await check_and_award_achievements(user_id)
    
    achievements = await db.user_achievements.find(
        {"user_id": user_id}
    ).sort("unlocked_at", -1).to_list(100)
    
    unlocked_types = {a["achievement_type"] for a in achievements}
    
    # جميع الإنجازات (مفتوحة + مغلقة)
    all_achievements = []
    for ach_type, ach in ACHIEVEMENTS_LIBRARY.items():
        is_unlocked = ach_type in unlocked_types
        unlocked_data = next((a for a in achievements if a["achievement_type"] == ach_type), None)
        
        all_achievements.append({
            "type": ach_type,
            "title_ar": ach.title_ar,
            "description_ar": ach.description_ar,
            "icon": ach.icon,
            "points": ach.points,
            "is_unlocked": is_unlocked,
            "unlocked_at": unlocked_data["unlocked_at"] if unlocked_data else None,
        })
    
    total_points = sum(a["points"] for a in achievements)
    
    return {
        "achievements": all_achievements,
        "total_unlocked": len(achievements),
        "total_available": len(ACHIEVEMENTS_LIBRARY),
        "total_points": total_points,
    }


# ============================
# ===== Leaderboard =====
# ============================

@api_router.get("/leaderboard")
async def get_leaderboard(
    grade: Optional[Grade] = None,
    user_id: str = Depends(get_current_user_id)
):
    """قائمة المتصدرين"""
    current_user = await get_user_by_id(user_id)
    
    # الحصول على جميع الطلاب
    query = {"role": UserRole.STUDENT}
    if grade:
        query["grade"] = grade
    elif current_user.grade:
        query["grade"] = current_user.grade  # افتراضياً نفس صف المستخدم
    
    students = await db.users.find(query).to_list(1000)
    
    # حساب نقاط كل طالب
    leaderboard_data = []
    for student in students:
        attempts = await db.quiz_attempts.find({"user_id": student["id"]}).to_list(1000)
        achievements = await db.user_achievements.find({"user_id": student["id"]}).to_list(100)
        
        total_quizzes = len(attempts)
        if total_quizzes == 0:
            continue
        
        avg_score = sum(a["score_percentage"] for a in attempts) / total_quizzes
        
        # نقاط = (مجموع النتائج / 10) + (نقاط الإنجازات)
        quiz_points = sum(a["score_percentage"] for a in attempts) / 10
        achievement_points = sum(a["points"] for a in achievements)
        total_points = int(quiz_points + achievement_points)
        
        leaderboard_data.append({
            "user_id": student["id"],
            "full_name": student["full_name"],
            "grade": student.get("grade"),
            "total_points": total_points,
            "total_quizzes": total_quizzes,
            "average_score": round(avg_score, 1),
            "achievements_count": len(achievements),
        })
    
    # ترتيب حسب النقاط
    leaderboard_data.sort(key=lambda x: x["total_points"], reverse=True)
    
    # إضافة التصنيف
    result = []
    for index, entry in enumerate(leaderboard_data):
        result.append(LeaderboardEntry(
            rank=index + 1,
            **entry,
            is_current_user=entry["user_id"] == user_id,
        ))
    
    return result[:50]  # أعلى 50

# ===== Health Check =====

@api_router.get("/")
async def root():
    """فحص حالة الخادم"""
    return {
        "message": "مرحباً بك في Tafawuq API",
        "version": "1.0.0",
        "status": "running"
    }

@api_router.get("/health")
async def health_check():
    """فحص صحة النظام"""
    try:
        # اختبار الاتصال بقاعدة البيانات
        await db.command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="خطأ في الاتصال بقاعدة البيانات")

# تضمين الموجه في التطبيق
app.include_router(api_router)

# حدث الإغلاق
@app.on_event("shutdown")
async def shutdown_db_client():
    """إغلاق الاتصال بقاعدة البيانات"""
    client.close()
    logger.info("Database connection closed")
