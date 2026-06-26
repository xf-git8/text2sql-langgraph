# 1.项目初始化，构建项目结构

    text2sql-langgraph/
    ├── app/
    │ ├── config/
    │ │ └── settings.py # 配置管理
    │ ├── core/ # 核心模块
    │ ├── services/ # 业务服务
    │ ├── agents/ # LangGraph智能体
    │ ├── api/ # API路由
    │ └── utils/ # 工具模块
    ├── db/ # 数据库脚本
    ├── .env # 环境变量
    └── requirements.txt # 依赖清单
    
  ## 功能实现顺序
  
    1.数据库连接管理模块
    2.LangGraph 基础工作流框架
        - SQL 生成服务
        - SQL 安全校验服务
        - RAG 表结构检索服务
    3.完整的 Agent 工作流
    4.身份认证模块
    5.API 接口层

# core模块配置
  ## init.py
  ## database.py
  
    - 数据库连接与重试机制（指数退避）
    - 获取表名列表
    - 获取单表结构信息
    - 获取所有表结构
    - SQL执行接口
    
# 3.先实基础现服务层
   ## SQL服务
   
    - SQL生成服务
    - SQL校验服务
        - 危险操作检测（DROP、DELETE、UPDATE、INSERT等）
        - SQL注入风险检测（OR 1=1、UNION等）
        - 多语句检测
        - 只允许SELECT查询
        
   ## QuestionAnalysis服务
   
        “问题理解”模块，利用 LLM 对用户输入进行意图识别和改写
        引入了Pydantic进行强类型约束，并优化了提示词逻辑
        增加了 reasoning 字段，让 LLM 输出分析思路，方便调试为什么它把某个问题归类为无效
        在 analyze 失败时，返回一个默认的 Pydantic 对象而不是裸字典，保证类型一致性
        
   ## RAG检索表结构服务 构建向量库 利用向量数据库根据用户问题检索相关的表结构，减少上下文长度并提高准确性
   
      - 使用 all-MiniLM-L6-v2 模型生成表结构向量
      - 使用 Chroma 构建本地向量数据库
      - 基于用户问题检索相关表结构
      - 将表结构格式化为 LLM 可理解的 Prompt
      - 支持重建向量库
      
# 4.实现LangGraph基本工作流程

  - 定义 Agent 状态（State）
  - 定义节点（Node）：检索表结构、生成SQL、执行SQL、总结回答
  - 定义边（Edge）：条件路由逻辑
  - 创建 Graph 实例
