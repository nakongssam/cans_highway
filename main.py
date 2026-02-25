import streamlit as st
from openai import OpenAI
import base64

# 페이지 설정
st.set_page_config(page_title="AI 신년사 생성기", page_icon="🧧")

# 스타일링
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #ff4b4b;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# OpenAI 클라이언트 초기화 (Streamlit Secrets 활용)
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def encode_image(image_file):
    """이미지 파일을 base64로 인코딩합니다."""
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

def generate_new_year_message(image_base64, tone, recipient):
    """이미지를 분석하고 신년사를 생성합니다."""
    prompt = f"""
    당신은 따뜻하고 지혜로운 문장가입니다. 
    첨부된 이미지를 분석하고, 이 이미지의 분위기나 상징물(예: 일출, 가족, 풍경 등)을 활용하여 
    '{recipient}'에게 보낼 '{tone}' 어조의 신년 축하 메시지를 작성해주세요.
    
    조건:
    1. 이미지에 나타난 구체적인 요소(색감, 사물, 느낌)를 문장에 자연스럽게 녹여낼 것.
    2. 너무 뻔하지 않고 진심이 느껴지는 감성적인 문장으로 작성할 것.
    3. 한국어로 작성할 것.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    },
                ],
            }
        ],
        max_tokens=800
    )
    return response.choices[0].message.content

# UI 구성
st.title("🧧 AI 이미지 맞춤 신년사 생성기")
st.write("이미지를 업로드하면 AI가 분석하여 세상에 하나뿐인 신년사를 써드립니다.")

with st.sidebar:
    st.header("설정")
    recipient = st.text_input("받는 분", placeholder="예: 부모님, 직장 상사, 친구 등")
    tone = st.selectbox("문체 선택", ["다정한", "격식 있는", "유머러스한", "감성적인", "희망찬"])
    
uploaded_file = st.file_uploader("신년 분위기가 담긴 이미지를 업로드하세요", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    st.image(uploaded_file, caption='업로드된 이미지', use_column_width=True)
    
    if st.button("AI 신년사 생성하기"):
        if not recipient:
            st.warning("받는 분을 입력해주세요!")
        else:
            with st.spinner("이미지를 분석하고 문장을 다듬는 중입니다..."):
                try:
                    base64_image = encode_image(uploaded_file)
                    result = generate_new_year_message(base64_image, tone, recipient)
                    
                    st.success("신년사가 완성되었습니다!")
                    st.markdown("---")
                    st.subheader(f"💌 {recipient}님께 전하는 메시지")
                    st.write(result)
                    st.markdown("---")
                    st.button("다시 작성하기")
                except Exception as e:
                    st.error(f"오류가 발생했습니다: {e}")

else:
    st.info("왼쪽 사이드바에서 정보를 입력하고 이미지를 업로드해주세요.")
