import re
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SqlValidator:
    """SQL验证器：用于在 SQL 执行前进行最后一道安全检查，防止危险操作和 SQL 注入。"""

    def __init__(self):
        self.dangerous_patterns = [
            r'\bDROP\b', r'\bDELETE\b', r'\bUPDATE\b', r'\bINSERT\b',
            r'\bREPLACE\b', r'\bTRUNCATE\b', r'\bALTER\b', r'\bCREATE\b',
            r'\bRENAME\b', r'\bEXEC\b', r'\bEXECUTE\b', r'\bCALL\b',
        ]
        self.injection_patterns = [
            r'--\s', r'#', r'/\*',
            r'\bOR\s+1=1\b', r'\bAND\s+1=1\b',
            r'\bOR\s+\d+=\d+\b', r'\bAND\s+\d+=\d+\b',
        ]

    def validate(self, sql: str) -> Dict[str, object]:
        """
        验证 SQL 语句是否安全。

        Returns:
            Dict: {"valid": bool, "errors": List[str]}
        """
        errors: List[str] = []

        if not sql or not sql.strip():
            return {"valid": False, "errors": ["SQL语句为空"]}
        normalized = sql.strip().rstrip(';').strip()

        # 1. 检查是否为 SELECT 语句
        if not normalized.upper().startswith('SELECT'):
            return {"valid": False, "errors": ["安全策略限制：只允许执行 SELECT 查询语句"]}

        # 2. 检查危险操作关键字
        for pattern in self.dangerous_patterns:
            match = re.search(pattern, normalized)
            if match:
                errors.append(f"包含危险操作关键字: {match.group(0)}")

        # 3. 检查 SQL 注入特征（使用原始大小写）
        for pattern in self.injection_patterns:
            match = re.search(pattern, normalized)
            if match:
                errors.append(f"包含SQL注入特征: {match.group(0)}")

        # 4. 检查多语句执行
        statements = [s.strip() for s in normalized.split(';') if s.strip()]
        if len(statements) > 1:
            return {"valid": False, "errors": ["安全策略限制：不允许多条SQL语句同时执行"]}

        # ：始终返回字典格式
        return {"valid": len(errors) == 0, "errors": errors}


# 创建全局单例
sql_validator = SqlValidator()