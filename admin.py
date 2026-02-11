import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import (
    add_teacher, is_teacher, create_quiz, get_teacher_quizzes,
    get_quiz_statistics, delete_quiz
)
from models import QuizBuilder, Question

logger = logging.getLogger(__name__)

# حالات المحادثة لإنشاء الكويز
(
    QUIZ_TITLE,
    QUIZ_DESCRIPTION,
    QUESTION_TEXT,
    QUESTION_TYPE,
    MCQ_OPTIONS,
    CORRECT_ANSWER,
    CONFIRM_QUESTION,
    CONFIRM_QUIZ
) = range(8)

# تخزين مؤقت لبناء الكويزات
quiz_builders = {}

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم المعلم"""
    user_id = update.effective_user.id
    
    # إضافة المعلم تلقائياً
    add_teacher(
        user_id,
        update.effective_user.username,
        update.effective_user.first_name
    )
    
    keyboard = [
        [InlineKeyboardButton("📝 إنشاء كويز جديد", callback_data="admin_create_quiz")],
        [InlineKeyboardButton("📋 قائمة الكويزات", callback_data="admin_list_quizzes")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("❓ المساعدة", callback_data="admin_help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👨‍🏫 **لوحة تحكم المعلم**\n\n"
        "مرحباً بك! يمكنك من هنا إدارة الكويزات الخاصة بك.\n\n"
        "اختر ما تريد فعله:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أزرار المعلم"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not is_teacher(user_id):
        await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الصفحة.")
        return
    
    data = query.data
    
    if data == "admin_create_quiz":
        await start_quiz_creation(update, context)
    
    elif data == "admin_list_quizzes":
        await list_teacher_quizzes(update, context)
    
    elif data == "admin_stats":
        await show_teacher_stats(update, context)
    
    elif data == "admin_help":
        await show_admin_help(update, context)

async def start_quiz_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إنشاء كويز جديد"""
    query = update.callback_query
    
    user_id = query.from_user.id
    quiz_builders[user_id] = QuizBuilder()
    
    await query.edit_message_text(
        "📝 **إنشاء كويز جديد**\n\n"
        "الخطوة 1/8: أدخل عنوان الكويز\n\n"
        "مثال: `اختبار الرياضيات - الفصل الأول`\n\n"
        "اكتب العنوان الآن:",
        parse_mode='Markdown'
    )
    
    return QUIZ_TITLE

async def receive_quiz_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام عنوان الكويز"""
    user_id = update.effective_user.id
    
    if user_id not in quiz_builders:
        await update.message.reply_text("❌ حدث خطأ. الرجاء البدء من جديد.")
        return ConversationHandler.END
    
    title = update.message.text.strip()
    quiz_builders[user_id].title = title
    
    await update.message.reply_text(
        f"✅ تم حفظ العنوان: **{title}**\n\n"
        "الخطوة 2/8: أدخل وصف الكويز\n\n"
        "مثال: `هذا الاختبار يغطي النهايات والاشتقاق`\n\n"
        "اكتب الوصف الآن:",
        parse_mode='Markdown'
    )
    
    return QUIZ_DESCRIPTION

async def receive_quiz_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام وصف الكويز"""
    user_id = update.effective_user.id
    
    if user_id not in quiz_builders:
        await update.message.reply_text("❌ حدث خطأ. الرجاء البدء من جديد.")
        return ConversationHandler.END
    
    description = update.message.text.strip()
    quiz_builders[user_id].description = description
    
    await update.message.reply_text(
        "✅ تم حفظ الوصف\n\n"
        "الخطوة 3/8: أدخل نص السؤال الأول\n\n"
        "اكتب السؤال الآن:",
        parse_mode='Markdown'
    )
    
    return QUESTION_TEXT

