import streamlit as st
import google.generativeai as genai
from PIL import Image

# 1. 페이지 설정
st.set_page_config(
    page_title="고속도로 시설물 점검 AI",
    page_icon="🚧",
    layout="wide"
)

# 2. API 키 및 모델 설정
if "GEMINI_API_KEY" in st.secrets:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        
        # 404 에러 방지를 위해 가장 표준적인 모델 명칭 사용
        # 만약 'gemini-1.5-flash'가 안되면 'models/gemini-1.5-flash'로 시도됨
        model_name = 'gemini-1.5-flash' 
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        st.error(f"모델 초기화 중 오류가 발생했습니다: {e}")
        st.stop()
else:
    st.error("❌ Streamlit Cloud의 Secrets에 'GEMINI_API_KEY'를 설정해 주세요.")
    st.stop()

# 3. UI 구성
st.title("🚧 고속도로 시설물 유지관리 AI 점검 시스템")
st.info("비공개 API 키를 통해 보안 연결이 활성화되었습니다.")

# 파일 업로더
uploaded_file = st.file_uploader("시설물 점검 사진을 업로드하세요 (JPG, PNG)", type=["jpg", "png", "jpeg"])

# 사용자가 정의한 전문 프롬프트
SYSTEM_PROMPT = """
너는 고속도로 운영기관의 시설물 유지관리 담당 기술자다.
입력되는 시설물 점검 사진 1장을 바탕으로 현장 점검 보고서 초안을 작성한다.

[작성 절차]
1. 외관 상태 관찰 (손상, 변형, 오염, 파손 등)
2. 손상 유형 판정 (균열, 박리, 부식, 침하, 탈락 등)
3. 위험도 평가 (낮음/중간/높음) 및 근거 제시
4. 긴급 조치 및 단계별 보수 권고안 작성
5. 추가 점검 항목 체크리스트 작성

보고서 형식:
[1. 점검 개요]
[2. 관찰 내용 (사진 기반)]
[3. 손상/이상 유형 판정 (가능성 포함)]
[4. 위험도 평가 (낮음/중간/높음) 및 근거]
[5. 즉시 조치 권고 (필요 시)]
[6. 보수/정비 권고안 (단계별)]
[7. 추가 점검/확인 항목 (체크리스트)]
[8. 참고/주의 (면책 문구)]
"""

if uploaded_file:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.image(image, caption="현장 점검 사진", use_container_width=True)
    
    with col2:
        if st.button("AI 보고서 생성", type="primary"):
            try:
                with st.spinner("이미지를 분석하여 전문 보고서를 작성 중입니다..."):
                    # API 호출
                    response = model.generate_content([SYSTEM_PROMPT, image])
                    
                    st.subheader("📋 분석 결과")
                    st.markdown(response.text)
                    
                    st.download_button(
                        label="📄 보고서 저장",
                        data=response.text,
                        file_name="highway_report.txt",
                        mime="text/plain"
                    )
            except Exception as e:
                # 에러 메시지별 맞춤 안내
                error_msg = str(e)
                if "429" in error_msg:
                    st.error("🚀 사용량 초과! 1분만 기다렸다가 다시 시도해 주세요.")
                elif "404" in error_msg:
                    st.error("🔍 모델을 찾을 수 없습니다. API 키가 활성화되었는지 확인해 주세요.")
                else:
                    st.error(f"오류 발생: {e}")
