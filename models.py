"""
نماذج قاعدة البيانات لتطبيق تفوق التعليمي
Database Models for Tafawuq Educational App
"""

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum

# ===== Enums =====

class UserRole(str, Enum):
    """دور المستخدم"""
    STUDENT = "student"
    ADMIN = "admin"

class Grade(str, Enum):
    """الصف الدراسي"""
    GRADE_9 = "grade_9"  # الصف التاسع
    GRADE_12 = "grade_12"  # الثالث الثانوي

class QuestionType(str, Enum):
    """نوع السؤال"""
    MULTIPLE_CHOICE = "multiple_choice"  # اختيار من متعدد
    TRUE_FALSE = "true_false"  # صح وخطأ
    FILL_BLANK = "fill_blank"  # أكمل الفراغ

class SubscriptionType(str, Enum):
    """نوع الاشتراك"""
    FREE = "free"
    PREMIUM = "premium"

class ContentType(str, Enum):
    """نوع المحتوى"""
    PDF = "pdf"
    VIDEO = "video"
    TEXT = "text"

# ===== User Models =====

class UserBase(BaseModel):
    """بيانات المستخدم الأساسية"""
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.STUDENT
    grade: Optional[Grade] = None
    subscription_type: SubscriptionType = SubscriptionType.FREE
    profile_image: Optional[str] = None  # base64 or URL

class UserCreate(UserBase):
    """إنشاء مستخدم جديد"""
    password: str
    grade: Grade  # Required for students

class UserLogin(BaseModel):
    """تسجيل الدخول"""
    email: EmailStr
    password: str

class UserResponse(UserBase):
    """استجابة بيانات المستخدم"""
    id: str
    created_at: datetime
    updated_at: datetime

class UserInDB(UserBase):
    """المستخدم في قاعدة البيانات"""
    id: str
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# ===== Subject Models =====

class SubjectBase(BaseModel):
    """المادة الدراسية الأساسية"""
    name_ar: str  # اسم المادة بالعربية
    description_ar: str
    grade: Grade
    icon: Optional[str] = None  # emoji or icon name
    color: str = "#4CAF50"  # لون المادة
    order: int = 0  # ترتيب العرض

class SubjectCreate(SubjectBase):
    """إنشاء مادة جديدة"""
    pass

class SubjectResponse(SubjectBase):
    """استجابة المادة"""
    id: str
    lesson_count: int = 0
    quiz_count: int = 0
    created_at: datetime

class SubjectInDB(SubjectBase):
    """المادة في قاعدة البيانات"""
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# ===== Lesson/Content Models =====

class ContentItem(BaseModel):
    """عنصر محتوى (ملخص، مراجعة، PDF، فيديو)"""
    title_ar: str
    content_type: ContentType
    content_url: Optional[str] = None  # رابط الفيديو أو PDF
    content_text: Optional[str] = None  # محتوى نصي
    duration_minutes: Optional[int] = None
    order: int = 0

class LessonBase(BaseModel):
    """الدرس الأساسي"""
    subject_id: str
    title_ar: str
    description_ar: str
    order: int = 0
    
    # المحتويات المختلفة
    summaries: List[ContentItem] = []  # الملخصات
    reviews: List[ContentItem] = []  # المراجعات
    pdfs: List[ContentItem] = []  # ملفات PDF
    videos: List[ContentItem] = []  # الفيديوهات
    
    is_premium: bool = False  # هل الدرس للمشتركين فقط؟

class LessonCreate(LessonBase):
    """إنشاء درس جديد"""
    pass

class LessonResponse(LessonBase):
    """استجابة الدرس"""
    id: str
    created_at: datetime

class LessonInDB(LessonBase):
    """الدرس في قاعدة البيانات"""
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# ===== Question Models =====

class QuestionChoice(BaseModel):
    """خيار للسؤال"""
    text_ar: str
    is_correct: bool = False

class QuestionBase(BaseModel):
    """السؤال الأساسي"""
    subject_id: str
    lesson_id: Optional[str] = None
    question_text_ar: str
    question_type: QuestionType
    
    # للاختيار من متعدد
    choices: List[QuestionChoice] = []
    
    # للصح والخطأ
    correct_answer_boolean: Optional[bool] = None
    
    # لإكمال الفراغ
    correct_answer_text: Optional[str] = None
    
    # شرح الإجابة
    explanation_ar: str
    points: int = 1
    difficulty: Literal["easy", "medium", "hard"] = "medium"

