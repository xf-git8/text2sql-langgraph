import re, logging
from typing import List, Tuple

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SqlValidator:
    """SQL验证器     用于在 SQL 执行前进行最后一道安全检查，防止危险操作和 SQL 注入。"""

    def __init__(self):
        # 危险操作关键字（只允许 SELECT）使用 \b 确保匹配完整单词，防止误伤（如字段名包含 'DROP' 的情况）
        self.dangerous_patterns = [
            r'\bDROP\b',
            r'\bDELETE\b',
            r'\bUPDATE\b',
            r'\bINSERT\b',
            r'\bREPLACE\b',
            r'\bTRUNCATE\b',
            r'\bALTER\b',
            r'\bCREATE\b',
            r'\bRENAME\b',
            r'\bEXEC\b',
            r'\bEXECUTE\b',
            r'\bCALL\b',
        ]

        # SQL 注入常见特征
        self.injection_patterns = [
            r'--\s',  # 注释符 --
            r'#',  # 注释符 #
            r'/\*',  # 注释符 /*
            r'\bOR\s+1=1\b',  # 永真条件
            r'\bAND\s+1=1\b',  # 永真条件
            r'\bOR\s+\d+=\d+\b',
            r'\bAND\s+\d+=\d+\b',
        ]

    def validate(self, sql: str) -> Tuple[bool, List[str]]:
        """验证 SQL 语句是否安全，并返回验证结果和错误信息列表
        Args:
             sql (str): 待验证的 SQL 语句
        Returns:
             Tuple[bool, List[str]]: 验证结果和错误信息列表
        """
        errors = []
    # 统一转为大写用于关键字匹配，但保留原始 sql 用于注入检测（区分大小写场景）
        sql_upper = sql
    # 检查是否为select语句
        if not sql_upper.startswith("SELECT"):
            errors.append("安全策略限制：只允许执行 SELECT 查询语句")
        # 2. 检查危险操作关键字
            for pattern in self.dangerous_patterns:
                if re.search(pattern, sql_upper):
                # 提取匹配到的关键字用于提示
                    match = re.search(pattern, sql_upper)
                    keyword = match.group(0) if match else pattern
                    errors.append(f"包含危险操作关键字: {keyword}")
        # 3. 检查 SQL 注入特征
            for pattern in self.injection_patterns:
                if re.search(pattern, sql):
                # 提取匹配到的关键字用于提示
                    match = re.search(pattern, sql)
                    keyword = match.group(0) if match else pattern
                    errors.append(f"包含 SQL 注入特征: {keyword}")
                # 4. 检查多语句执行 (防止 SELECT * FROM t; DROP TABLE t;)
                # 简单的分号检测，更严谨的做法是解析 SQL 语法树，但这里做轻量级拦截
                if ";" in sql.strip():
                # 去除结尾的分号后，如果中间还有分号，说明有多条语句
                # 或者 split 后长度大于 2 (因为最后一个可能是空字符串)
                    parts = [p.strip() for p in sql.strip().split(";") if p.strip()]
                    if len(parts) > 1:
                         errors.append("安全策略限制：不允许多条 SQL 语句同时执行")
# 创建全局单例
sql_validator = SqlValidator()
