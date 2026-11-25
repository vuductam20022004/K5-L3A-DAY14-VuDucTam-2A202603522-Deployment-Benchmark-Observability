# Benchmark & Observability Report — Day 14

**Họ tên:** Vũ Đức Tâm (MSSV 2A202603522)

**Ngày chạy:** 25/11/2026 (UTC+7)

**Môi trường CP7:** Ubuntu 24.04 trên WSL2, x86-64, 12 CPU logic, Python 3.12.3. Agent v1 nghe tại `127.0.0.1:8001`, agent v2 tại `127.0.0.1:8002`. Mô hình `mock-llm-small` tính token và chi phí mô phỏng.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Ngưỡng mặc định của `load_test.py`, theo dõi thời gian chờ của nhóm request thành công chậm hơn. |
| Error rate `/ask` | ≤ 2% | Ngưỡng mặc định của `load_test.py`, theo dõi phần request có trạng thái khác `200`. |
| Accuracy trên golden dataset | ≥ 85% trong CI | Ngưỡng của Exercise 7.3 cho pull request. Lượt nghiệm thu CP7 sau khi sửa KB yêu cầu 100% và 0 regression. |

### Metrics từ Exercise 7.1

Gửi `POST /ask` với câu hỏi về Prometheus vào agent v2 trả `200`. Đọc `/metrics` ngay sau đó thấy `http_requests_total` là Counter, `agent_in_flight_requests` là Gauge và `agent_question_length_chars` là Histogram mới. `agent_question_length_chars_count` bằng `1` sau request mẫu.

Middleware dùng template route như `/ask` và gộp URL lạ vào `unmatched`. Nếu dùng URL thực làm label, mỗi đường dẫn lạ sẽ sinh thêm time series cho những tổ hợp label tương ứng, làm tăng RAM và chi phí thu thập. Histogram dùng các bucket hữu hạn để tổng hợp độ dài câu hỏi. [Mã metrics](06-lab-complete/benchmark-observability/develop/app.py)

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

Mỗi lượt đo 300 request sau một request warm-up. RPS tính trên toàn bộ lượt đo, còn các thống kê latency lấy từ response `200`. Load test dùng `MOCK_ERROR_RATE=0.01`. [Script load test](06-lab-complete/benchmark-observability/develop/load_test.py)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.42 | 188.4 | 218.2 | 1697.4 | 1.33% | PASS |
| 10 | 43.21 | 188.8 | 218.2 | 1693.5 | 1.33% | PASS |
| 50 | 104.97 | 195.9 | 240.3 | 1707.4 | 0.00% | PASS |
| 100 | 70.95 | 300.6 | 2308.5 | 2532.6 | 1.33% | FAIL |

RPS tăng từ 4.42 ở concurrency 1 lên 104.97 ở concurrency 50, rồi giảm còn 70.95 ở concurrency 100. Tại mức 100, p95 lên 2308.5 ms và vượt ngưỡng 500 ms. Kết quả phù hợp với việc nhiều request cùng chờ tài nguyên hoặc kết nối. Bài đo tính thời gian từ phía client nên gộp cả thời gian chờ kết nối và thời gian xử lý của server. [Concurrency 1](06-lab-complete/benchmark-observability/develop/reports/load_v2_c1.json) · [Concurrency 10](06-lab-complete/benchmark-observability/develop/reports/load_v2_c10.json) · [Concurrency 50](06-lab-complete/benchmark-observability/develop/reports/load_v2_c50.json) · [Concurrency 100](06-lab-complete/benchmark-observability/develop/reports/load_v2_c100.json)

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 190.2 | 218.4 | 224.3 |
| 0.03 (mặc định) | 237.8 | 218.3 | 1690.0 |
| 0.1 | 328.9 | 1692.5 | 1717.4 |

Mỗi lần đổi `MOCK_SLOW_RATE`, khởi động lại v2 và đo ở concurrency 20. Khi tỷ lệ giả lập tăng từ 0 lên 3%, avg tăng từ 190.2 lên 237.8 ms còn p99 tăng từ 224.3 lên 1690.0 ms. Các request nhanh chiếm đa số nên kéo trung bình về gần mức bình thường. Ở 10%, nhóm chậm đủ lớn để p95 lên 1692.5 ms. Dùng p95 cho SLO và theo dõi thêm p99 để nhìn nhóm chậm nhất.

