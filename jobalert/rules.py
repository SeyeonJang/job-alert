"""직무 / 고용형태 / 경력 판단에 쓰는 키워드.

알림이 너무 많거나 적으면 이 파일만 고치면 된다.
- 소문자로 비교하므로 영어는 소문자로 적는다.
- '확실히 포함'은 제외 키워드보다 먼저 본다 (예: Product Data Analyst).
"""

# ── 직무 ────────────────────────────────────────────────────────────
# 제목에 있으면 제외 키워드가 같이 있어도 보낸다.
ROLE_STRONG_INCLUDE = [
    "product manager", "product owner", "프로덕트 매니저", "프로덕트매니저",
    "프로덕트 오너", "프로덕트오너", "서비스 기획", "서비스기획",
    "데이터 분석", "데이터분석", "data analyst", "data analysis",
    "business analyst", "product analyst", "data scientist",
    "데이터 사이언티스트", "데이터사이언티스트", "problem solver",
    "사업 기획", "사업기획", "전략 기획", "전략기획",
]

# 제목에 있으면 관련 직무로 본다.
ROLE_INCLUDE = [
    "기획자", "플랫폼 기획", "정책 기획", "프로덕트 기획", "제품 기획",
    "program manager", "프로그램 매니저", "product lead", "product operations",
    "operations manager", "오퍼레이션", "bizops", "business operations",
    "strategy", "strategist", "전략", "chief of staff", "staff",
    "analytics", "애널리틱스", "bi ", "인사이트", "insight",
    "growth manager", "그로스 매니저", "pmo",
]
# 제목에 대문자 PM / PO 가 단어로 있으면 관련 직무로 본다.
ROLE_INCLUDE_ACRONYMS = ["PM", "PO", "TPM", "BA"]

# 사이트가 주는 직군·직무·키워드 값에 있으면 관련 직무로 본다.
CATEGORY_INCLUDE = [
    "product management", "프로덕트 매니지먼트", "프로덕트", "product",
    "data", "데이터", "business analysis", "전략", "strategy",
    "service & business", "서비스 기획", "pm", "기획",
]

# 제목에 있으면 제외한다.
ROLE_EXCLUDE = [
    # 개발·엔지니어링
    "engineer", "엔지니어", "개발자", "developer", "programmer", "프로그래머",
    "devops", "dba", "sre", "qa ", "백엔드", "프론트엔드", "backend", "frontend",
    "ios", "android", "안드로이드", "machine learning", "머신러닝",
    "게임 엔진", "클라이언트 개발", "서버 개발", "앱 개발", "웹 개발",
    # 디자인·콘텐츠 제작
    "designer", "디자이너", "디자인 그룹", "design lead", "illustrator", "일러스트",
    "animator", "애니메이터", "photographer", "포토그래퍼", "retoucher", "리터처",
    "에디터", "editor", "조연출", "영상 제작", "video", "스타일리스트",
    # MD·영업·마케팅
    " md", "md ", "md(", "머천다이저", "바이어", "buyer", "vmd",
    "영업", "sales", "세일즈", "account manager", "어카운트",
    "마케터", "marketer", "마케팅", "marketing",
    # 경영지원
    "hrbp", "hr ", "인사", "채용", "recruit", "talent", "people",
    "재무", "회계", "세무", "자금", "finance", "fp&a", "accounting", "tax",
    "treasury", "settlement", "정산", "ir ", "ir/", "공시",
    "법무", "변호사", "legal", "compliance", "컴플라이언스",
    "보안", "security", "개인정보", "privacy",
    "총무", "workplace", "구매", "procurement", "비서", "통번역",
    "interpreter", "translator", "localization", "현지화",
    # 현장·운영
    "물류", "입출고", "배송", "센터", "fc ", "fc운영", "scm", "s&op",
    "풀필먼트", "fulfillment", "logistics", "상담", "고객경험지원",
    "판매사원", "매장", "생산", "설비", "포장", "공정", "보건관리자",
    "안전관리자", "ehs", "연구원", "연구팀", "소싱",
    # 상시 인재풀
    "인재풀", "인재 pool", "인재pool", "talent pool", "사외 추천",
]

# 사이트가 주는 직군·직무 값에 있으면 제외한다 (제목으로 판단이 안 될 때만).
CATEGORY_EXCLUDE = [
    "software development", "개발", "engineering", "인프라", "devops",
    "design", "디자인", "md", "영업", "sales", "marketing", "마케팅",
    "finance", "인사", "hrm", "human resources", "talent acquisition",
    "법무", "legal", "보안", "security", "compliance", "고객서비스", "cx",
    "fc운영", "fc기획", "ehs", "scm", "photographer", "editor",
    "production management", "video production", "general affair",
    "content design", "fashion design", "package design", "tech",
]

# ── 고용형태 ────────────────────────────────────────────────────────
INTERN_WORDS = ["인턴", "intern", "체험형", "채용연계형", "채용 연계형"]
CONTRACT_WORDS = [
    "계약", "파견", "프리랜서", "freelance", "위촉", "기간제", "단기",
    "대체인력", "대체 인력", "육아휴직 대체", "현장실습", "contract", "임원",
]

# ── 경력 ────────────────────────────────────────────────────────────
MAX_YEARS = 1   # 자격요건 연차가 이 값 이하면 보낸다

# 상세 본문에서 '자격요건'으로 보는 소제목
REQUIREMENT_HEADINGS = [
    "자격요건", "자격 요건", "지원자격", "지원 자격", "필수 요건", "필수요건",
    "필수 자격", "필수 조건", "자격 조건", "자격조건", "지원 조건", "모집 대상",
    "이런 분을 찾고 있어요", "이런 분을 찾아요", "이런 분을 찾습니다",
    "이런 분과 함께", "이런 분이 필요해요", "이런 경험이 필요해요",
    "찾고 있는 분", "requirements", "qualifications", "minimum qualifications",
    "who you are", "what we look for", "필요 역량", "필요역량", "지원 요건",
    "이런 분이면 좋아요", "이런 분을 기다려요", "함께하고 싶은 분",
]
# '우대사항' 등 연차를 무시할 소제목
PREFERRED_HEADINGS = [
    "우대", "더 좋아요", "더 좋습니다", "더욱 좋", "preferred", "nice to have",
    "bonus", "plus", "가산점",
]
# 자격요건 구역이 끝나는 소제목
OTHER_HEADINGS = [
    "담당업무", "담당 업무", "주요업무", "주요 업무", "이런 일을 해요",
    "이런 일을 합니다", "합류하면", "혜택", "복지", "근무 조건", "근무조건",
    "근무지", "전형", "채용 절차", "채용절차", "지원 방법", "참고", "유의사항",
    "팀 소개", "팀을 소개", "회사 소개", "합류 여정", "프로세스", "benefits",
    "responsibilities", "what you'll do", "about", "기타", "제출",
]
