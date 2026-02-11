import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import (
    get_quiz_by_code, start_student_attempt, save_answer,
    complete_attempt, get_student_attempts
)
from models import Question

logger = logging.getLogger(__name__)

# حالات المحادثة للطالب
ENTER_QUIZ_CODE, ANSWER_QUESTION, SHOW_RESULTS = range(3)

# تخزين مؤقت لمحاولات الطلاب
student_sessions = {}

async def join_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الانضمام إلى كويز باستخدام الكود"""
    # استخراج كود الكويز من الرسالة
    text = update.message.text.strip()
    parts = text.split()
    
    if len(parts) >= 2:
        quiz_code = parts[1]
        return await start_quiz_with_code(update, context, quiz_code)
    else:
        await update.message.reply_text(
            "📝 **الانضمام إلى كويز**\n\n"
            "الرجاء إدخال كود الكويز:\n\n"
            "مثال: `/join ABC123`",
            parse_mode='Markdown'
        )
        return ENTER_QUIZ_CODE

async def receive_quiz_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام كود الكويز من الطالب"""
    quiz_code = update.message.text.strip().upper()
    return await start_quiz_with_code(update, context, quiz_code)

async def start_quiz_with_code(update: Update, context: ContextTypes.DEFAULT_TYPE, quiz_code):
    """بدء الكويز بالكود"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    # البحث عن الكويز
    quiz = get_quiz_by_code(quiz_code)
    
    if not quiz:
        await update.message.reply_text(
            "❌ **كود غير صحيح**\n\n"
            "لم يتم العثور على كويز بهذا الكود.\n"
            "الرجاء التحقق من الكود والمحاولة مرة أخرى.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    # التحقق من وجود الكويز وأسئلته
    if not quiz.questions:
        await update.message.reply_text(
            "❌ **عذراً، هذا الكويز لا يحتوي على أسئلة**",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    # إنشاء محاولة جديدة
    attempt = start_student_attempt(
        quiz_id=quiz.id,
        student_telegram_id=user_id,
        student_name=username
    )
    
    # تخزين جلسة الطالب
    student_sessions[user_id] = {
        'quiz_id': quiz.id,
        'quiz_code': quiz.quiz_code,
        'quiz_title': quiz.title,
        'attempt_id': attempt.id,
        'current_question': 0,
        'questions': quiz.questions,
        'total_questions': len(quiz.questions),
        'score': 0,
        'answers': []
    }
    
    # عرض معلومات الكويز
    await update.message.reply_text(
        f"✅ **تم الانضمام إلى الكويز بنجاح!**\n\n"
        f"📚 **عنوان الكويز:** {quiz.title}\n"
        f"📝 **الوصف:** {quiz.description}\n"
        f"📊 **عدد الأسئلة:** {len(quiz.questions)}\n\n"
        f"🎯 **جاري بدء الاختبار...**",
        parse_mode='Markdown'
    )
    
    # إرسال أول سؤال
    await send_student_question(update, context, user_id)
    return ANSWER_QUESTION

async def send_student_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """إرسال سؤال للطالب"""
    session = student_sessions[user_id]
    q_index = session['current_question']
    
    if q_index >= session['total_questions']:
        await finish_student_quiz(update, context, user_id)
        return
    
    question_data = session['questions'][q_index]
    question = Question.from_dict(question_data)
    question_num = q_index + 1
    
    # بناء نص السؤال
    text = f"**السؤال {question_num}/{session['total_questions']}**\n\n"
    text += f"{question.question_text}\n\n"
    
    if question.question_type == 'tf':
        text += "اختر الإجابة الصحيحة:"
        keyboard = [
            [
                InlineKeyboardButton("✅ صح", callback_data=f"student_answer_t_{q_index}"),
                InlineKeyboardButton("❌ خطأ", callback_data=f"student_answer_f_{q_index}")
            ]
        ]
    else:
        text += "اختر الإجابة الصحيحة من الخيارات التالية:\n"
        keyboard = []
        
        for option in question.options[:4]:
            # استخراج الحرف من بداية الخيار
            opt_letter = option[0] if option else 'a'
            opt_text = option[3:] if len(option) > 3 else option
            keyboard.append([
                InlineKeyboardButton(f"{opt_letter}) {opt_text}", 
                                    callback_data=f"student_answer_{opt_letter}_{q_index}")
            ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_student_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إجابة الطالب"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in student_sessions:
        await query.edit_message_text("❌ جلسة الاختبار منتهية. ابدأ من جديد بـ /join")
        return
    
    session = student_sessions[user_id]
    
    # استخراج البيانات
    data = query.data
    parts = data.split('_')
    
    if len(parts) != 4:
        return
    
    answer = parts[2]
    q_index = int(parts[3])
    
    # الحصول على السؤال
    question_data = session['questions'][q_index]
    question = Question.from_dict(question_data)
    
    # التحقق من الإجابة
    is_correct = question.validate_answer(answer)
    
    if is_correct:
        session['score'] += 1
    
    # حفظ الإجابة
    session['answers'].append({
        'question_num': q_index + 1,
        'user_answer': answer,
        'correct_answer': question.correct_answer,
        'is_correct': is_correct
    })
    
    # حفظ في قاعدة البيانات
    save_answer(
        attempt_id=session['attempt_id'],
        question_num=q_index + 1,
        answer=answer,
        is_correct=is_correct
    )
    
    # عرض نتيجة الإجابة
    emoji = "✅" if is_correct else "❌"
    correct_display = "صح" if question.correct_answer == 't' else "خطأ" if question.correct_answer == 'f' else question.correct_answer.upper()
    answer_display = "صح" if answer == 't' else "خطأ" if answer == 'f' else answer.upper()
    
    await query.edit_message_text(
        f"{emoji} **السؤال {q_index + 1}**\n\n"
        f"إجابتك: {answer_display}\n"
        f"{'✓ إجابة صحيحة' if is_correct else f'✗ الإجابة الصحيحة: {correct_display}'}\n\n"
        f"⏳ جاري تحميل السؤال التالي...",
        parse_mode='Markdown'
    )
    
    # الانتقال للسؤال التالي
    session['current_question'] += 1
    
    await send_student_question(update, context, user_id)

async def finish_student_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """إنهاء الكويز وعرض النتيجة"""
    session = student_sessions[user_id]
    
    score = session['score']
    total = session['total_questions']
    percentage = (score / total) * 100 if total > 0 else 0
    
    # تحديث قاعدة البيانات
    complete_attempt(session['attempt_id'], score, total)
    
    # تحديد المستوى
    if percentage >= 90:
        level = "ممتاز 🏆"
    elif percentage >= 75:
        level = "جيد جداً ⭐"
    elif percentage >= 50:
        level = "مقبول ✓"
    else:
        level = "ضعف 📉"
    
    # بناء رسالة النتيجة
    result_text = (
        f"🎉 **تم الانتهاء من الاختبار!**\n\n"
        f"📚 **الكويز:** {session['quiz_title']}\n"
        f"📊 **نتيجتك:**\n"
        f"• الإجابات الصحيحة: {score}/{total}\n"
        f"• النسبة المئوية: {percentage:.1f}%\n"
        f"• المستوى: {level}\n\n"
    )
    
    # عرض تفاصيل الإجابات (اختصاراً)
    correct_count = sum(1 for a in session['answers'] if a['is_correct'])
    wrong_count = total - correct_count
    
    result_text += (
        f"📋 **ملخص:**\n"
        f"✅ صحيح: {correct_count}\n"
        f"❌ خطأ: {wrong_count}\n\n"
    )
    
    # عرض أول 3 أخطاء إن وجدت
    wrong_answers = [a for a in session['answers'] if not a['is_correct']][:3]
    if wrong_answers:
        result_text += "**⚠️ أسئلة تحتاج مراجعة:**\n"
        for a in wrong_answers:
            user_display = "صح" if a['user_answer'] == 't' else "خطأ" if a['user_answer'] == 'f' else a['user_answer'].upper()
            correct_display = "صح" if a['correct_answer'] == 't' else "خطأ" if a['correct_answer'] == 'f' else a['correct_answer'].upper()
            result_text += f"• سؤال {a['question_num']}: إجابتك ({user_display}) | الصحيحة ({correct_display})\n"
    
    keyboard = [
        [InlineKeyboardButton("📊 سجل المحاولات", callback_data="student_history")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id if hasattr(update, 'message') else query.message.chat.id,
        text=result_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # تنظيف الجلسة
    del student_sessions[user_id]

async def student_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض سجل محاولات الطالب"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    attempts = get_student_attempts(user_id)
    
    if not attempts:
        await query.edit_message_text(
            "📊 **لا توجد محاولات سابقة**\n\n"
            "ابدأ بحل كويز جديد باستخدام /join",
            parse_mode='Markdown'
        )
        return
    
    text = "📊 **سجل المحاولات:**\n\n"
    
    for attempt in attempts[:10]:  # آخر 10 محاولات
        quiz = get_quiz_by_code(attempt.quiz_id)  # تحتاج دالة للحصول على الكويز
        quiz_title = quiz.title if quiz else "كويز"
        
        text += f"**{quiz_title}**\n"
        text += f"📅 {attempt.completed_at.strftime('%Y-%m-%d %H:%M')}\n"
        text += f"✅ {attempt.score}/{attempt.total_questions} | {attempt.percentage:.1f}%\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

def get_student_conv_handler():
    """الحصول على معالج محادثة الطالب"""
    return ConversationHandler(
        entry_points=[
            CommandHandler("join", join_quiz),
            MessageHandler(filters.Regex(r'^/join'), join_quiz)
        ],
        states={
            ENTER_QUIZ_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_quiz_code)],
            ANSWER_QUESTION: [CallbackQueryHandler(handle_student_answer, pattern="^student_answer_")]
        },
        fallbacks=[
            CommandHandler("cancel", lambda u,c: ConversationHandler.END)
        ]
    )
