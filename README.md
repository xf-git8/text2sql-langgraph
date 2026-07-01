
# 1.项目初始化，构建项目结构

 ## 初始结构 text2sql-langgraph/
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
    - 数据库连接管理模块
    - LangGraph 基础工作流框架
        - SQL 生成服务
        - SQL 安全校验服务
        - Question 问题理解服务
        - RAG 表结构检索服务
        - Result 结果格式化服务
    - 完整的 Agent 工作流
    - 身份认证模块
    - API 接口层   
    阶段性结构： 实现api接口路由层和服务层的优化拆分  
    服务层：执行业务逻辑，供路由层调用
    路由层：定义HTTP接口，调用服务层,返回结果
    text2sql-langgraph/  
    ├── app/
    │   ├── __init__.py
    │   ├── main.py                    # FastAPI主入口
    │   ├── config/
    │   │   └── settings.py            # 配置管理
    │   ├── core/
    │   │   ├── __init__.py
    │   │   └── database.py            # 数据库连接管理
    │   ├── services/
    │   │   ├── __init__.py
    │   │   ├── sql_generator.py       # SQL生成服务
    │   │   ├── sql_validator.py       # SQL安全校验
    │   │   ├── rag_retrieval.py       # RAG表结构检索
    │   │   ├── question_processor.py  # 问题意图识别与改写
    │   │   └── result_formatter.py    # 结果格式化
    │   │  
    │   ├── agents/
    │   │   ├── __init__.py
    │   │   └── text2sql_agent.py      # LangGraph工作流
    │   └── api/ 
    │        ├── __init__.py          # 只负责汇总导出 router
    │        ├── routes/              # 新建 routes 文件夹
    │          ├── __init__.py      # 空文件
    │          ├── auth.py          # 认证路由
    │          └── query.py        # 查询路由
    │                     
    │              
    ├── db/
    │   ├── init.sql                   # 数据库初始化
    │   └── test_data.sql              # 测试数据
    ├── .env                           # 环境变量
    ├── requirements.txt               # 依赖清单
    └──run.py                         # 启动脚本(暂时和main放在一起)
    - webui界面
    - 测试与部署
    - 项目维护与更新
    
# 2.core模块配置init.py
  -database.py
    - 数据库连接与重试机制（指数退避）
    - 获取表名列表
    - 获取单表结构信息
    - 获取所有表结构
    - SQL执行接口
    
# 3.先实基础现服务层

  ## -SQL服务：
    - SQL生成服务
    - SQL校验服务
        - 危险操作检测（DROP、DELETE、UPDATE、INSERT等）
        - SQL注入风险检测（OR 1=1、UNION等）
        - 多语句检测
        - 只允许SELECT查询
        
  ## -QuestionAnalysis分析处理
        “问题理解”模块，利用 LLM 对用户输入进行意图识别和改写
        引入了Pydantic进行强类型约束，并优化了提示词逻辑
        增加了 reasoning 字段，让 LLM 输出分析思路，方便调试为什么它把某个问题归类为无效
        在 analyze 失败时，返回一个默认的 Pydantic 对象而不是裸字典，保证类型一致性
        
  ## -RAG检索表结构服务 构建向量库 
        利用向量数据库根据用户问题检索相关的表结构，减少上下文长度并提高准确性
      - 使用 BGE- 模型生成表结构向量
      - 使用 Chroma 构建本地向量数据库(检索之前进行问题分析改写)
      - 基于用户问题检索相关表结构
      - 将表结构格式化为 LLM 可理解的 Prompt
      - 支持重建向量库
      
  ## -Result结果格式化服务
      - 使用 LLM 将SQL执行结果转换为自然语言回答
      - 处理空结果、单行结果和多行结果
      - 结果长度限制防止超出模型上下文
      - 降级方案：简单格式化作为兜底
      
# 4.实现LangGraph基本工作流程
    工作流中的“短路机制”： 
    通过在每个节点内部统一加入 if state["intention"] == "invalid": return state 的前置检查，
    配合 should_retry 中的条件判断，系统能够极其高效地拦截无效请求。 对于无效问题，系统完全不会去调用昂贵的 LLM 生成 SQL 或访问数据库， 从而极大地节省了计算资源和响应时间。
    AgentState 状态定义（包含问题、表结构、SQL、结果等） 
    6个节点：process_question、generate_sql、validate_sql、execute_sql、retry_correction、summarize
    条件路由：执行失败时自动重试修正（最多max_retries次）
    工作流流程：用户问题 → 问题意图识别和改写RAG表结构检索 → SQL生成校验执行 → 结果格式化 → 返回回答
                                                         ↓
                                                  [执行失败] → SQL修正 → 重试校验与执行

# 5.实现身份认证模块添加权限
   OAuth2 Password Bearer + JWT Refresh Token Rotation 认证体系。
   整个流程分为“首次登录”、“资源访问”和“无感刷新”三个核心阶段。生产环境引入redis缓存，提升性能。
   
# 6.实现API接口层路

  ## -用户认证接口
  ## -LangGraph工作流查询接口

  ## 已查询接口为例数据流程
  客户端请求
    │
    │  POST /query  { question: "查询订单数量", token: "xxx" }
    │
    ▼
  ┌─────────────────────────────────────────────┐
  │  app/main.py                                │
  │  app.include_router(api_router)             │  ← 注册总路由
  └──────────────────┬──────────────────────────┘
                     │
                     ▼
  ┌─────────────────────────────────────────────┐
  │  app/api/__init__.py                        │
  │  router.include_router(query_router)        │  ← 汇总注册
  └──────────────────┬──────────────────────────┘
                     │
                     ▼
  ┌─────────────────────────────────────────────┐
  │  app/api/routes/query.py       【路由层】     │
  │                                             │
  │  1. 接收请求体 → QueryRequest                 │
  │  2. Depends(get_current_user) → 校验Token    │  ← 认证拦截
  │  3. 调用 query_service.execute_query()       │  ← 调用服务层
  │  4. 返回 QueryResponse                       │
  └──────────┬──────────────────┬───────────────┘
             │                  │
             ▼                  ▼
  ┌──────────────────┐  ┌─────────────────────────┐
  │  app/auth.py     │  │  app/api/query.py       │
  │  【认证服务层】     │  │  【查询服务层】           │
  │                  │  │                         │
  │  解析Token        │  │  组装inputs              │
  │  校验用户          │  │  调用text2sql_graph      │
  │  返回user dict    │  │  返回result dict         │
  └──────────────────┘  └───────────┬──────────────┘
                                    │
                                    ▼
                      ┌─────────────────────────┐
                      │  text2sql_graph.invoke()│
                      │  【LangGraph Agent】     │
                      │  意图识别 → RAG检索        │
                      │  → SQL生成 → 校验         │
                      │  → 执行 → 返回答案         │
                      └─────────────────────────┘

<img width="1869" height="437" alt="image" src="https://github.com/user-attachments/assets/6cd2d077-b4e8-48e2-a628-9335d5c4394f" />


<img width="1868" height="868" alt="image" src="https://github.com/user-attachments/assets/762a5909-2f5b-420d-bbbb-7b5a936e4e32" />

  
