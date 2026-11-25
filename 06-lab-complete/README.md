# Part 6 — Final Project: Production-ready AI Agent

Agent dùng FastAPI, mock LLM và Redis. Bộ chấm CP5 kiểm tra agent chạy trực tiếp và trong Docker. Mốc hoàn thành là **`PASS 12/12`** khi chạy bộ chấm đầy đủ.

---

## Checklist Deliverable

- [ ] Dockerfile (multi-stage, < 500 MB)
- [ ] docker-compose.yml (agent + redis)
- [ ] .dockerignore
- [ ] Health check endpoint (`GET /health`)
- [ ] Readiness endpoint (`GET /ready`)
- [ ] API Key authentication
- [ ] Rate limiting
- [ ] Cost guard
- [ ] Config từ environment variables
- [ ] Structured logging
- [ ] Graceful shutdown
- [ ] Public URL ready (Railway / Render config)

---

## Script chấm dựa vào những tiêu chí dưới đây

Script tự khởi động agent của bạn, gọi API thật, build và chạy Docker image. Để chấm được, agent phải tuân theo các quy ước sau:

| Hạng mục | Yêu cầu |
|----------|---------|
| Điểm vào | `app/main.py` có biến `app` (FastAPI), chạy được bằng `uvicorn app.main:app --workers 2` từ thư mục này |
| `GET /health` | Luôn trả **200** khi process còn chạy, kể cả khi Redis chưa kết nối được |
| `GET /ready` | **200** khi sẵn sàng; **503** khi Redis (`REDIS_URL`) không kết nối được |
| `POST /ask` | Body JSON `{"question": "..."}` (được phép có thêm `user_id`) → **200** |
| API key | Header `X-API-Key` phải trùng biến `AGENT_API_KEY`; thiếu hoặc sai → **401** |
| Rate limit | Tối đa `RATE_LIMIT_PER_MINUTE` request / 60 giây cho mỗi API key; vượt → **429** (nên có header `Retry-After`). State lưu trong **Redis**, vẫn còn sau khi restart agent |
| Cost guard | Tổng chi phí vượt `DAILY_BUDGET_USD` (hoặc `MONTHLY_BUDGET_USD`) → **402** |
| Biến môi trường | Đọc từ env: `AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD` / `MONTHLY_BUDGET_USD`, `PORT`, `ENVIRONMENT`. Liệt kê đủ trong `.env.example`. Script chạy với `ENVIRONMENT=staging` |
| Log | Mỗi dòng log của app là **1 JSON object hợp lệ** (log của uvicorn không tính) |
| Graceful shutdown | Nhận SIGTERM khi đang có request → request đó vẫn trả 200, process tự thoát với exit code 0. Trong Docker, `docker stop` phải xong trong < 10 giây |
| Docker image | Multi-stage, base slim, user non-root, có `HEALTHCHECK`, < 500 MB. `CMD` lắng nghe theo biến `PORT` (mặc định 8000), uvicorn là PID 1. Container khởi động được khi **không có** Redis |
| Compose | Một service build từ `Dockerfile` + một service dùng image `redis:*`; agent có `REDIS_URL` trỏ tới service Redis và `depends_on` nó |
| `.dockerignore` | Loại trừ `.env`, `__pycache__`, `venv` |
| Deploy config | `railway.toml` (builder `DOCKERFILE`, `healthcheckPath = "/health"`) **hoặc** `render.yaml` (`type: web`, `healthCheckPath: /health`, secret dùng `generateValue` / `sync: false`) |

---

## Mã nguồn

```
06-lab-complete/
├── app/
│   ├── main.py           # HTTP endpoints, log JSON và lifespan
│   ├── config.py         # Cấu hình từ biến môi trường
│   ├── auth.py           # Xác thực X-API-Key
│   ├── rate_limiter.py   # Sliding window trong Redis
│   ├── cost_guard.py     # Dự trữ và đối soát chi phí trong Redis
│   └── redis_client.py   # Kết nối Redis và readiness
├── utils/mock_llm.py     # Mock LLM
├── Dockerfile            # Image multi-stage
├── docker-compose.yml    # Agent và Redis
├── .dockerignore
├── .env.example          # Mẫu biến môi trường
├── railway.toml          # Cấu hình cho CP6
├── requirements.txt
├── check_production_ready.py   # Bộ chấm CP5
└── benchmark-observability/    # Part 7
```