class QuestionCreate(QuestionBase):
    """إنشاء سؤال جديد"""
    pass

class QuestionResponse(QuestionBase):
    """استجابة السؤال"""
    id: str
    created_at: datetime

class QuestionInDB(QuestionBase):
    """السؤال في قاعدة البيانات"""
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ===== Quiz Models =====

class QuizBase(BaseModel):
    """الاختبار الأساسي"""
    subject_id: str
    title_ar: str
    description_ar: str
    duration_minutes: int = 30
    passing_score: int = 60  # النسبة المئوية للنجاح
    question_ids: List[str] = []
    is_premium: bool = False

class QuizCreate(QuizBase):
    """إنشاء اختبار جديد"""
    pass

class QuizResponse(QuizBase):
    """استجابة الاختبار"""
    id: str
    question_count: int
    created_at: datetime

class QuizInDB(QuizBase):
    """الاختبار في قاعدة البيانات"""
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# ===== Quiz Attempt Models =====

class AnswerSubmission(BaseModel):
    """إجابة السؤال"""
    question_id: str
    # الإجابة حسب نوع السؤال
    selected_choice_index: Optional[int] = None  # للاختيار من متعدد
    boolean_answer: Optional[bool] = None  # للصح والخطأ
    text_answer: Optional[str] = None  # لإكمال الفراغ

class QuizSubmission(BaseModel):
    """تسليم الاختبار"""
    quiz_id: str
    answers: List[AnswerSubmission]
    time_taken_minutes: int

class QuestionResult(BaseModel):
    """نتيجة السؤال"""
    question_id: str
    question_text_ar: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    points_earned: int
    explanation_ar: str

class QuizResult(BaseModel):
    """نتيجة الاختبار"""
    quiz_id: str
    quiz_title_ar: str
    total_questions: int
    correct_answers: int
    wrong_answers: int
    score_percentage: float
    total_points: int
    earned_points: int
    passed: bool
    time_taken_minutes: int
    question_results: List[QuestionResult]

class QuizAttemptBase(BaseModel):
    """محاولة الاختبار"""
    user_id: str
    quiz_id: str
    subject_id: str
    answers: List[AnswerSubmission]
    score_percentage: float
    total_questions: int
    correct_answers: int
    passed: bool
    time_taken_minutes: int

class QuizAttemptInDB(QuizAttemptBase):
    """محاولة الاختبار في قاعدة البيانات"""
    id: str
    attempted_at: datetime = Field(default_factory=datetime.utcnow)

# ===== User Progress Models =====

class SubjectProgress(BaseModel):
    """تقدم الطالب في المادة"""
    subject_id: str
    subject_name_ar: str
    total_quizzes: int = 0
    completed_quizzes: int = 0
    average_score: float = 0.0
    total_lessons: int = 0
    completed_lessons: int = 0

class UserStats(BaseModel):
    """إحصائيات الطالب"""
    total_quizzes_taken: int
    average_score: float
    total_study_time_minutes: int
    weak_subjects: List[str]  # أسماء المواد الضعيفة
    strong_subjects: List[str]  # أسماء المواد القوية
    subjects_progress: List[SubjectProgress]
    recent_quiz_scores: List[float]  # آخر 10 نتائج

class UserProgressInDB(BaseModel):
    """تقدم المستخدم في قاعدة البيانات"""
    id: str
    user_id: str
    completed_lesson_ids: List[str] = []
    bookmarked_lesson_ids: List[str] = []
    last_accessed_subject_id: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# ===== Token Models =====

