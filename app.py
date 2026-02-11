import os
import sys
import logging
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler
)
from dotenv import load_dotenv

# إعداد logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تحميل متغيرات البيئة
load_dotenv()

# استيراد الملفات المحلية
from database import add_teacher, is_teacher, get_db
from admin import admin_panel, admin_callback_handler, get_admin_conv_handler
from student import get_student_conv_handler, student_history

# متغيرات
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', 10000))

async def start(update: Update, context):
    """معالج أمر /start"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    # التحقق مما إذا كان المستخدم معلم
    if is_teacher(user_id):
        # فتح لوحة تحكم المعلم
        await admin_panel(update, context)
    else:
        # رسالة ترحيب للطالب
        await update.message.reply_text(
            "📚 **مرحباً بك في بوت الكويزات التعليمي!**\n\n"
            "🎯 **للطلاب:**\n"
            "• احصل على كود الكويز من معلمك\n"
            "• أرسل `/join [الكود]` لبدء الاختبار\n"
            "• مثال: `/join ABC123`\n\n"
            "📊 **لمشاهدة نتائجك السابقة:**\n"
            "• أرسل `/history`\n\n"
            "👨‍🏫 **للمعلمين:**\n"
            "• إذا كنت معلماً، أرسل `/admin` للدخول للوحة التحكم",
            parse_mode='Markdown'
        )

async def admin_command(update: Update, context):
    """معالج أمر /admin"""
    await admin_panel(update, context)

async def history_command(update: Update, context):
    """معالج أمر /history"""
    # إنشاء callback query وهمي لاستخدام الدالة
    class MockQuery:
        def __init__(self, user_id, chat_id):
            self.from_user = type('User', (), {'id': user_id})()
            self.message = type('Message', (), {'chat_id': chat_id})()
        
        async def answer(self):
            pass
        
        async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
            return await context.bot.send_message(
                chat_id=self.message.chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
    
    mock_query = MockQuery(update.effective_user.id, update.effective_chat.id)
    await student_history(update, context)

async def help_command(update: Update, context):
    """معالج أمر /help"""
    help_text = (
        "📚 **مساعدة البوت**\n\n"
        "**🎯 أوامر الطلاب:**\n"
        "/join [الكود] - الانضمام إلى كويز\n"
        "/history - عرض سجل المحاولات\n"
        "/start - الصفحة الرئيسية\n\n"
        "**👨‍🏫 أوامر المعلمين:**\n"
        "/admin - فتح لوحة التحكم\n"
        "/create - إنشاء كويز جديد\n\n"
        "**❓ للمساعدة الإضافية:**\n"
        "تواصل مع الدعم الفني @AdminBot"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def cancel(update: Update, context):
    """إلغاء المحادثة الحالية"""
    await update.message.reply_text(
        "✅ تم إلغاء العملية.",
        parse_mode='Markdown'
    )
    return ConversationHandler.END

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    logger.info("🚀 بدء تشغيل بوت الكويزات...")
    
    # التحقق من التوكن
    if not TOKEN:
        logger.error("❌ TOKEN غير موجود!")
        return
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة معالج المحادثة للمعلم
    application.add_handler(get_admin_conv_handler())
    
    # إضافة معالج المحادثة للطالب
    application.add_handler(get_student_conv_handler())
    
    # إضافة الأوامر الرئيسية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # إضافة معالج callback للمعلم
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))
    
    # التحقق مما إذا كان على Render
    is_render = os.getenv('RENDER', '').lower() in ['true', '1', 'yes']
    
    if is_render:
        # استخدام webhook
        render_service_name = os.getenv('RENDER_SERVICE_NAME', 'math-limits-bot2')
        webhook_url = f"https://{render_service_name}.onrender.com/{TOKEN}"
        
        logger.info(f"🌐 استخدام webhook: {webhook_url}")
        
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=webhook_url,
            drop_pending_updates=True
        )
    else:
        # استخدام polling
        logger.info("💻 التشغيل محلياً")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )

if __name__ == '__main__':
    main()
