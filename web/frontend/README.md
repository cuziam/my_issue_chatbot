# InterMax Issue Analysis — Web Dashboard

ClickUp 이슈 분석 결과를 실시간으로 모니터링하고 AI와 대화할 수 있는 웹 대시보드입니다.

## 기술 스택

- **Frontend**: React 19 + TypeScript + Vite + TailwindCSS
- **Backend**: FastAPI + uvicorn (WebSocket)
- **AI**: Claude CLI (`claude -p --output-format stream-json`)

## 주요 기능

- **Dashboard**: 분석 대상 태스크 목록 조회 (ClickUp 연동)
- **Task Detail**: 태스크 상세 — 설명, 댓글, 분석 보고서, 패치 리뷰, 진행 상태
- **Ask AI Chat**: 태스크 컨텍스트 기반 AI 대화 (Claude 세션 resume 지원)
- **Jobs**: 분석 작업 목록 및 실시간 진행 모니터링 (WebSocket)
- **실시간 스트리밍**: 분석/채팅 진행 상황을 WebSocket으로 실시간 표시

## 실행

```bash
# Frontend (dev)
cd web/frontend
npm install
npm run dev          # http://localhost:5173

# Backend
cd web/backend
pip install -r requirements.txt
uvicorn web.backend.main:app --host 0.0.0.0 --port 8000
```

## 프로젝트 구조

```
web/frontend/src/
├── api/client.ts              # API 클라이언트 (REST + WebSocket)
├── components/
│   ├── ChatPanel.tsx          # Ask AI 채팅 모달
│   ├── ProgressTimeline.tsx   # 분석 진행 타임라인
│   ├── ProgressBanner.tsx     # 상단 진행 배너
│   ├── ErrorBoundary.tsx      # 에러 경계
│   ├── task-detail/           # TaskDetail 서브 컴포넌트
│   │   ├── DescriptionTab.tsx
│   │   ├── CommentsTab.tsx
│   │   ├── ProgressTab.tsx
│   │   └── TaskSidebar.tsx
│   └── ui/                    # 공통 UI 컴포넌트
│       ├── Badge, Button, Card, Modal, Tabs, Toast ...
├── pages/
│   ├── Dashboard.tsx          # 메인 태스크 목록
│   ├── TaskDetail.tsx         # 태스크 상세 페이지
│   └── Jobs.tsx               # 분석 작업 목록
├── hooks/useWebSocket.ts      # WebSocket 훅
├── contexts/WebSocketContext.tsx
├── stores/toastStore.ts       # 토스트 알림 상태
├── constants/index.ts         # 상수 정의
├── utils/format.ts            # 포맷 유틸리티
└── types/index.ts             # TypeScript 타입 정의

web/backend/
├── main.py                    # FastAPI 앱 + CORS + WebSocket
├── routers/
│   ├── analysis.py            # 분석 API (/api/analysis/*)
│   └── chat.py                # 채팅 API (/api/chat/*)
├── services/
│   ├── analysis_service.py    # 분석 실행 (Claude subprocess)
│   ├── chat_service.py        # 채팅 실행 (Claude --resume)
│   ├── claude_subprocess.py   # Claude CLI 공통 유틸리티
│   └── progress_emitter.py    # 진행 상태 WebSocket 발행
├── models/                    # Pydantic 모델
└── ws/manager.py              # WebSocket 연결 관리자
```
