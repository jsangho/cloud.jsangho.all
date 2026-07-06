# 1. Node.js 공식 이미지 가져오기
FROM node:24.15-alpine

# pnpm 글로벌 설치
RUN npm install -g pnpm

WORKDIR /app

# 2. 패키지 설치 파일만 먼저 복사 후 설치 (캐싱 효율을 위해)
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

# 3. 소스 코드 전체 복사
COPY . .

# 4. Next.js 개발 서버 실행 (볼륨 마운트로 핫 리로드)
CMD ["pnpm", "dev"]
