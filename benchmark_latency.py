import requests
import time
import math

# Cấu hình
API_URL = "http://localhost:8000/api/chat"
NUM_REQUESTS = 50 # Chạy 50 lần để có mẫu thống kê đáng tin cậy

# Các truy vấn đại diện
test_payloads = [
    {"question": "thịt bò", "disease": "Suy thận"},
    {"question": "cơm trắng", "disease": "Tiểu đường"},
    {"question": "cá hồi", "disease": "Béo phì"},
    {"question": "trái thơm", "disease": "Tăng huyết áp"},
    {"question": "bánh mì", "disease": "Tiểu đường"},
]

def percentile(data, percent):
    size = len(data)
    if size == 0: return 0
    return sorted(data)[int(math.ceil((size * percent) / 100)) - 1]

def run_benchmark():
    print(f"Bắt đầu chạy tool đo lường Delay API: {NUM_REQUESTS} requests...")
    print(f"Địa chỉ đích: {API_URL}")
    print("-" * 50)
    
    latencies = []
    
    for i in range(NUM_REQUESTS):
        payload = test_payloads[i % len(test_payloads)]
        start_time = time.time()
        
        try:
            # Gửi request lên Backend FastAPI đang chạy localhost:8000
            response = requests.post(API_URL, json=payload, timeout=60)
            end_time = time.time()
            
            latency = (end_time - start_time) * 1000 # Đổi ra ms
            
            if response.status_code == 200:
                latencies.append(latency)
                print(f"✅ Req {i+1:02d}/{NUM_REQUESTS} [{payload['question']}] - Thành công: {latency:.0f} ms")
            elif response.status_code == 429:
                print(f"⚠️ Req {i+1:02d}/{NUM_REQUESTS} - Bị Rate Limit (HTTP 429). Chờ xả Rate Limit 10s...")
                time.sleep(10)
            else:
                print(f"❌ Req {i+1:02d}/{NUM_REQUESTS} - Lỗi Backend HTTP {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Req {i+1:02d}/{NUM_REQUESTS} - Không kết nối được Backend: {e}")
            print("❗ Đảm bảo bạn đã khởi động 'docker-compose up backend' hoặc đang chạy Backend bằng Uvicorn local!")
            return
            
        # Thêm 2.5 giây delay giữa mỗi request để lách luật Rate Limit của Groq Free Tier
        time.sleep(2.5) 

    if not latencies:
        print("\nKhông có request nào thành công để làm thống kê.")
        return

    # Sắp xếp mảng để tự tính P95, P99
    latencies.sort()
    avg_latency = sum(latencies) / len(latencies)
    p95_latency = percentile(latencies, 95)
    p99_latency = percentile(latencies, 99)
    min_latency = latencies[0]
    max_latency = latencies[-1]

    print("\n" + "="*50)
    print("📊 KẾT QUẢ BENCHMARK – TRÍCH XUẤT CHO BÁO CÁO")
    print("="*50)
    print(f"  Số request thành công : {len(latencies)} / {NUM_REQUESTS}")
    print(f"  Thời gian nhanh nhất  : {min_latency:.0f} ms")
    print(f"  Thời gian chậm nhất   : {max_latency:.0f} ms")
    print(f"  TRUNG BÌNH (Average)  : {avg_latency:.0f} ms")
    print(f"  Percentile 95 (P95)   : {p95_latency:.0f} ms")
    print(f"  Percentile 99 (P99)   : {p99_latency:.0f} ms")
    print("="*50)

if __name__ == "__main__":
    run_benchmark()
