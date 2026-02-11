# 🧮 بوت اختبارات رياضيات النهايات - مع Keep-alive
# 🔧 يعمل 24/7 على Render

import os
import asyncio
import json
import random
import threading
import time
import requests
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# 🔐 التوكن من متغيرات البيئة
TOKEN = os.environ.get('TELEGRAM_TOKEN')
TEACHER_ID = 8422436251  # غير هذا الرقم!

# 🌐 Flask لإبقاء البوت نشطاً
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <html>
        <head>
            <title>بوت الرياضيات</title>
            <style>
                body { font-family: Arial; text-align: center; padding: 50px; }
                h1 { color: #2c3e50; }
                .status { color: #27ae60; font-size: 24px; }
            </style>
        </head>
        <body>
            <h1>🤖 بوت اختبارات الرياضيات</h1>
            <div class="status">✅ يعمل بنجاح!</div>
            <p>⏰ يعمل 24/7 على Render</p>
            <p>👨🏫 للمعلم: استخدم /stats في Telegram</p>
            <p>📱 للطلاب: ابحث عن @mathimatical_testBot</p>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return {"status": "active", "timestamp": datetime.now().isoformat()}

@app.route('/ping')
def ping():
    return "pong"

# 🔄 وظيفة لإرسال طلبات دورية
def keep_alive():
    """إبقاء البوت نشطاً بإرسال طلبات دورية"""
    def ping_server():
        while True:
            try:
                # الحصول على رابط Render تلقائياً
                render_url = os.environ.get('RENDER_URL', '')
                if not render_url:
                    # محاولة تخمين الرابط
                    service_name = os.environ.get('RENDER_SERVICE_NAME', '')
                    if service_name:
                        render_url = f"https://{service_name}.onrender.com"
                
                if render_url:
                    response = requests.get(f"{render_url}/ping", timeout=10)
                    print(f"✅ Keep-alive ping: {response.status_code} at {datetime.now().strftime('%H:%M:%S')}")
                else:
                    print("⚠️ لا يمكن تحديد رابط Render")
            except Exception as e:
                print(f"⚠️ Keep-alive failed: {e}")
            time.sleep(300)  # كل 5 دقائق
    
    thread = threading.Thread(target=ping_server, daemon=True)
    thread.start()

# 📊 قاعدة البيانات
class Database:
    def __init__(self):
        self.data_file = 'data.json'
        self.data = self.load_data()
    
    def load_data(self):
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {'students': {}, 'total_questions': 0, 'correct_answers': 0}
    
    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def register_student(self, user_id, name):
        user_id = str(user_id)
        if user_id not in self.data['students']:
            self.data['students'][user_id] = {
                'name': name,
                'correct': 0,
                'total': 0,
                'joined': datetime.now().strftime('%Y-%m-%d'),
                'last_active': datetime.now().isoformat()
            }
            self.save_data()
            return True
        return False
    
    def update_score(self, user_id, is_correct):
        user_id = str(user_id)
        if user_id in self.data['students']:
            self.data['students'][user_id]['total'] += 1
            self.data['students'][user_id]['last_active'] = datetime.now().isoformat()
            
            if is_correct:
                self.data['students'][user_id]['correct'] += 1
            
            self.data['total_questions'] += 1
            if is_correct:
                self.data['correct_answers'] += 1
            
            self.save_data()
            return self.data['students'][user_id]

db = Database()

# 📚 الأسئلة (نفس الأسئلة السابقة)
TRUE_FALSE_QUESTIONS = [
    {"id": 1, "q": "lim┬(x→0)〖sin(x)/x = 1〗", "ans": True, "exp": "نعم، هذه نهاية أساسية"},
    {"id": 2, "q": "lim┬(x→∞)〖1/x = ∞〗", "ans": False, "exp": "خطأ، النهاية = 0"},
    {"id": 3, "q": "lim┬(x→2)〖(x²-4)/(x-2)=4〗", "ans": True, "exp": "صحيح، (x²-4)/(x-2)=x+2"},
]

MCQ_QUESTIONS = [
    {"id": 1, "q": "ما قيمة: lim┬(x→3)〖(x²-9)/(x-3)〗؟", "ops": ["0", "3", "6", "9"], "ans": 2, "exp": "الحل: (x²-9)/(x-3)=x+3، النهاية=6"},
    {"id": 2, "q": "lim┬(x→0)〖(e^x-1)/x〗=؟", "ops": ["0", "1", "e", "∞"], "ans": 1, "exp": "نهاية أساسية = 1"},
]

# 🎯 دوال البوت (نفس الدوال السابقة)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_new = db.register_student(user.id, user.first_name)
    
    if is_new:
        msg = f"🎉 أهلاً {user.first_name}!\nتم تسجيلك في بوت اختبارات النهايات."
    else:
        student = db.data['students'].get(str(user.id), {})
        msg = f"👋 أهلًا بعودتك {user.first_name}!\nنتيجتك: {student.get('correct', 0)}/{student.get('total', 0)}"
    
    msg += "\n\n📋 الأوامر:\n/start - البداية\n/truefalse - أسئلة صح/خطأ\n/mcq - أسئلة خيارات\n/score - نتيجتك\n/top - المتصدرين"
    
    await update.message.reply_text(msg)

async def truefalse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = random.choice(TRUE_FALSE_QUESTIONS)
    buttons = [
        [InlineKeyboardButton("✅ صحيح", callback_data=f"tf_{q['id']}_true")],
        [InlineKeyboardButton("❌ خطأ", callback_data=f"tf_{q['id']}_false")]
    ]
    text = f"🔵 سؤال صح/خطأ:\n\n❓ {q['q']}"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def mcq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = random.choice(MCQ_QUESTIONS)
    buttons = []
    letters = ['أ', 'ب', 'ج', 'د']
    for i, option in enumerate(q['ops']):
        buttons.append([InlineKeyboardButton(f"{letters[i]}. {option}", callback_data=f"mcq_{q['id']}_{i}")])
    text = f"🔴 سؤال خيارات:\n\n❓ {q['q']}"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    q_type, q_id, answer = data[0], int(data[1]), data[2]
    
    if q_type == 'tf':
        q = next((q for q in TRUE_FALSE_QUESTIONS if q['id'] == q_id), None)
        if q:
            is_correct = ((answer == 'true') == q['ans'])
            msg = f"✅ صحيح!\n\n{q['exp']}" if is_correct else f"❌ خطأ!\n\n{q['exp']}"
            db.update_score(query.from_user.id, is_correct)
    
    elif q_type == 'mcq':
        q = next((q for q in MCQ_QUESTIONS if q['id'] == q_id), None)
        if q:
            is_correct = (int(answer) == q['ans'])
            letters = ['أ', 'ب', 'ج', 'د']
            if is_correct:
                msg = f"✅ إجابة صحيحة!\n\n{q['exp']}"
            else:
                correct = letters[q['ans']]
                msg = f"❌ إجابة خاطئة!\nالصحيحة: {correct}\n\n{q['exp']}"
            db.update_score(query.from_user.id, is_correct)
    
    user_id = str(query.from_user.id)
    if user_id in db.data['students']:
        student = db.data['students'][user_id]
        msg += f"\n\n📊 نتيجتك: {student['correct']}/{student['total']}"
    
    msg += "\n\n🔁 /truefalse - /mcq"
    await query.edit_message_text(msg)

async def score_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in db.data['students']:
        await update.message.reply_text("⚠️ اكتب /start أولاً")
        return
    
    student = db.data['students'][user_id]
    total, correct = student['total'], student['correct']
    percent = (correct/total*100) if total > 0 else 0
    
    report = f"📊 نتيجتك:\n✅ {correct} صحيح\n❌ {total-correct} خطأ\n🎯 {percent:.1f}%\n📅 {student['joined']}"
    await update.message.reply_text(report)

# 🔧 تشغيل Flask في خيط منفصل
def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# 🔧 تشغيل البوت
def run_telegram_bot():
    print("=" * 50)
    print("🧮 بوت اختبارات رياضيات النهايات")
    print("=" * 50)
    print(f"📅 بدأ التشغيل: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"👥 الطلاب المسجلين: {len(db.data['students'])}")
    print("✅ البوت يعمل 24/7 مع Keep-alive!")
    print("=" * 50)
    
    # بدء Keep-alive
    keep_alive()
    
    # تشغيل البوت
    async def main():
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("truefalse", truefalse_command))
        app.add_handler(CommandHandler("mcq", mcq_command))
        app.add_handler(CommandHandler("score", score_command))
        app.add_handler(CallbackQueryHandler(handle_answer, pattern="^tf_"))
        app.add_handler(CallbackQueryHandler(handle_answer, pattern="^mcq_"))
        
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        # استمر في التشغيل
        while True:
            await asyncio.sleep(3600)
    
    asyncio.run(main())

# 🚀 نقطة البداية
if __name__ == "__main__":
    # تشغيل Flask في خيط منفصل
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # تشغيل البوت بعد ثانيتين
    time.sleep(2)
    run_telegram_bot()
