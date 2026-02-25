import os
import streamlit as st
from openai import OpenAI

# -----------------------------
# 페이지 설정
# -----------------------------
st.set_page_config(
    page_title="AI 업무지원 웹앱",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 생성형 AI 업무지원 웹앱")
st.caption("GPT API를 활용한 문서 자동 생성 도구")

st.divider()

# -----------------------------
# API KEY 불러오기
# -----------------------------
api_key = None

# Streamlit Cloud Secrets
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except:
    pass

# 로컬 환경 변수
if not api_key:
    api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    st.error("OPENAI_API_KEY가 없습니다. Streamlit Cloud Secrets에 등록하세요.")
    st.stop()

client = OpenAI(api_key=api_key)

# -----------------------------
# 입력 UI
# -----------------------------
st.subheader("업무 내용 입력")

system_prompt = st.text_area(
    "System Prompt",
    value="You are a helpful assistant that helps generate official reports.",
    height=80
)

user_prompt = st.text_area(
    "User Prompt",
    placeholder="예: 오늘 실시한 시설물 점검 내용을 보고서 형식으로 작성해줘.",
    height=150
)

temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1)
max_tokens = st.slider("Max Tokens", 100, 2000, 500, 100)

# -----------------------------
# GPT 호출
# -----------------------------
if st.button("🚀 문서 생성하기", use_container_width=True):

    if not user_prompt.strip():
        st.warning("내용을 입력하세요.")
        st.stop()

    with st.spinner("AI가 문서를 생성 중입니다..."):

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt.strip()},
                    {"role": "user", "content": user_prompt.strip()}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )

            answer = response.choices[0].message.content

        except Exception as e:
            st.error("API 호출 중 오류 발생")
            st.exception(e)
            st.stop()

    st.subheader("📄 생성 결과")
    st.write(answer)

    usage = getattr(response, "usage", None)
    if usage:
        st.caption(
            f"Prompt: {usage.prompt_tokens} | Completion: {usage.completion_tokens} | Total: {usage.total_tokens}"
        )

st.divider()
st.info("App Settings → Secrets → OPENAI_API_KEY 입력 필요")
