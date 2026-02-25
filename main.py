import streamlit as st
import google.generativeai as genai
from PIL import Image

# 1. 페이지 설정
st.set_page_config(page_title="고속도로 시설물 점검 AI", page_icon="🚧", layout="wide")

# 2. API 키 및 모델 설정 (오류 방지 로직 포함)
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    
    # 404 에러 방지: 사용할 수 있는 모델 리스트 확인 후 자동 선택
    try:
        # 가장 안정적인 1.5 Flash 모델 설정
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"모델 초기화 중 오류가 발생했습니다: {e}")
        st.stop()
else:
    st.error("❌ Streamlit Secrets에 'GEMINI_API_KEY'를 설정해 주세요.")
    st.stop()

# 3. 앱 제목 및 설명
st.title("🚧 고속도로 시설물 유지관리 AI 점검 시스템")
st.info("비공개 API 키를 통해 보안 연결이 활성화되었습니다.")

# 4. 파일 업로더
uploaded_file = st.file_uploader("시설물 점검 사진을 업로드하세요 (JPG, PNG)", type=["jpg", "png", "jpeg"])

# 5. 시설물 기술자 프롬프트 (전달해주신 내용 반영)
SYSTEM_PROMPT = """
너는 고속도로 운영기관의 시설물 유지관리 담당 기술자다.
입력되는 시설물 점검 사진 1장을 바탕으로 현장 점검 보고서 초안을 작성하는 업무를 수행한다.

다음의 절차에 따라 분석을 수행할 것:
1. 사진에 나타난 시설물의 외관 상태를 관찰하여 손상, 변형, 오염, 파손 등의 이상 여부를 식별한다.
2. 식별된 이상 현상이 있을 경우, 해당 손상의 유형을 기술적으로 판정한다. (예: 균열, 박리, 부식, 침하, 탈락 등)
3. 해당 이상이 시설물의 기능 또는 안전성에 미칠 수 있는 잠재적 영향을 고려하여 위험도를 다음 중 하나로 평가한다. (낮음 / 중간 / 높음)
4. 긴급한 안전 위험이 예상되는 경우에만 즉시 조치 필요 사항을 제시한다.
5. 중장기 유지관리를 위한 단계별 보수 및 정비 권고안을 작성한다.
6. 사진만으로 판단이 어려운 경우, 추가 점검이 필요한 항목을 체크리스트 형태로 제시한다.

[작성 원칙]
- 사진에 기반하지 않은 정보는 임의로 생성하지 말 것
- 확정이 어려운 내용은 '현장 확인 필요'로 명시할 것
- 과장된 표현 또는 추정성 판단을 단정적으로 서술하지 말 것
- 기술 보고서 문체를 유지할 것

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

# 6. 실행 로직
if uploaded_file:
    image = Image.open(uploaded_file)
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.image(image, caption="업로드된 점검 사진", use_container_width=True)
    
    with col2:
        if st.button("AI 보고서 생성", type="primary"):
            try:
                with st.spinner("AI 기술자가 이미지를 정밀 분석 중입니다..."):
                    # API 호출
                    response = model.generate_content([SYSTEM_PROMPT, image])
                    
                    st.subheader("📋 분석 결과")
                    st.markdown(response.text)
                    
                    # 텍스트 파일 다운로드 버튼
                    st.download_button(
                        label="📄 보고서 텍스트 다운로드",
                        data=response.text,
                        file_name="highway_inspection_report.txt",
                        mime="text/plain"
                    )
            except Exception as e:
                error_str = str(e)
                if "429" in error_str:
                    st.error("🚀 현재 무료 사용량이 초과되었습니다. 1분만 기다렸다가 다시 시도해 주세요!")
                elif "404" in error_str:
                    st.error("🔍 모델 이름을 찾을 수 없습니다. 구글 API 서버의 일시적 오류일 수 있습니다.")
                else:
                    st.error(f"오류가 발생했습니다: {e}")
