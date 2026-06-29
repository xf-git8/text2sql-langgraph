import streamlit as st
import requests, json

# ==================== 页面基础配置 ====================
st.set_page_config(page_title="Text2SQL 查询", layout="wide")
API_BASE = "http://127.0.0.1:8000/api/v1"

# ==================== Session State 初始化 ====================
if "token" not in st.session_state:
    st.session_state.token = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "tables" not in st.session_state:
    st.session_state.tables = []


# ==================== 通用请求头 ====================
def get_headers():
    headers = {"Content-Type": "application/json"}
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    return headers


# ==================== 获取表结构 ====================
def fetch_tables():
    try:
        res = requests.post(
            f"{API_BASE}/login",
            json={"username": username, "password": password},
            timeout=10,
            proxies={"http": None, "https": None}
        )
        if res.status_code == 200:
            data = res.json()
            if isinstance(data.get("tables"), list):
                st.session_state.tables = data["tables"]
        elif res.status_code == 401:
            st.session_state.token = None
            st.rerun()
    except Exception as e:
        st.sidebar.warning(f"⚠️ 获取表结构失败: {e}")


# ==================== 🔐 登录界面 ====================
if not st.session_state.token:
    st.title("🔑 Text2SQL 登录")

    with st.form("login_form"):
        username = st.text_input("用户名", placeholder="admin")
        password = st.text_input("密码", type="password", placeholder="123456")
        submitted = st.form_submit_button("登 录", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("❌ 用户名和密码不能为空")
            else:
                try:
                    # ⚠️ 注意：FastAPI OAuth2PasswordRequestForm 要求 x-www-form-urlencoded
                    res = requests.post(
                        f"{API_BASE}/login",
                        json={
                            "username": username,  # str 类型
                            "password": password  # str 类型
                        },
                        proxies={"http": None, "https": None},
                        timeout=10
                    )

                    if res.status_code == 200:
                        data = res.json()
                        token = data.get("access_token")
                        if token:
                            st.session_state.token = token
                            fetch_tables()
                            st.success("✅ 登录成功！正在跳转...")
                            st.rerun()
                        else:
                            st.error("❌ 登录成功但未返回有效 Token")
                    else:
                        err = res.json().get("detail", f"HTTP {res.status_code}")
                        st.error(f"❌ {err}")

                except Exception as e:
                    st.error(f"❌ 请求异常: {e}")
    st.stop()  # 🔑 关键：未登录时阻止渲染后续内容

# ==================== 💬 主界面（登录后） ====================
# 左侧边栏：表结构 + 退出
with st.sidebar:
    st.header(f"📊 SCHEMA 向量库 ({len(st.session_state.tables)})")
    if st.session_state.tables:
        for table in st.session_state.tables:
            if st.button(table, key=f"tbl_{table}", use_container_width=True):
                # 点击表名自动填入查询框（通过 session_state 传递）
                st.session_state.prefill_question = f"查询 {table} 表的前10条数据"
                st.rerun()
    else:
        st.caption("暂无表信息")

    st.divider()
    if st.button("🚪 退出登录", use_container_width=True):
        st.session_state.token = None
        st.session_state.messages = []
        st.session_state.tables = []
        st.rerun()

# 右侧：聊天区域
st.title("💬 Text2SQL 智能查询")

# 渲染历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入框（支持预填充）
default_q = st.session_state.pop("prefill_question", "")
if prompt := st.chat_input("请输入自然语言查询问题...", ):
    # 1. 显示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. 调用后端并显示 AI 回复
    with st.chat_message("assistant"):
        with st.spinner("😕 正在分析并生成 SQL..."):
            try:
                res = requests.post(
                    f"{API_BASE}/query",  # 或者是你的其他接口地址
                    json={"question": prompt},
                    headers={"Authorization": f"Bearer {st.session_state.token}"},
                    timeout=30,
                    # ✅ 这里也要加上，防止查询时也走代理报错
                    proxies={"http": None, "https": None}
                )
                try:
                    response_data = res.json()
                    st.write("🔍 完整返回数据：", json.dumps(response_data, ensure_ascii=False, indent=2))
                except:
                    st.write("🔍 原始返回文本：", res.text)

                if res.status_code == 401:
                    st.session_state.token = None
                    st.error("❌ 认证已过期，请重新登录")
                    st.rerun()
                elif res.status_code == 200:
                    data = res.json()
                    answer = data.get("answer", "(无回答内容)")
                    # 更新侧边栏表列表
                    new_tables = data.get("tables", [])
                    if new_tables:
                        st.session_state.tables = list(set(st.session_state.tables + new_tables))
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    err = res.json().get("detail", f"HTTP {res.status_code}")
                    error_msg = f"❌ {err}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

            except Exception as e:
                error_msg = f"❌ 请求异常: {e}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
