# 분석 템플릿 가이드

이 문서는 ClickUp Issue Analysis Bot에서 사용하는 분석 템플릿의 구조와 사용법을 설명합니다.

---

## 📋 목차

1. [템플릿이란?](#템플릿이란)
2. [템플릿 구조](#템플릿 구조)
3. [사용 가능한 템플릿](#사용-가능한-템플릿)
4. [템플릿 사용법](#템플릿-사용법)
5. [커스텀 템플릿 추가](#커스텀-템플릿-추가)

---

## 템플릿이란?

템플릿은 **Claude AI에게 전달되는 분석 지시사항의 틀**입니다.

### 동작 원리

```
ClickUp Task → fetch.py → task.json 저장
                           ↓
                    analyze.py가 실행
                           ↓
            prompts.json에서 템플릿 로드
                           ↓
            템플릿에 실제 데이터 삽입 (rendering)
                           ↓
            Claude AI에게 전달 → 분석 실행
                           ↓
                    report.md 생성
```

### 템플릿의 역할

| 구분 | 설명 |
|------|------|
| **입력** | ClickUp 태스크 정보 (제목, 설명, 이미지, 댓글, 버전) |
| **처리** | 템플릿에 정의된 변수 위치에 실제 데이터 삽입 |
| **출력** | Claude가 분석할 완성된 프롬프트 |

---

## 템플릿 구조

### 파일 위치
```
jar-decompiler/prompts.json
```

### JSON 구조

```json
{
  "템플릿_ID": {
    "name": "템플릿 이름",
    "description": "템플릿 설명",
    "template": "실제 프롬프트 내용..."
  }
}
```

### 템플릿 변수 (Placeholders)

템플릿 안에서 `{변수명}` 형식으로 사용되며, 실행 시 실제 값으로 대체됩니다.

| 변수 | 설명 | 예시 |
|------|------|------|
| `{title}` | 태스크 제목 | "JSPD 메모리 누수 현상" |
| `{description}` | 태스크 설명 | "5.4.11 버전에서 메모리가 계속 증가합니다..." |
| `{images}` | 첨부 이미지 목록 | "- tasks/IMX-9326/images/image_0.png" |
| `{comments}` | 댓글 내역 | "[2025-01-15] 홍길동: 추가 로그입니다..." |
| `{versions}` | 버전 정보 | "- Product: 5.4.11.1\n- Agent Version: 5.4.11" |
| `{version_paths}` | 디컴파일된 소스 경로 | "- packages/v5.4.11.1/decompiled/" |

---

## 사용 가능한 템플릿

### 1. `issue_analysis` - 이슈 분석

**언제 사용?**
- 버그 리포트 분석
- 에러/예외 상황 조사
- 성능 문제 분석
- 고객 불만 사항 조사

**출력 형식:**
```markdown
### 버전 정보
### 이슈 요약
### 재현 단계 (사용자/엔지니어 관점)
### 근본 원인 분석
### 해결 방안 제안
```

**사용 예시:**
```powershell
python analyze.py --task-id IMX-9326 --template issue_analysis
```

---

### 2. `spec_inquiry` - 사양 문의

**언제 사용?**
- 특정 기능의 동작 방식 확인
- 설정 가능 여부 조사
- 제약 사항 확인
- 문서화되지 않은 기능 확인

**출력 형식:**
```markdown
### 버전 정보
### 문의 내용 요약
### 사양 확인 결과
### 확인 방법 (사용자/엔지니어 관점)
```

**사용 예시:**
```powershell
python analyze.py --task-id IMX-8521 --template spec_inquiry
```

---

### 3. `improvement_request` - 개선 요청

**언제 사용?**
- 신규 기능 추가 요청 분석
- 기존 기능 개선 제안 검토
- 기술적 실현 가능성 평가
- 개발 복잡도 추정

**출력 형식:**
```markdown
### 버전 정보
### 요청 내용 요약
### 관련 기능 확인
### 구현 제안
```

**사용 예시:**
```powershell
python analyze.py --task-id IMX-7412 --template improvement_request
```

---

## 템플릿 사용법

### 기본 워크플로우

```powershell
# 1. 태스크 다운로드
python fetch.py --task-id IMX-9326

# 2. 템플릿 선택하여 분석
python analyze.py --task-id IMX-9326 --template issue_analysis

# 3. 생성된 프롬프트 확인 (디버깅용)
cat tasks\IMX-9326\prompt.txt

# 4. 분석 결과 확인
cat tasks\IMX-9326\report.md

# 5. ClickUp에 업로드 (선택사항)
python upload.py --task-id IMX-9326
```

### 템플릿 선택 가이드

| 태스크 유형 | 추천 템플릿 |
|-------------|------------|
| "~가 안 됩니다", "에러 발생" | `issue_analysis` |
| "~를 설정할 수 있나요?", "~는 어떻게 동작하나요?" | `spec_inquiry` |
| "~기능을 추가해주세요", "~를 개선해주세요" | `improvement_request` |

---

## 커스텀 템플릿 추가

### 1. prompts.json 편집

```json
{
  "custom_template": {
    "name": "커스텀 분석",
    "description": "특정 목적을 위한 커스텀 템플릿",
    "template": "당신은 InterMax 전문가입니다.\n\n## 태스크 정보\n제목: {title}\n\n{description}\n\n... 원하는 형식 추가 ..."
  }
}
```

### 2. analyze.py 수정 (템플릿 선택지 추가)

`analyze.py` 파일의 214-219줄 수정:

```python
parser.add_argument(
    "--template",
    choices=["issue_analysis", "spec_inquiry", "improvement_request", "custom_template"],  # ← 추가
    default="issue_analysis",
    help="Analysis template to use"
)
```

### 3. 사용

```powershell
python analyze.py --task-id IMX-9999 --template custom_template
```

---

## 템플릿 렌더링 과정

### 내부 동작 (`analyze.py:render_prompt()`)

```python
# 1. 템플릿 로드
template = prompts["issue_analysis"]["template"]

# 2. 데이터 준비
versions_text = "- Product: 5.4.11.1\n- Agent Version: 5.4.11"
images_text = "- tasks/IMX-9326/images/image_0.png"
...

# 3. 변수 치환
prompt = template.format(
    title="JSPD 메모리 누수 현상",
    description="5.4.11 버전에서...",
    images=images_text,
    comments=comments_text,
    versions=versions_text,
    version_paths=paths_text
)

# 4. 완성된 프롬프트 저장
# tasks/IMX-9326/prompt.txt
```

---

## 템플릿 작성 팁

### 1. 명확한 지시사항

❌ **나쁜 예:**
```
이슈를 분석해주세요.
```

✅ **좋은 예:**
```
다음 형식으로 상세한 분석 보고서를 작성해주세요:
### 버전 정보
### 이슈 요약 (2-3문장)
### 재현 단계
...
```

### 2. 구조화된 출력

출력 형식을 명확히 정의하면 일관된 결과를 얻을 수 있습니다.

```
### 섹션 제목
(무엇을 작성할지 설명)
- 항목 1: ...
- 항목 2: ...
```

### 3. 컨텍스트 제공

```
당신은 InterMax 고객 지원 엔지니어가 보고한 이슈를 분석하는 전문가입니다.
다음 디렉토리의 디컴파일된 코드베이스를 검토하여...
```

---

## 예시: 템플릿 렌더링 결과

### 입력 (task.json)

```json
{
  "id": "IMX-9326",
  "name": "JSPD 메모리 누수 현상",
  "description": "5.4.11 버전에서 메모리가 계속 증가합니다",
  "custom_fields": {
    "Product": "5.4.11.1"
  }
}
```

### 템플릿 (issue_analysis)

```
당신은 InterMax 이슈를 분석하는 전문가입니다.

## 태스크 정보
제목: {title}

{description}

## 버전 정보
{versions}

...
```

### 출력 (prompt.txt)

```
당신은 InterMax 이슈를 분석하는 전문가입니다.

## 태스크 정보
제목: JSPD 메모리 누수 현상

5.4.11 버전에서 메모리가 계속 증가합니다

## 버전 정보
- Product: 5.4.11.1

...
```

---

## 트러블슈팅

### Q: 템플릿 변수가 치환되지 않음

**증상:** `{title}` 같은 변수가 그대로 출력됨

**해결:**
- `prompts.json` 문법 오류 확인
- `analyze.py:render_prompt()` 함수 확인
- 변수명 철자 확인 (`{title}` vs `{titile}`)

### Q: 한국어가 깨짐

**해결:**
- `prompts.json`을 UTF-8 인코딩으로 저장
- `analyze.py`에서 `encoding="utf-8"` 확인

### Q: 커스텀 템플릿이 선택 안 됨

**해결:**
- `analyze.py`의 `choices` 리스트에 템플릿 ID 추가
- 템플릿 ID가 `prompts.json`의 키와 정확히 일치하는지 확인

---

## 요약

| 항목 | 설명 |
|------|------|
| **위치** | `prompts.json` |
| **변수** | `{title}`, `{description}`, `{images}`, `{comments}`, `{versions}`, `{version_paths}` |
| **렌더링** | `analyze.py:render_prompt()` 함수 |
| **결과** | `tasks/{TASK_ID}/prompt.txt` (디버깅용) |
| **언어** | 한국어 (2025-02-01 업데이트) |

---

템플릿을 수정하거나 새로 추가하면, 다양한 분석 시나리오에 맞춰 Claude의 응답을 커스터마이징할 수 있습니다.
