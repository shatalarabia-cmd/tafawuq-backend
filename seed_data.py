"""
ملف إضافة بيانات تجريبية لتطبيق تفوق
Seed Data Script for Tafawuq App
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path
import os
import sys
import certifi

# إضافة المسار للنماذج
sys.path.append(str(Path(__file__).parent))

from models import *
from auth import get_password_hash
import uuid

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url, tlsCAFile=certifi.where()) # 👈 أضفنا التعديل هناdb = client[os.environ.get('DB_NAME', 'tafawuq_db')]


def generate_id():
    return str(uuid.uuid4())


async def seed_database():
    """إضافة البيانات التجريبية"""
    
    print("🌱 بدء إضافة البيانات التجريبية...")
    
    # === 1. حذف البيانات القديمة ===
    print("\n🗑️  حذف البيانات القديمة...")
    await db.users.delete_many({})
    await db.subjects.delete_many({})
    await db.lessons.delete_many({})
    await db.questions.delete_many({})
    await db.quizzes.delete_many({})
    await db.quiz_attempts.delete_many({})
    await db.user_progress.delete_many({})
    
    # === 2. إنشاء المستخدمين ===
    print("\n👥 إنشاء المستخدمين...")
    
    # مدير
    admin_id = generate_id()
    admin = {
        "id": admin_id,
        "email": "admin@tafawuq.com",
        "full_name": "المدير العام",
        "role": "admin",
        "grade": None,
        "subscription_type": "premium",
        "profile_image": None,
        "hashed_password": get_password_hash("admin123"),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    await db.users.insert_one(admin)
    print(f"✅ تم إنشاء المدير: {admin['email']} / admin123")
    
    # طلاب
    students_data = [
        {
            "email": "student9@tafawuq.com",
            "full_name": "أحمد محمد",
            "grade": "grade_9",
            "password": "student123"
        },
        {
            "email": "student12@tafawuq.com",
            "full_name": "فاطمة علي",
            "grade": "grade_12",
            "password": "student123"
        }
    ]
    
    student_ids = []
    for student_data in students_data:
        student_id = generate_id()
        student = {
            "id": student_id,
            "email": student_data["email"],
            "full_name": student_data["full_name"],
            "role": "student",
            "grade": student_data["grade"],
            "subscription_type": "free",
            "profile_image": None,
            "hashed_password": get_password_hash(student_data["password"]),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        await db.users.insert_one(student)
        student_ids.append(student_id)
        
        # إنشاء سجل التقدم
        progress = {
            "id": generate_id(),
            "user_id": student_id,
            "completed_lesson_ids": [],
            "bookmarked_lesson_ids": [],
            "last_accessed_subject_id": None,
            "updated_at": datetime.utcnow()
        }
        await db.user_progress.insert_one(progress)
        
        print(f"✅ تم إنشاء الطالب: {student['email']} / {student_data['password']}")
    
    # === 3. إنشاء المواد ===
    print("\n📚 إنشاء المواد الدراسية...")
    
    subjects_data = [
        # مواد الصف التاسع
        {
            "name_ar": "الرياضيات",
            "description_ar": "أساسيات الجبر والهندسة للصف التاسع",
            "grade": "grade_9",
            "icon": "📐",
            "color": "#2196F3",
            "order": 1
        },
        {
            "name_ar": "اللغة العربية",
            "description_ar": "النحو والأدب والبلاغة",
            "grade": "grade_9",
            "icon": "📖",
            "color": "#4CAF50",
            "order": 2
        },
        {
            "name_ar": "العلوم",
            "description_ar": "الفيزياء والكيمياء والأحياء",
            "grade": "grade_9",
            "icon": "🔬",
            "color": "#FF9800",
            "order": 3
        },
        # مواد الثالث الثانوي
        {
            "name_ar": "الرياضيات المتقدمة",
            "description_ar": "التفاضل والتكامل والإحصاء",
            "grade": "grade_12",
            "icon": "📊",
            "color": "#9C27B0",
            "order": 1
        },
        {
            "name_ar": "الفيزياء",
            "description_ar": "الفيزياء الحديثة والكهرومغناطيسية",
            "grade": "grade_12",
            "icon": "⚛️",
            "color": "#F44336",
            "order": 2
        },
        {
            "name_ar": "الكيمياء",
            "description_ar": "الكيمياء العضوية وغير العضوية",
            "grade": "grade_12",
            "icon": "🧪",
            "color": "#00BCD4",
            "order": 3
        }
    ]
    
    subjects = []
    for subject_data in subjects_data:
        subject_id = generate_id()
        subject = {
            "id": subject_id,
            **subject_data,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        await db.subjects.insert_one(subject)
        subjects.append(subject)
        print(f"✅ تم إنشاء المادة: {subject['name_ar']} - {subject['grade']}")
    
    # === 4. إنشاء الدروس ===
    print("\n📝 إنشاء الدروس...")
    
    lessons_count = 0
    for subject in subjects:
        # إنشاء 3 دروس لكل مادة
        for i in range(1, 4):
            lesson_id = generate_id()
            lesson = {
                "id": lesson_id,
                "subject_id": subject["id"],
                "title_ar": f"الدرس {i}: مقدمة في {subject['name_ar']}",
                "description_ar": f"شرح شامل للدرس {i} من مادة {subject['name_ar']}",
                "order": i,
                "summaries": [
                    {
                        "title_ar": f"ملخص الدرس {i}",
                        "content_type": "text",
                        "content_text": f"هذا ملخص شامل للدرس {i} يغطي النقاط الأساسية والمهمة في الموضوع.",
                        "order": 1
                    }
                ],
                "reviews": [
                    {
                        "title_ar": f"مراجعة الدرس {i}",
                        "content_type": "text",
                        "content_text": f"مراجعة سريعة لأهم نقاط الدرس {i} للتحضير للاختبار.",
                        "order": 1
                    }
                ],
                "pdfs": [
                    {
                        "title_ar": f"كتاب الدرس {i}",
                        "content_type": "pdf",
                        "content_url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
                        "order": 1
                    }
                ],
                "videos": [
                    {
                        "title_ar": f"شرح فيديو الدرس {i}",
                        "content_type": "video",
                        "content_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                        "duration_minutes": 15,
                        "order": 1
                    }
                ],
                "is_premium": i == 3,  # الدرس الثالث مدفوع
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            await db.lessons.insert_one(lesson)
            lessons_count += 1
    
    print(f"✅ تم إنشاء {lessons_count} درس")
    
    # === 5. إنشاء الأسئلة والاختبارات ===
    print("\n❓ إنشاء الأسئلة والاختبارات...")
    
    quizzes_count = 0
    questions_count = 0
    
    for subject in subjects:
        # إنشاء اختبار واحد لكل مادة
        quiz_id = generate_id()
        question_ids = []
        
        # إنشاء 10 أسئلة لكل اختبار (مزيج من الأنواع)
        for i in range(1, 11):
            question_id = generate_id()
            
            # تحديد نوع السؤال
            if i <= 5:
                # أسئلة اختيار من متعدد
                question = {
                    "id": question_id,
                    "subject_id": subject["id"],
                    "lesson_id": None,
                    "question_text_ar": f"ما هي {i}؟ (من مادة {subject['name_ar']})",
                    "question_type": "multiple_choice",
                    "choices": [
                        {"text_ar": "الخيار الأول", "is_correct": True},
                        {"text_ar": "الخيار الثاني", "is_correct": False},
                        {"text_ar": "الخيار الثالث", "is_correct": False},
                        {"text_ar": "الخيار الرابع", "is_correct": False}
                    ],
                    "correct_answer_boolean": None,
                    "correct_answer_text": None,
                    "explanation_ar": "الإجابة الصحيحة هي الخيار الأول لأن...",
                    "points": 1,
                    "difficulty": "medium",
                    "created_at": datetime.utcnow()
                }
            elif i <= 8:
                # أسئلة صح وخطأ
                question = {
                    "id": question_id,
                    "subject_id": subject["id"],
                    "lesson_id": None,
                    "question_text_ar": f"العبارة التالية صحيحة: البيان {i} في {subject['name_ar']}",
                    "question_type": "true_false",
                    "choices": [],
                    "correct_answer_boolean": i % 2 == 0,
                    "correct_answer_text": None,
                    "explanation_ar": f"هذه العبارة {'صحيحة' if i % 2 == 0 else 'خاطئة'} لأن...",
                    "points": 1,
                    "difficulty": "easy",
                    "created_at": datetime.utcnow()
                }
            else:
                # أسئلة إكمال الفراغ
                question = {
                    "id": question_id,
                    "subject_id": subject["id"],
                    "lesson_id": None,
                    "question_text_ar": f"أكمل الفراغ: _____ هو المفهوم الأساسي في {subject['name_ar']}",
                    "question_type": "fill_blank",
                    "choices": [],
                    "correct_answer_boolean": None,
                    "correct_answer_text": "التعلم",
                    "explanation_ar": "الكلمة الصحيحة هي 'التعلم' لأنها تمثل...",
                    "points": 2,
                    "difficulty": "hard",
                    "created_at": datetime.utcnow()
                }
            
            await db.questions.insert_one(question)
            question_ids.append(question_id)
            questions_count += 1
        
        # إنشاء الاختبار
        quiz = {
            "id": quiz_id,
            "subject_id": subject["id"],
            "title_ar": f"اختبار {subject['name_ar']}",
            "description_ar": f"اختبار شامل يغطي أهم نقاط مادة {subject['name_ar']}",
            "duration_minutes": 30,
            "passing_score": 60,
            "question_ids": question_ids,
            "is_premium": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        await db.quizzes.insert_one(quiz)
        quizzes_count += 1
    
    print(f"✅ تم إنشاء {questions_count} سؤال")
    print(f"✅ تم إنشاء {quizzes_count} اختبار")
    
    # === ملخص النهائي ===
    print("\n" + "="*50)
    print("✅ تمت إضافة البيانات التجريبية بنجاح!")
    print("="*50)
    print("\n📊 الإحصائيات:")
    print(f"   - المستخدمين: {len(students_data) + 1}")
    print(f"   - المواد: {len(subjects)}")
    print(f"   - الدروس: {lessons_count}")
    print(f"   - الأسئلة: {questions_count}")
    print(f"   - الاختبارات: {quizzes_count}")
    
    print("\n🔑 بيانات تسجيل الدخول:")
    print(f"   المدير: admin@tafawuq.com / admin123")
    print(f"   طالب صف تاسع: student9@tafawuq.com / student123")
    print(f"   طالب ثالث ثانوي: student12@tafawuq.com / student123")
    
    print("\n🚀 جاهز للاستخدام!")


if __name__ == "__main__":
    asyncio.run(seed_database())
