# CP6 · Cloud Deployment

## URL công khai

Agent Part 6 đang chạy tại [day14-cp6-agent.onrender.com](https://day14-cp6-agent.onrender.com). Render báo deployment `live` và bốn phép thử HTTP CP6 đều đạt tại 19:44 ngày 25/11/2026 (UTC+7). [Dashboard của agent](https://dashboard.render.com/web/srv-dc3dftm7bikc73csolpg)

## Nền tảng và cấu hình

| Hạng mục | Cấu hình đã triển khai |
| --- | --- |
| Web service | `day14-cp6-agent`, Render Free, Singapore |
| Mã nguồn | Thư mục `06-lab-complete/` trên nhánh `deploy/cp6-render`, commit `4a158e0` |
| Build | Dockerfile multi-stage của agent CP5, runtime Docker |
| Key Value | `day14-cp6-redis`, Render Free, Singapore, tương thích Redis và truy cập qua mạng nội bộ |
| Health check | `/health` cho web service. `/ready` xác nhận agent kết nối được Redis |
| Biến môi trường | `PORT=10000`, `ENVIRONMENT=production`, `REDIS_URL` dùng kết nối nội bộ, `AGENT_API_KEY` lưu trong biến của service |

Render CLI xác nhận Blueprint hợp lệ, sau đó tạo Key Value và web service theo cấu hình đó. Hai dịch vụ ở cùng region để agent gọi Redis qua mạng nội bộ. [Blueprint CP6](06-lab-complete/render.yaml) · [Commit triển khai](https://github.com/vuductam20022004/K5-L3A-DAY14-VuDucTam-2A202603522-Deployment-Benchmark-Observability/commit/4a158e0f9c85e503ffb385edee88e7498aed8705) · [Render Key Value](https://render.com/docs/key-value)

## Kết quả kiểm chứng

| Phép thử | Mã mong đợi | Mã thực tế |
| --- | ---: | ---: |
| `GET /health` | 200 | 200 |
| `GET /ready` | 200 | 200 |
| `POST /ask` thiếu key | 401 | 401 |
| `POST /ask` có key đúng | 200 | 200 |

## Chạy lại phép thử

Mở tab Environment của web service trên Render để lấy `AGENT_API_KEY`. Trong terminal Ubuntu, chạy đoạn dưới đây và dán key tại lời nhắc. `read -rsp` ẩn giá trị đang nhập. [Dashboard của agent](https://dashboard.render.com/web/srv-dc3dftm7bikc73csolpg)

```bash
BASE=https://day14-cp6-agent.onrender.com
read -rsp "AGENT_API_KEY: " AGENT_API_KEY
printf '\n'
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'
unset AGENT_API_KEY
```

## Ảnh bằng chứng

`test.png` được xuất từ đầu ra của lượt kiểm thử thật lúc 23:29 ngày 25/11/2026 (UTC+7). Ảnh hiển thị đủ bốn mã HTTP và ẩn giá trị của key. Hai ảnh giao diện Render còn chờ chụp. [Kết quả kiểm thử](screenshots/test.png)

| Tệp cần lưu | Nội dung cần thấy |
| --- | --- |
| `screenshots/dashboard.png` | Dashboard Render có web service `day14-cp6-agent` và Key Value `day14-cp6-redis` |
| `screenshots/running.png` | Deployment của agent có trạng thái `Live` và URL công khai |
| `screenshots/test.png` | Đã lưu đầu ra chứa bốn mã `200`, `200`, `401`, `200` |

Phần so sánh Railway với Render và phân tích pipeline Cloud Run nằm trong bài làm. [MISSION_ANSWERS.md](MISSION_ANSWERS.md#part-3--cloud-deployment-cp6)
