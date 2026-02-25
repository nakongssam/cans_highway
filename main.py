import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="Hello Streamlit Cloud",
    page_icon="🚀",
    layout="centered",
)

st.title("🚀 Streamlit Community Cloud 배포 테스트")
st.caption("GitHub 업로드 → Streamlit Cloud에서 즉시 실행되는 최소 웹앱 템플릿")

st.write("현재 시각:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

st.divider()

name = st.text_input("이름을 입력하세요", placeholder="예: 한나")
if name:
    st.success(f"안녕하세요, {name}님! 🎉")

st.divider()

st.subheader("간단한 계산기")
a = st.number_input("A", value=10.0)
b = st.number_input("B", value=5.0)
op = st.selectbox("연산", ["+", "-", "×", "÷"])

result = None
if op == "+":
    result = a + b
elif op == "-":
    result = a - b
elif op == "×":
    result = a * b
else:
    result = "0으로 나눌 수 없어요" if b == 0 else a / b

st.info(f"결과: {result}")

st.divider()
st.caption("✅ 이 앱은 외부 API/파일/DB 없이 동작해서 Streamlit Cloud에서 오류 날 확률이 매우 낮습니다.")
