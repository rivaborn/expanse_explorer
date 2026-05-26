from docker.io/node:18
workdir /app/backend/
copy ./backend/package*.json ./backend/.npmrc ./
run npm ci
copy ./backend/ ./

from docker.io/node:18
workdir /app/frontend/
copy ./frontend/package*.json ./frontend/.npmrc ./
run npm ci
copy ./frontend/ ./
run npm run build

from docker.io/node:18
run apt update && apt install -y wait-for-it && rm -rf /var/lib/apt/lists/*
run npm install -g concurrently
workdir /app/backend/
copy --from=0 /app/backend/ ./
workdir /app/frontend/build/
copy --from=1 /app/frontend/build/ ./