class Token(BaseModel):
    """رمز المصادقة"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenData(BaseModel):
    """بيانات الرمز"""
    user_id: Optional[str] = None


# ===== Notification Models =====

class NotificationType(str, Enum):
    """نوع الإشعار"""
    GENERAL = "general"  # عام
    NEW_LESSON = "new_lesson"  # درس جديد
    NEW_QUIZ = "new_quiz"  # اختبار جديد
    ACHIEVEMENT = "achievement"  # إنجاز
    SUBSCRIPTION = "subscription"  # اشتراك
    REMINDER = "reminder"  # تذكير

class NotificationBase(BaseModel):
    """الإشعار الأساسي"""
    title_ar: str
    body_ar: str
    notification_type: NotificationType = NotificationType.GENERAL
    target_user_ids: List[str] = []  # فارغ = للجميع
    target_grade: Optional[Grade] = None  # محدد بصف معين
    icon: str = "🔔"
    is_read: bool = False

class NotificationCreate(BaseModel):
    """إنشاء إشعار جديد"""
    title_ar: str
    body_ar: str
    notification_type: NotificationType = NotificationType.GENERAL
    target_user_ids: List[str] = []
    target_grade: Optional[Grade] = None
    icon: str = "🔔"

class NotificationResponse(BaseModel):
    """استجابة الإشعار"""
    id: str
    title_ar: str
    body_ar: str
    notification_type: NotificationType
    icon: str
    is_read: bool
    created_at: datetime

class NotificationInDB(BaseModel):
    """الإشعار في قاعدة البيانات"""
    id: str
    title_ar: str
    body_ar: str
    notification_type: NotificationType
    target_user_ids: List[str] = []
    target_grade: Optional[Grade] = None
    icon: str = "🔔"
    read_by_user_ids: List[str] = []  # قائمة من قرأ الإشعار
    sender_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ===== Subscription Models =====

class SubscriptionPlan(str, Enum):
    """خطة الاشتراك"""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

class SubscriptionCodeBase(BaseModel):
    """كود الاشتراك الأساسي"""
    code: str
    plan: SubscriptionPlan
    duration_days: int
    description_ar: Optional[str] = None
    max_uses: int = 1  # عدد مرات الاستخدام المسموح
    is_active: bool = True

class SubscriptionCodeCreate(BaseModel):
    """إنشاء كود اشتراك"""
    plan: SubscriptionPlan
    description_ar: Optional[str] = None
    max_uses: int = 1
    quantity: int = 1  # عدد الأكواد المراد إنشاؤها

class SubscriptionCodeResponse(BaseModel):
    """استجابة كود الاشتراك"""
    id: str
    code: str
    plan: SubscriptionPlan
    duration_days: int
    description_ar: Optional[str] = None
    max_uses: int
    used_count: int = 0
    is_active: bool
    created_at: datetime
    used_by_user_ids: List[str] = []

class SubscriptionCodeInDB(BaseModel):
    """كود الاشتراك في قاعدة البيانات"""
    id: str
    code: str
    plan: SubscriptionPlan
    duration_days: int
    description_ar: Optional[str] = None
    max_uses: int = 1
    used_count: int = 0
    used_by_user_ids: List[str] = []
    is_active: bool = True
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SubscriptionActivate(BaseModel):
    """تفعيل اشتراك بكود"""
    code: str

class UserSubscriptionInDB(BaseModel):
    """اشتراك المستخدم"""
    id: str
    user_id: str
    plan: SubscriptionPlan
    code_used: str
    duration_days: int
    activated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    is_active: bool = True


# ===== Achievement Models =====

class AchievementType(str, Enum):
    """نوع الإنجاز"""
    FIRST_QUIZ = "first_quiz"  # أول اختبار
    FIRST_PASS = "first_pass"  # أول نجاح
    PERFECT_SCORE = "perfect_score"  # 100%
    STREAK_5 = "streak_5"  # 5 اختبارات ناجحة متتالية
    STREAK_10 = "streak_10"  # 10 اختبارات ناجحة متتالية
    QUIZ_MASTER = "quiz_master"  # 20 اختبار مكتمل
    HONOR_STUDENT = "honor_student"  # معدل 90%+
    EARLY_BIRD = "early_bird"  # إنهاء 5 دروس
    DEDICATED = "dedicated"  # 10 ساعات دراسة

class Achievement(BaseModel):
    """إنجاز"""
    type: AchievementType
    title_ar: str
    description_ar: str
    icon: str
    points: int = 10

class UserAchievementInDB(BaseModel):
    """إنجاز المستخدم"""
    id: str
    user_id: str
    achievement_type: AchievementType
    title_ar: str
    description_ar: str
    icon: str
    points: int
    unlocked_at: datetime = Field(default_factory=datetime.utcnow)


# ===== Leaderboard Models =====

class LeaderboardEntry(BaseModel):
    """عنصر في قائمة المتصدرين"""
    rank: int
    user_id: str
    full_name: str
    grade: Optional[Grade] = None
    total_points: int  # مجموع نقاط من الاختبارات
    total_quizzes: int
    average_score: float
    achievements_count: int
    is_current_user: bool = False


# ===== Email Verification Models =====

class EmailVerificationCode(BaseModel):
    """كود التحقق من البريد"""
    user_id: str
    code: str
    expires_at: datetime
    is_verified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class VerifyEmailRequest(BaseModel):
    """طلب التحقق من البريد"""
    code: str
