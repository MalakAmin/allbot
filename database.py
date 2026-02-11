import os
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import JSON  # استيراد منفصل

logger = logging.getLogger(__name__)

# الحصول على رابط قاعدة البيانات
DATABASE_URL = os.getenv('DATABASE_URL', '')

# تحويل الرابط للتنسيق الصحيح
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# إذا كان الرابط فارغاً، استخدم SQLite للتجربة المحلية
if not DATABASE_URL:
    DATABASE_URL = 'sqlite:///quiz_bot.db'
    logger.warning("⚠️ لم يتم العثور على DATABASE_URL، استخدام SQLite محلياً")

# إنشاء الاتصال
try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    logger.info(f"✅ تم الاتصال بقاعدة البيانات: {DATABASE_URL.split('@')[0] if '@' in DATABASE_URL else 'محلي'}")
except Exception as e:
    logger.error(f"❌ فشل الاتصال بقاعدة البيانات: {e}")
    # استخدام SQLite كنسخة احتياطية
    engine = create_engine('sqlite:///quiz_bot_backup.db')
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    logger.warning("⚠️ استخدام SQLite كنسخة احتياطية")

# ============= نماذج قاعدة البيانات =============

class Teacher(Base):
    """جدول المعلمين"""
    __tablename__ = 'teachers'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    full_name = Column(String(200))
    created_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)

class Quiz(Base):
    """جدول الكويزات"""
    __tablename__ = 'quizzes'
    
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, nullable=False)
    quiz_code = Column(String(50), unique=True, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    questions = Column(JSON)  # تخزين الأسئلة كـ JSON
    created_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    total_students = Column(Integer, default=0)

class StudentAttempt(Base):
    """جدول محاولات الطلاب"""
    __tablename__ = 'student_attempts'
    
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, nullable=False)
    student_telegram_id = Column(Integer, nullable=False)
    student_name = Column(String(200))
    answers = Column(JSON)  # تخزين الإجابات كـ JSON
    score = Column(Integer, default=0)
    total_questions = Column(Integer, default=0)
    percentage = Column(Integer, default=0)  # تخزين كنسبة مئوية * 100
    started_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime)
    is_completed = Column(Boolean, default=False)

# إنشاء الجداول
Base.metadata.create_all(bind=engine)

# ============= دوال إدارة قاعدة البيانات =============

def get_db():
    """الحصول على جلسة قاعدة البيانات"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============= دوال المعلمين =============

def add_teacher(telegram_id, username, full_name):
    """إضافة معلم جديد"""
    db = SessionLocal()
    try:
        teacher = db.query(Teacher).filter(Teacher.telegram_id == telegram_id).first()
        if not teacher:
            teacher = Teacher(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name
            )
            db.add(teacher)
            db.commit()
            logger.info(f"✅ معلم جديد: {username}")
        return teacher
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة المعلم: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def is_teacher(telegram_id):
    """التحقق مما إذا كان المستخدم معلماً"""
    db = SessionLocal()
    try:
        teacher = db.query(Teacher).filter(
            Teacher.telegram_id == telegram_id,
            Teacher.is_active == True
        ).first()
        return teacher is not None
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من المعلم: {e}")
        return False
    finally:
        db.close()

# ============= دوال الكويزات =============

import random
import string

def generate_quiz_code():
    """توليد كود عشوائي للكويز"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def create_quiz(teacher_id, title, description, questions):
    """إنشاء كويز جديد"""
    db = SessionLocal()
    try:
        # توليد كود فريد
        while True:
            quiz_code = generate_quiz_code()
            existing = db.query(Quiz).filter(Quiz.quiz_code == quiz_code).first()
            if not existing:
                break
        
        quiz = Quiz(
            teacher_id=teacher_id,
            quiz_code=quiz_code,
            title=title,
            description=description,
            questions=questions
        )
        db.add(quiz)
        db.commit()
        logger.info(f"✅ كويز جديد: {title} - الكود: {quiz_code}")
        return quiz
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء الكويز: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def get_quiz_by_code(quiz_code):
    """الحصول على كويز بواسطة الكود"""
    db = SessionLocal()
    try:
        return db.query(Quiz).filter(
            Quiz.quiz_code == quiz_code.upper(),
            Quiz.is_active == True
        ).first()
    except Exception as e:
        logger.error(f"❌ خطأ في البحث عن الكويز: {e}")
        return None
    finally:
        db.close()

