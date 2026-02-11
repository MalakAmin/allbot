from typing import List, Dict, Any
import json

class Question:
    """نموذج السؤال"""
    
    def __init__(self, question_num: int, question_text: str, question_type: str, 
                 correct_answer: str, options: List[str] = None):
        self.question_num = question_num
        self.question_text = question_text
        self.question_type = question_type  # 'tf' أو 'mcq'
        self.correct_answer = correct_answer
        self.options = options or []
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل السؤال إلى قاموس"""
        return {
            'question_num': self.question_num,
            'question_text': self.question_text,
            'question_type': self.question_type,
            'correct_answer': self.correct_answer,
            'options': self.options
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """إنشاء سؤال من قاموس"""
        return cls(
            question_num=data['question_num'],
            question_text=data['question_text'],
            question_type=data['question_type'],
            correct_answer=data['correct_answer'],
            options=data.get('options', [])
        )
    
    def validate_answer(self, answer: str) -> bool:
        """التحقق من صحة الإجابة"""
        if self.question_type == 'tf':
            return answer.lower() == self.correct_answer.lower()
        else:
            return answer.lower() == self.correct_answer.lower()

class QuizBuilder:
    """بناء الكويزات"""
    
    def __init__(self):
        self.questions = []
        self.title = ""
        self.description = ""
    
    def add_question(self, question: Question):
        """إضافة سؤال"""
        self.questions.append(question)
    
    def remove_question(self, question_num: int):
        """حذف سؤال"""
        self.questions = [q for q in self.questions if q.question_num != question_num]
        # إعادة ترقيم الأسئلة
        for i, q in enumerate(self.questions, 1):
            q.question_num = i
    
    def get_questions_dict(self) -> Dict:
        """تحويل الأسئلة إلى قاموس للتخزين"""
        return {
            'title': self.title,
            'description': self.description,
            'questions': [q.to_dict() for q in self.questions],
            'total_questions': len(self.questions)
        }
    
    def load_from_dict(self, data: Dict):
        """تحميل الأسئلة من قاموس"""
        self.title = data.get('title', '')
        self.description = data.get('description', '')
        self.questions = [
            Question.from_dict(q_data) 
            for q_data in data.get('questions', [])
        ]
