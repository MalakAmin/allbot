import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# الاتصال بقاعدة البيانات
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///quiz_bot.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

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
    quiz_code = Column(String(50), unique=True, nullable=False)  # كود الكويز
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
    percentage = Column(Float, default=0)
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
        return db
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
            return teacher
        return teacher
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
    finally:
        db.close()

# ============= دوال الكويزات =============

def generate_quiz_code():
    """توليد كود عشوائي للكويز"""
    import random
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def create_quiz(teacher_id, title, description, questions):
    """إنشاء كويز جديد"""
    db = SessionLocal()
    try:
        quiz_code = generate_quiz_code()
        # التأكد من عدم تكرار الكود
        while db.query(Quiz).filter(Quiz.quiz_code == quiz_code).first():
            quiz_code = generate_quiz_code()
        
        quiz = Quiz(
            teacher_id=teacher_id,
            quiz_code=quiz_code,
            title=title,
            description=description,
            questions=questions
        )
        db.add(quiz)
        db.commit()
        return quiz
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
    finally:
        db.close()

def update_quiz(quiz_id, **kwargs):
    """تحديث بيانات الكويز"""
    db = SessionLocal()
    try:
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if quiz:
            for key, value in kwargs.items():
                setattr(quiz, key, value)
            db.commit()
        return quiz
    finally:
        db.close()

def delete_quiz(quiz_id):
    """حذف كويز (تعطيله)"""
    return update_quiz(quiz_id, is_active=False)

# ============= دوال محاولات الطلاب =============

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
            attempt.answers[str(question_num)] = {
                'answer': answer,
                'is_correct': is_correct
            }
            db.commit()
        return attempt
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
            attempt.percentage = (score / total_questions) * 100 if total_questions > 0 else 0
            attempt.completed_at = datetime.now()
            attempt.is_completed = True
            db.commit()
        return attempt
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
        avg_score = sum(a.score for a in attempts) / total_attempts
        avg_percentage = sum(a.percentage for a in attempts) / total_attempts
        
        return {
            'total_attempts': total_attempts,
            'avg_score': round(avg_score, 1),
            'avg_percentage': round(avg_percentage, 1),
            'max_score': max(a.score for a in attempts),
            'min_score': min(a.score for a in attempts)
        }
    finally:
        db.close()