def get_teacher_quizzes(teacher_id):
    """الحصول على جميع كويزات المعلم"""
    db = SessionLocal()
    try:
        return db.query(Quiz).filter(
            Quiz.teacher_id == teacher_id,
            Quiz.is_active == True
        ).order_by(Quiz.created_at.desc()).all()
    except Exception as e:
        logger.error(f"❌ خطأ في جلب كويزات المعلم: {e}")
        return []
    finally:
        db.close()

def get_quiz_statistics(quiz_id):
    """الحصول على إحصائيات الكويز"""
    db = SessionLocal()
    try:
        attempts = db.query(StudentAttempt).filter(
            StudentAttempt.quiz_id == quiz_id,
            StudentAttempt.is_completed == True
        ).all()
        
        if not attempts:
            return None
        
        total_attempts = len(attempts)
        total_score = sum(a.score for a in attempts)
        total_percentage = sum(a.percentage for a in attempts)
        
        return {
            'total_attempts': total_attempts,
            'avg_score': round(total_score / total_attempts, 1),
            'avg_percentage': round(total_percentage / total_attempts, 1),
            'max_score': max(a.score for a in attempts),
            'min_score': min(a.score for a in attempts)
        }
    except Exception as e:
        logger.error(f"❌ خطأ في جلب الإحصائيات: {e}")
        return None
    finally:
        db.close()

def start_student_attempt(quiz_id, student_telegram_id, student_name):
    """بدء محاولة جديدة للطالب"""
    db = SessionLocal()
    try:
        attempt = StudentAttempt(
            quiz_id=quiz_id,
            student_telegram_id=student_telegram_id,
            student_name=student_name,
            answers={}
        )
        db.add(attempt)
        db.commit()
        
        # تحديث عدد الطلاب في الكويز
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if quiz:
            quiz.total_students += 1
            db.commit()
        
        return attempt
    except Exception as e:
        logger.error(f"❌ خطأ في بدء المحاولة: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def complete_attempt(attempt_id, score, total_questions):
    """إنهاء محاولة الطالب"""
    db = SessionLocal()
    try:
        attempt = db.query(StudentAttempt).filter(StudentAttempt.id == attempt_id).first()
        if attempt:
            attempt.score = score
            attempt.total_questions = total_questions
            percentage = (score / total_questions) * 100 if total_questions > 0 else 0
            attempt.percentage = int(percentage)  # تخزين كرقم صحيح
            attempt.completed_at = datetime.now()
            attempt.is_completed = True
            db.commit()
            logger.info(f"✅ محاولة منتهية: {attempt_id}, النتيجة: {score}/{total_questions}")
        return attempt
    except Exception as e:
        logger.error(f"❌ خطأ في إنهاء المحاولة: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def get_student_attempts(student_telegram_id):
    """الحصول على جميع محاولات الطالب"""
    db = SessionLocal()
    try:
        return db.query(StudentAttempt).filter(
            StudentAttempt.student_telegram_id == student_telegram_id,
            StudentAttempt.is_completed == True
        ).order_by(StudentAttempt.completed_at.desc()).all()
    except Exception as e:
        logger.error(f"❌ خطأ في جلب محاولات الطالب: {e}")
        return []
    finally:
        db.close()

def save_answer(attempt_id, question_num, answer, is_correct):
    """حفظ إجابة الطالب"""
    db = SessionLocal()
    try:
        attempt = db.query(StudentAttempt).filter(StudentAttempt.id == attempt_id).first()
        if attempt:
            if not attempt.answers:
                attempt.answers = {}
            if isinstance(attempt.answers, dict):
                attempt.answers[str(question_num)] = {
                    'answer': answer,
                    'is_correct': is_correct
                }
            db.commit()
        return attempt
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ الإجابة: {e}")
        db.rollback()
        return None
    finally:
        db.close()