async def receive_question_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام نص السؤال"""
    user_id = update.effective_user.id
    
    if user_id not in quiz_builders:
        await update.message.reply_text("❌ حدث خطأ. الرجاء البدء من جديد.")
        return ConversationHandler.END
    
    question_text = update.message.text.strip()
    context.user_data['current_question_text'] = question_text
    
    keyboard = [
        [InlineKeyboardButton("📝 صح/خطأ (True/False)", callback_data="qtype_tf")],
        [InlineKeyboardButton("🔠 اختيار من متعدد (MCQ)", callback_data="qtype_mcq")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📝 نص السؤال: **{question_text}**\n\n"
        "الخطوة 4/8: اختر نوع السؤال:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return QUESTION_TYPE

async def receive_question_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام نوع السؤال"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    q_type = query.data.replace("qtype_", "")
    
    context.user_data['current_question_type'] = q_type
    
    if q_type == 'tf':
        keyboard = [
            [InlineKeyboardButton("✅ صح (True)", callback_data="answer_t")],
            [InlineKeyboardButton("❌ خطأ (False)", callback_data="answer_f")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "✅ تم اختيار **صح/خطأ**\n\n"
            "الخطوة 5/8: اختر الإجابة الصحيحة:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return CORRECT_ANSWER
    
    else:  # MCQ
        await query.edit_message_text(
            "✅ تم اختيار **اختيار من متعدد**\n\n"
            "الخطوة 5/8: أرسل الخيارات بالترتيب\n\n"
            "اكتب كل خيار في سطر منفصل:\n"
            "مثال:\n"
            "`الخيار أ`\n"
            "`الخيار ب`\n"
            "`الخيار ج`\n"
            "`الخيار د`",
            parse_mode='Markdown'
        )
        return MCQ_OPTIONS

async def receive_mcq_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام خيارات MCQ"""
    user_id = update.effective_user.id
    
    options_text = update.message.text.strip()
    options = [opt.strip() for opt in options_text.split('\n') if opt.strip()]
    
    if len(options) < 2:
        await update.message.reply_text(
            "❌ يجب إدخال خيارين على الأقل!\n\n"
            "الرجاء إدخال الخيارات مرة أخرى:"
        )
        return MCQ_OPTIONS
    
    # تسمية الخيارات بأحرف
    labeled_options = []
    for i, opt in enumerate(options[:4]):  # حد أقصى 4 خيارات
        label = chr(97 + i)  # a, b, c, d
        labeled_options.append(f"{label}) {opt}")
    
    context.user_data['current_options'] = labeled_options
    
    # إنشاء أزرار للاختيار
    keyboard = []
    for i, opt in enumerate(labeled_options[:4]):
        label = chr(97 + i)
        keyboard.append([InlineKeyboardButton(opt, callback_data=f"mcq_answer_{label}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✅ تم حفظ الخيارات\n\n"
        "الخطوة 6/8: اختر الإجابة الصحيحة:",
        reply_markup=reply_markup
    )
    
    return CORRECT_ANSWER

async def receive_correct_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام الإجابة الصحيحة"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in quiz_builders:
        await query.edit_message_text("❌ حدث خطأ. الرجاء البدء من جديد.")
        return ConversationHandler.END
    
    answer = query.data
    if answer.startswith('mcq_answer_'):
        answer = answer.replace('mcq_answer_', '')
    elif answer.startswith('answer_'):
        answer = answer.replace('answer_', '')
    
    # إنشاء السؤال
    question_num = len(quiz_builders[user_id].questions) + 1
    question_text = context.user_data.get('current_question_text', '')
    q_type = context.user_data.get('current_question_type', '')
    
    options = None
    if q_type == 'mcq':
        options = context.user_data.get('current_options', [])
    
    question = Question(
        question_num=question_num,
        question_text=question_text,
        question_type=q_type,
        correct_answer=answer,
        options=options
    )
    
    quiz_builders[user_id].add_question(question)
    
    # عرض السؤال المضاف
    question_display = f"**السؤال {question_num}:** {question_text}\n"
    question_display += f"**النوع:** {'صح/خطأ' if q_type == 'tf' else 'اختيار من متعدد'}\n"
    question_display += f"**الإجابة الصحيحة:** {answer.upper()}\n"
    
    if options:
        question_display += "**الخيارات:**\n"
        for opt in options[:4]:
            question_display += f"• {opt}\n"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ إضافة سؤال آخر", callback_data="quiz_add_another"),
            InlineKeyboardButton("🏁 إنهاء الكويز", callback_data="quiz_finish")
        ],
        [InlineKeyboardButton("❌ حذف هذا السؤال", callback_data="quiz_delete_last")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"✅ **تم إضافة السؤال بنجاح!**\n\n"
        f"{question_display}\n"
        f"📊 عدد الأسئلة الحالي: {len(quiz_builders[user_id].questions)}\n\n"
        f"ماذا تريد أن تفعل؟",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return CONFIRM_QUESTION

async def quiz_confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تأكيد الكويز"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in quiz_builders:
        await query.edit_message_text("❌ حدث خطأ. الرجاء البدء من جديد.")
        return ConversationHandler.END
    
    action = query.data
    
    if action == "quiz_add_another":
        # إضافة سؤال آخر
        await query.edit_message_text(
            f"📝 **إضافة سؤال جديد**\n\n"
            f"السؤال رقم: {len(quiz_builders[user_id].questions) + 1}\n\n"
            f"أدخل نص السؤال:",
            parse_mode='Markdown'
        )
        return QUESTION_TEXT
    
    elif action == "quiz_delete_last":
        # حذف آخر سؤال
        quiz_builders[user_id].remove_question(len(quiz_builders[user_id].questions))
        await query.edit_message_text(
            f"✅ **تم حذف آخر سؤال**\n\n"
            f"📊 عدد الأسئلة الحالي: {len(quiz_builders[user_id].questions)}\n\n"
            f"ماذا تريد أن تفعل؟",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ إضافة سؤال", callback_data="quiz_add_another"),
                 InlineKeyboardButton("🏁 إنهاء الكويز", callback_data="quiz_finish")]
            ])
        )
        return CONFIRM_QUESTION
    
    elif action == "quiz_finish":
        # إنهاء الكويز وحفظه
        quiz_data = quiz_builders[user_id].get_questions_dict()
        
        # الحصول على ID المعلم
        teacher = add_teacher(user_id, query.from_user.username, query.from_user.first_name)
        
        # حفظ الكويز في قاعدة البيانات
        quiz = create_quiz(
            teacher_id=teacher.id,
            title=quiz_data['title'],
            description=quiz_data['description'],
            questions=quiz_data['questions']
        )
        
        # عرض ملخص الكويز
        summary = (
            f"🎉 **تم إنشاء الكويز بنجاح!**\n\n"
            f"📌 **عنوان الكويز:** {quiz.title}\n"
            f"📝 **الوصف:** {quiz.description}\n"
            f"🔑 **كود الكويز:** `{quiz.quiz_code}`\n"
            f"📊 **عدد الأسئلة:** {len(quiz_data['questions'])}\n\n"
            f"✅ **مشاركة الكويز مع الطلاب:**\n"
            f"اطلب من الطلاب إرسال هذا الكود: `{quiz.quiz_code}`\n\n"
            f"أو استخدم رابط المشاركة:\n"
            f"`/join {quiz.quiz_code}`"
        )
        
        # تنظيف البيانات المؤقتة
        del quiz_builders[user_id]
        
        await query.edit_message_text(summary, parse_mode='Markdown')
        return ConversationHandler.END

