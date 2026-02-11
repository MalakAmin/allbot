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