`POST /ask` xác thực API key, kiểm tra cửa sổ 60 giây, dự trữ chi phí trước khi gọi mock LLM rồi ghi lại chi phí theo phản hồi thực tế. Redis giữ các bộ đếm dùng chung giữa worker. Ngân sách mặc định là `10 USD` mỗi tháng theo UTC. Khi đặt `DAILY_BUDGET_USD`, agent dùng ngân sách ngày. Số token của mock được ước lượng theo độ dài nội dung. [CODE_LAB.md — Part 6](../CODE_LAB.md#part-6-final-project-60-phút)

---

## Chạy local

Chạy các lệnh sau trong `06-lab-complete/` từ terminal Ubuntu WSL2.

```bash
export PORT=8000
export AGENT_API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
docker compose -p k5-day14-cp5 up -d --build --wait

cp5_base_url="http://127.0.0.1:$PORT"
curl -i "$cp5_base_url/health"
curl -i "$cp5_base_url/ready"
curl -i -X POST "$cp5_base_url/ask" \
  -H "X-API-Key: $AGENT_API_KEY" -H "Content-Type: application/json" \
  -d '{"question":"Docker là gì?"}'

docker compose -p k5-day14-cp5 down
```

Để dùng file cấu hình local, sao chép `.env.example` thành `.env` và điền `AGENT_API_KEY` trong `.env`. Compose đặt `REDIS_URL` cho agent trỏ đến service `redis`. Khi chạy bằng Python với Redis riêng, đặt `REDIS_URL` qua env rồi chạy `python -m app.main` trong môi trường đã cài requirements.

---

## Chấm bài

```bash
python3 -m venv ~/.venvs/day14-cp5
source ~/.venvs/day14-cp5/bin/activate
python -m pip install -r requirements.txt
python check_production_ready.py                 # chấm đầy đủ — cần Docker đang chạy
python check_production_ready.py --skip-docker   # chế độ nhanh khi đang làm (bỏ build image)
python check_production_ready.py --static-only   # chỉ đọc file, không chạy agent
python check_production_ready.py --public-url https://your-app.railway.app   # thêm kiểm tra URL đã deploy
```

- Kết quả in theo từng tiêu chí: ✅ đạt · ❌ chưa đạt · ⚠️ chưa kiểm tra được.
- **Chỉ PASS khi cả 12 tiêu chí ✅.** Mục ⚠️ (vd máy chưa bật Docker) cũng tính là chưa đạt, nên khi nộp bài phải chạy chế độ đầy đủ.
- Lần đầu chạy, script build Docker image nên mất vài phút. Bài test stateless cần Redis: script dùng `REDIS_URL` nếu có, không thì tự bật container `redis:7-alpine` tạm thời.

---

## Deploy

**Railway · CP6**

Dùng thư mục `06-lab-complete/` làm root của service. Thêm Redis trên Railway và đặt `REDIS_URL` cho agent bằng URL nội bộ của Redis. Đặt `AGENT_API_KEY` trong biến môi trường của service.

```bash
npm i -g @railway/cli
railway login
railway init
railway variables set AGENT_API_KEY=your-secret-key
railway up
railway domain        # nhận public URL
```

**Render:** push repo lên GitHub → Render Dashboard → New → Blueprint → chọn repo (Render đọc `render.yaml`) → điền secret → Deploy.

Sau khi deploy: `python check_production_ready.py --public-url <URL>` và ghi URL vào `DEPLOYMENT.md` (xem [DAY14_DELIVERY_CHECKLIST.md](../DAY14_DELIVERY_CHECKLIST.md)).

---

## Part 7 — Benchmark & Observability

Agent đã chạy được, bước tiếp theo là đo xem nó **nhanh** và **đúng** tới đâu, rồi **giám sát** khi chạy thật:

```bash
cd benchmark-observability
```

| Thư mục | Nội dung |
|---------|----------|
| `develop/` | Agent có `/metrics`, load test (p50/p95/p99, SLO), eval trên golden dataset + quality gate |
| `production/` | Docker Compose: agent x2 + Nginx + Prometheus + Grafana + Jaeger + Locust, 4 alert rules |

Hướng dẫn đầy đủ: [benchmark-observability/README.md](benchmark-observability/README.md). Nộp kèm `BENCHMARK_REPORT.md` theo [mẫu](benchmark-observability/BENCHMARK_REPORT_TEMPLATE.md).