async def list_teacher_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة كويزات المعلم"""
    query = update.callback_query
    
    user_id = query.from_user.id
    teacher = add_teacher(user_id, query.from_user.username, query.from_user.first_name)
    
    quizzes = get_teacher_quizzes(teacher.id)
    
    if not quizzes:
        await query.edit_message_text(
            "📋 **لا توجد كويزات بعد**\n\n"
            "ابدأ بإنشاء أول كويز لك!",
            parse_mode='Markdown'
        )
        return
    
    text = "📋 **قائمة الكويزات الخاصة بك:**\n\n"
    
    for quiz in quizzes[:10]:  # عرض آخر 10 كويزات
        stats = get_quiz_statistics(quiz.id)
        stats_text = f"👥 {quiz.total_students} طالب"
        if stats:
            stats_text += f" | 📊 {stats['avg_percentage']}%"
        
        text += f"**{quiz.title}**\n"
        text += f"🔑 كود: `{quiz.quiz_code}`\n"
        text += f"📅 {quiz.created_at.strftime('%Y-%m-%d')}\n"
        text += f"📊 {stats_text}\n"
        text += f"🔹 {quiz.total_questions or len(quiz.questions)} سؤال\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_teacher_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات المعلم"""
    query = update.callback_query
    
    user_id = query.from_user.id
    teacher = add_teacher(user_id, query.from_user.username, query.from_user.first_name)
    
    quizzes = get_teacher_quizzes(teacher.id)
    
    total_quizzes = len(quizzes)
    total_students = sum(q.total_students for q in quizzes)
    
    text = (
        f"📊 **إحصائيات شاملة**\n\n"
        f"👨‍🏫 **المعلم:** {teacher.full_name}\n"
        f"📋 **عدد الكويزات:** {total_quizzes}\n"
        f"👥 **إجمالي الطلاب:** {total_students}\n"
        f"📅 **عضو منذ:** {teacher.created_at.strftime('%Y-%m-%d')}\n\n"
    )
    
    if quizzes:
        text += "**آخر 3 كويزات:**\n"
        for quiz in quizzes[:3]:
            stats = get_quiz_statistics(quiz.id)
            if stats:
                text += f"• {quiz.title}: {stats['total_attempts']} محاولة، متوسط {stats['avg_percentage']}%\n"
            else:
                text += f"• {quiz.title}: لا توجد محاولات بعد\n"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض مساعدة المعلم"""
    query = update.callback_query
    
    help_text = (
        "👨‍🏫 **مساعدة المعلم**\n\n"
        "**الأوامر المتاحة:**\n"
        "/admin - فتح لوحة التحكم\n"
        "/create - إنشاء كويز جديد\n\n"
        
        "**كيفية إنشاء كويز:**\n"
        "1. اختر 'إنشاء كويز جديد'\n"
        "2. أدخل عنوان الكويز\n"
        "3. أدخل وصف الكويز\n"
        "4. أضف الأسئلة واحداً تلو الآخر\n"
        "5. اختر نوع السؤال (صح/خطأ أو MCQ)\n"
        "6. حدد الإجابة الصحيحة\n"
        "7. كرر حتى تنتهي من جميع الأسئلة\n"
        "8. اضغط 'إنهاء الكويز' للحفظ\n\n"
        
        "**مشاركة الكويز:**\n"
        "• كل كويز يحصل على كود فريد\n"
        "• أرسل الكود للطلاب\n"
        "• الطلاب يبدأون الكويز بإرسال `/join [الكود]`\n\n"
        
        "**مشاهدة النتائج:**\n"
        "• من قائمة الكويزات، اختر 'عرض النتائج'\n"
        "• يمكنك رؤية إحصائيات كل كويز\n"
        "• متوسط درجات الطلاب وعدد المحاولات"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

def get_admin_conv_handler():
    """الحصول على معالج محادثة إنشاء الكويز"""
    return ConversationHandler(
        entry_points=[
            CommandHandler("create", start_quiz_creation),
            CallbackQueryHandler(start_quiz_creation, pattern="^admin_create_quiz$")
        ],
        states={
            QUIZ_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_quiz_title)],
            QUIZ_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_quiz_description)],
            QUESTION_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_question_text)],
            QUESTION_TYPE: [CallbackQueryHandler(receive_question_type, pattern="^qtype_")],
            MCQ_OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_mcq_options)],
            CORRECT_ANSWER: [CallbackQueryHandler(receive_correct_answer, pattern="^(answer_|mcq_answer_)")],
            CONFIRM_QUESTION: [CallbackQueryHandler(quiz_confirmation_handler, pattern="^(quiz_add_another|quiz_delete_last|quiz_finish)$")]
        },
        fallbacks=[
            CommandHandler("cancel", lambda u,c: ConversationHandler.END),
            CallbackQueryHandler(lambda u,c: ConversationHandler.END, pattern="^admin_panel$")
        ]
    )
