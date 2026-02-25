import os
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="GPT API Streamlit", page_icon="🤖", layout="centered")

st.title("🤖 GPT API 호출 웹앱 (Streamlit Cloud)")
st.caption("Secrets에 OPENAI_API_KEY를 넣으면 바로 동작합니다.")

# --- API Key 로드 (Cloud: st.secrets / Local: 환경변수) ---
api_key = None
try:
    api_key = st.secrets.get("OPENAI_API_KEY", None)
except Exception:
    api_key = None

if not api_key:
    api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    st.error("OPENAI_API_KEY가 없습니다. Streamlit Cloud > App settings > Secrets에 등록하세요.")
    st.stop()

client = OpenAI(api_key=api_key)

# --- UI ---
model = st.selectbox("모델", ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1"], index=0)
system_prompt = st.text_area(
    "System prompt (선택)",
    value="You are a helpful assistant.",
    height=80,
)
user_prompt = st.text_area("User prompt", placeholder="질문을 입력하세요...", height=160)

col1, col2 = st.columns([1, 1])
with col1:
    temperature = st.slider("temperature", 0.0, 1.0, 0.3, 0.1)
with col2:
    max_tokens = st.slider("max_tokens", 64, 2048, 512, 64)

if st.button("🚀 보내기", type="primary", use_container_width=True):
    if not user_prompt.strip():
        st.warning("User prompt를 입력하세요.")
        st.stop()

    with st.spinner("GPT가 답변 생성 중..."):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt.strip()},
                    {"role": "user", "content": user_prompt.strip()},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            answer = resp.choices[0].message.content or ""
        except Exception as e:
            st.exception(e)
            st.stop()

    st.subheader("✅ 응답")
    st.write(answer)

    # 선택: 간단한 사용량 표시(응답에 usage가 없을 수도 있어서 안전하게 처리)
    usage = getattr(resp, "usage", None)
    if usage:
        st.caption(
            f"tokens — prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens}, total: {usage.total_tokens}"
        )

st.divider()
st.markdown(
    """
### 🔐 Streamlit Secrets 설정
Streamlit Community Cloud에서 **App settings → Secrets**에 아래처럼 추가:

```toml
OPENAI_API_KEY = "sk-..."