Lượt slow rate 0 ghi 7 response `503` trong 300 request, nên error rate 2.33% vượt ngưỡng 2%. Lỗi upstream được giả lập riêng với độ trễ. [Slow rate 0](06-lab-complete/benchmark-observability/develop/reports/load_v2_slow_0.json) · [Slow rate 0.03](06-lab-complete/benchmark-observability/develop/reports/load_v2_slow_0.03.json) · [Slow rate 0.1](06-lab-complete/benchmark-observability/develop/reports/load_v2_slow_0.1.json)

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Ba lượt eval dùng cùng 23 câu hỏi và đặt `MOCK_ERROR_RATE=0` để đo chất lượng câu trả lời. Runner chấm từng câu theo từ khóa kỳ vọng và ngưỡng điểm mặc định `0.6`. [Script eval](06-lab-complete/benchmark-observability/develop/eval/run_eval.py)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 1/23 (4.35%) | 21/23 (91.30%) | 23/23 (100.00%) |
| Avg tokens / câu | 56.6 | 109.0 | 114.9 |
| Tổng cost (USD) | 0.000397 | 0.000760 | 0.000801 |
| Cost / câu đúng (USD) | 0.00039735 | 0.00003619 | 0.00003482 |
| p95 latency (ms) | 189.0 | 210.6 | 209.8 |
| Quality gate | FAIL (≥80%) | PASS (≥80%) | PASS (≥100%) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung tài liệu về cách xác thực API key và JWT, gồm kiểm tra chữ ký hoặc MAC và claim `exp`. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung tài liệu về HPA và các chỉ số dùng để điều chỉnh số replica. |

Retrieval làm v2 dùng thêm token và tăng p95 từ 189.0 ms lên 210.6 ms trong lượt eval ban đầu. Số câu đúng tăng từ 1 lên 21, kéo chi phí mô phỏng trên mỗi câu đúng xuống 0.00003619 USD. Sau khi bổ sung hai tài liệu, v2 đạt 23/23 câu, 0 regression và còn 0.00003482 USD cho mỗi câu đúng. Chi phí trên mỗi câu đúng gắn mức sử dụng token với số kết quả đạt yêu cầu. [Eval v1](06-lab-complete/benchmark-observability/develop/reports/eval_v1.json) · [Eval v2](06-lab-complete/benchmark-observability/develop/reports/eval_v2.json) · [Eval v2 sau sửa](06-lab-complete/benchmark-observability/develop/reports/eval_v2_fixed.json)

Lệnh kiểm chứng sau khi khởi động lại v2 với knowledge base mới.

```bash
python eval/run_eval.py --url http://127.0.0.1:8002 --min-accuracy 1.0 \
  --baseline reports/eval_v2.json --out reports/eval_v2_fixed.json
```

### Quality gate cho pull request

Job CI cài `requirements.txt`, khởi động agent v2 với `MOCK_ERROR_RATE=0` và chờ `/health` trả `200`. Từ thư mục `develop`, chạy lệnh sau trực tiếp trong bước kiểm tra để CI nhận exit code của script.

```bash
python eval/run_eval.py --url http://127.0.0.1:8002 --min-accuracy 0.85
```

Exit code `0` cho phép job qua. Exit code `1` làm job fail khi accuracy dưới 85%. Nếu thêm `--baseline` trỏ tới báo cáo đã duyệt, một câu đúng ở baseline rồi thành sai cũng làm job fail. Đặt job làm required status check của nhánh đích để pull request chỉ được merge sau khi job qua. [Runner eval](06-lab-complete/benchmark-observability/develop/eval/run_eval.py)

---

## 4. Observability stack (production)

Project Docker Compose `k5-day14-observability` chạy agent với Nginx, Prometheus, Grafana, Jaeger và Locust. Lượt build đầu báo `ModuleNotFoundError: No module named 'uvicorn'`. Thêm `PYTHONUSERBASE=/home/agent/.local` vào image runtime để Python của user `agent` tìm được các package từ builder. Sau khi build lại, Nginx trả `200` ở `/health`, `404` ở `/metrics`, `401` ở `POST /ask` thiếu key và `200` khi có key. Prometheus scrape `/metrics` trực tiếp từ agent qua mạng Compose. [Dockerfile runtime](06-lab-complete/benchmark-observability/production/Dockerfile) · [Cấu hình Nginx](06-lab-complete/benchmark-observability/production/nginx/nginx.conf)

