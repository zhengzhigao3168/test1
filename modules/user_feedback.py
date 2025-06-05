import time
import json
from typing import List, Dict, Optional

class UserFeedbackManager:
    """用户反馈收集与分析模块"""
    def __init__(self, feedback_file: str = "user_feedback_data.json"):
        self.feedback_file = feedback_file
        self.feedback_data = self.load_feedback_data()

    def load_feedback_data(self) -> List[Dict]:
        try:
            with open(self.feedback_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_feedback_data(self):
        with open(self.feedback_file, "w", encoding="utf-8") as f:
            json.dump(self.feedback_data, f, ensure_ascii=False, indent=2)

    def add_feedback(self, user: str, content: str, feedback_type: str, extra: Optional[Dict] = None):
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "user": user,
            "content": content,
            "feedback_type": feedback_type,
            "extra": extra or {}
        }
        self.feedback_data.append(entry)
        self.save_feedback_data()

    def get_feedback_summary(self) -> Dict[str, int]:
        summary = {}
        for entry in self.feedback_data:
            ft = entry.get("feedback_type", "未知")
            summary[ft] = summary.get(ft, 0) + 1
        return summary

    def analyze_feedback(self) -> Dict:
        # 简单分析：统计各类反馈数量，提取常见建议
        summary = self.get_feedback_summary()
        suggestions = [entry["content"] for entry in self.feedback_data if entry["feedback_type"] in ["建议", "补充"]]
        return {
            "summary": summary,
            "suggestions": suggestions,
            "total": len(self.feedback_data)
        }

    def generate_improvement_suggestions(self) -> List[str]:
        # 基于收集到的建议内容，简单去重后输出
        analysis = self.analyze_feedback()
        suggestions = list(set(analysis["suggestions"]))
        return suggestions 