### 4.1 Screenshot

Lượt đọc Grafana dùng 30 user, ramp-up 5 user/giây. Lúc 23:15:17 ngày 25/11/2026 (UTC+7), các truy vấn Prometheus đang cấp dữ liệu cho Golden Signals ghi nhận traffic 16.89 RPS, error rate 0.86%, p95 293.5 ms, avg 234.3 ms, và 3 request đang xử lý. p95 cao hơn avg cho thấy nhóm request ở phần đuôi có thời gian xử lý dài hơn mức trung bình.

Ba replica nhận tải gần đều với 5.63 RPS, 5.70 RPS, 5.56 RPS. Panel Tokens/s ghi 1243.51 token input/giây và 663.41 token output/giây. Prompt v2 chứa system prompt, câu hỏi và tài liệu truy xuất, trong khi response chỉ chứa câu trả lời. [Dashboard Grafana](http://localhost:3000/d/day14-agent-overview) · [Truy vấn của dashboard](06-lab-complete/benchmark-observability/production/grafana/dashboards/agent-overview.json)

- [x] `screenshots/grafana-dashboard.png` — ảnh xuất bằng Grafana Image Renderer từ khoảng thời gian của lượt tải 30 user. [Ảnh Golden Signals](screenshots/grafana-dashboard.png)
- [ ] `screenshots/jaeger-slow-trace.png` — trace chậm với span LLM hiển thị rõ. [Jaeger](http://localhost:16686/trace/9c5bf7dfeaa12363ef9f2251f90ca5af)
- [ ] `screenshots/jaeger-error-trace.png` — trace lỗi với event `exception` trong span LLM. [Jaeger](http://localhost:16686/trace/f731a5ea0d7f824a99bc0c1a4fcbf12b)
- [ ] `screenshots/prometheus-alert-firing.png` — hai rule cùng `firing`. [Prometheus Alerts](http://localhost:9090/alerts)

### 4.2 Thí nghiệm "phá hệ thống"

`promtool test rules /p/alert_rules_test.yml` trả `SUCCESS` với exit code `0`. Các rule chạy đánh giá mỗi 5 giây. Thời gian phát hiện trong bảng tính từ lúc bắt đầu thay đổi đến lần đầu quan sát trạng thái `firing` qua API Prometheus. [Rule unit test](06-lab-complete/benchmark-observability/production/prometheus/alert_rules_test.yml) · [Prometheus HTTP API](https://prometheus.io/docs/prometheus/latest/querying/api/#alerts)

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 91.4 giây | Error rate 20.48% khi phát hiện |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 149.7 giây | Latency p95 1899.5 ms khi phát hiện |
| D | `docker pause` một replica khi có hai replica | `AgentInstanceDown` | 42.4 giây | Instances up |

A và B được bật cùng lúc từ 23:15:53 với 30 user để quan sát hai rule đồng thời. Lúc 23:18:23 ngày 25/11/2026 (UTC+7), API ghi nhận cả hai rule đều `firing`. Khoảng đo gồm thời gian tạo lại container, scrape, đánh giá rule và điều kiện duy trì `for`. Ở ca D, mình bỏ pause cho container sau khi quan sát `AgentInstanceDown`. [Trang Alerts của Prometheus](http://localhost:9090/alerts)

**Phát hiện chất lượng giảm khi chuyển sang agent v1.** Các rule hạ tầng quan sát lỗi, độ trễ, khả năng scrape và tốc độ chi phí. Câu trả lời sai vẫn có thể trả HTTP `200` với latency đạt ngưỡng. Lượt eval CP7 đo v1 đúng 1/23 câu. Chạy golden eval theo phiên bản trước khi phát hành và định kỳ sau deploy, đối chiếu regression theo từng ID và gắn kết quả với `agent.version` để nhận ra lỗi chất lượng. [Eval v1](reports/eval_v1.json)

### 4.3 Debug bằng trace

Trace chậm nhất trong các trace mẫu truy vấn có span gốc `POST /ask` dài 3556.31 ms. Span `chat mock-llm-small` dài 3537.08 ms, chiếm 99.5% thời gian của request. Log `llm_call` ghi `llm_ms` từ độ trễ mà mock LLM tính trước khi ngủ. Jaeger dùng thời điểm bắt đầu và kết thúc span để đo thời gian thực đi qua bước đó. [Trace chậm 9c5bf7dfeaa12363ef9f2251f90ca5af](http://localhost:16686/trace/9c5bf7dfeaa12363ef9f2251f90ca5af) · [Jaeger Query API](https://www.jaegertracing.io/docs/2.23/architecture/apis/)

```json
{"ts":"2026-11-25T16:16:14.235908+00:00","level":"INFO","service":"observable-agent","instance":"40cdca8f4479","event":"llm_call","trace_id":"9c5bf7dfeaa12363ef9f2251f90ca5af","span_id":"310da7bffe1509c7","request_id":"6a0a2f1068aa","model":"mock-llm-small","agent_version":"v2","input_tokens":95,"output_tokens":55,"cost_usd":0.000047,"llm_ms":1695.5}
```

Trace lỗi có span gốc dài 96.59 ms. Span `chat mock-llm-small` dài 71.78 ms và có event `exception` với kiểu `utils.mock_llm.LLMError`. Log cùng `trace_id` ghi lỗi upstream `503` giả lập. [Trace lỗi f731a5ea0d7f824a99bc0c1a4fcbf12b](http://localhost:16686/trace/f731a5ea0d7f824a99bc0c1a4fcbf12b)

```json
{"ts":"2026-11-25T16:18:17.545549+00:00","level":"INFO","service":"observable-agent","instance":"6da0cf990561","event":"llm_error","trace_id":"f731a5ea0d7f824a99bc0c1a4fcbf12b","span_id":"3f803bfcb4381349","request_id":"beb7cddcd711","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

Snapshot Golden Signals, thời điểm alert và trace kèm log được lưu từ lượt chạy CP8. [Dữ liệu observability](benchmark-results/observability-evidence.json)

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 62.14 | 190 | 270 | 1700 | 86/7885 (1.09%) |
| 3 | 61.81 | 190 | 220 | 1700 | 67/7847 (0.85%) |

Lấy hàng `Aggregated` trong từng CSV, gồm cả `POST /ask` và `GET /health`. Mỗi lượt dùng 100 user, ramp-up 10 user/giây trong 2 phút, cùng cấu hình mock mặc định. Các lỗi ghi trong CSV là HTTP `503` từ mock upstream. [CSV một replica](benchmark-results/scale_1_stats.csv) · [CSV ba replica](benchmark-results/scale_3_stats.csv)

Lượt đầu cho thấy `docker compose run` khởi động dependency với số replica mặc định. Lượt đo trong bảng chạy với `docker compose run --rm --no-deps locust` để giữ số instance đã chọn. Mỗi lượt có 26 mẫu Prometheus cách nhau 5 giây. `sum(up{job="agent"})` giữ lần lượt ở 1 và 3 trong các khoảng đo.

Khi tăng từ một lên ba replica, p95 tổng giảm từ 270 xuống 220 ms và p95 riêng của `/ask` giảm từ 280 xuống 220 ms. Throughput vẫn quanh 62 RPS và p99 giữ ở 1700 ms. Với 100 user có thời gian nghỉ 0.5–2 giây giữa request, mức tải tạo ra gần giống nhau ở hai lượt. Khoảng p99 phù hợp với độ trễ giả lập của mock LLM vì mỗi request vẫn gọi LLM một lần. [Kịch bản Locust](06-lab-complete/benchmark-observability/production/locust/locustfile.py)

---

## 6. Kết luận

1. p95 và p99 cho thấy nhóm request chậm trong khi phần lớn request giữ avg gần mức thường thấy.
2. Benchmark scale cần giữ mức tải cố định và xác minh số replica thực sự phục vụ qua Prometheus. Restart hoặc đổi replica giữa lượt có thể làm sai kết luận.
3. Dùng metric để xác định lúc sự cố xuất hiện, trace để khoanh span chiếm thời gian và `trace_id` để đọc log của chính request đó.

Trên production có thể đo tỷ lệ câu đúng theo phiên bản bằng một tập eval định kỳ, rồi cảnh báo nếu tỷ lệ giảm dưới ngưỡng chất lượng. Giữ label ở mức phiên bản hoặc nhóm câu hỏi để giới hạn số time series.
