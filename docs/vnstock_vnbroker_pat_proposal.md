# ĐỀ XUẤT KIẾN TRÚC: BẮT BUỘC SỬ DỤNG PAT KEY CHO THƯ VIỆN VNBROKER
*(Tài liệu đã cập nhật sau kết quả Audit & Đánh giá Kiến trúc ngày 15/06/2026)*

Tài liệu này được biên soạn để làm cơ sở xem xét, đánh giá và thảo luận về việc loại bỏ cơ chế kết nối kép hiện tại (kết nối trực tiếp và gián tiếp) và chuyển hẳn sang cơ chế bắt buộc xác thực qua **Personal Access Token (PAT)**, kết hợp các giải pháp dự phòng và giảm thiểu ma sát người dùng.

---

## 1. So sánh `vnbroker` và `vnstock`

Để có cái nhìn tổng quan trước khi đi vào giải pháp, dưới đây là bảng đối chiếu giữa hai thư viện:

| Tiêu chí | `vnstock` (Bản cộng đồng / Lịch sử) | `vnbroker` (Dự án hiện tại) |
| :--- | :--- | :--- |
| **Kiến trúc mặc định** | **Trực tiếp (Direct):** Client kết nối thẳng tới các API public của CTCK. | **Kép (Dual-mode):** Hỗ trợ cả kết nối trực tiếp và kết nối gián tiếp thông qua SaaS Gateway. |
| **Xác thực người dùng** | Không có xác thực (Anonymous). | Hỗ trợ xác thực PAT key (`vninvest_pat_...`) qua module `vninvest-sdk`. |
| **Bảo mật & Tải trọng** | Không kiểm soát. Dễ bị chặn IP (IP Ban) từ phía các công ty chứng khoán khi gọi nhiều mã. | Tích hợp sẵn `ProxyManager` thông minh và tính năng cô lập dữ liệu (Tenant Isolation). |
| **Hiệu năng & Batching** | Đồng bộ, tuần tự (Sequential) -> Tải chậm khi danh mục nhiều mã. | Hỗ trợ **Async Batch Fetching** (VCI `fetch_multiple`) và Redis Caching tập trung. |
| **Khả năng thương mại** | Không thể thương mại hóa dạng API SaaS vì người dùng tự do kết nối trực tiếp. | Có khả năng phân hạng dịch vụ (Free/Pro/Enterprise) dựa vào hạn mức cuộc gọi (Quota) gắn với PAT. |

---

## 2. Vấn đề của cơ chế Kép (Direct & Indirect) hiện tại

Hiện tại, thư viện đang cho phép 2 cơ chế hoạt động song song:
1. **Truy cập trực tiếp (Direct)**: Người dùng tải `vnbroker` về và tự do gọi dữ liệu từ các CTCK mà không cần khai báo bất cứ thông tin định danh nào.
2. **Truy cập gián tiếp (Indirect)**: Sử dụng gói SaaS `vninvest-sdk` gọi qua Gateway trung gian để được quản lý hạn mức, caching và phân quyền.

### Rủi ro của mô hình kép:
* **Lỗ hổng bypass**: Người dùng hoàn toàn có thể "lách luật" bằng cách dùng trực tiếp thư viện `vnbroker` để lấy dữ liệu miễn phí mà không cần trả tiền cho gói dịch vụ SaaS qua PAT key.
* **Rủi ro IP Ban**: Khi người dùng gọi trực tiếp từ máy của họ với tần suất cao, IP của người dùng hoặc của các cụm server chứa thư viện dễ bị phía CTCK chặn, làm gián đoạn ứng dụng của họ.
* **Chi phí bảo trì**: Mỗi khi CTCK thay đổi API thô, chúng ta phải cập nhật lại mã nguồn client và bắt buộc tất cả người dùng cập nhật thư viện `vnbroker` trên máy của họ.

---

## 3. Đề xuất Kiến trúc: PAT-Only với Cơ chế Lai (Hybrid Model)

Để giải quyết vấn đề bảo mật nhưng đồng thời giảm thiểu ma sát sử dụng (onboarding friction) và đảm bảo tính sẵn sàng cao, chúng tôi đề xuất mô hình **PAT-Only lai ghép** dưới đây:

```
                                  KIẾN TRÚC MÔ HÌNH LAI (HYBRID MODEL)
                                  
                                        [ Khởi tạo Vnbroker() ]
                                                   |
                                     +-------------+-------------+
                                     |                           |
                            (Có Key / Default Key)           (Gateway Down)
                                     v                           v
                       [ vninvest SaaS Gateway ]     [ Emergency Fallback Mode ]
                                     |                           |
                       +-------------+-------------+             | (Gọi Direct thô từ Client)
                       |                           |             v
                 (Cache Hit)                 (Cache Miss)   [ API Gốc của CTCK ]
                       v                           v        (Rate Limit nội bộ cực thấp)
                 [ Redis Cache ]         [ vnbroker Server ]
```

---

## 4. Chi tiết các Điểm Bổ sung & Cải tiến từ Audit

### 4.1. Giảm thiểu ma sát đăng ký (Onboarding Friction) bằng Default PAT
Để nhà phát triển có thể cài đặt và thử nghiệm ngay mà không cần qua bước đăng ký tài khoản phiền phức, thư viện sẽ được nhúng sẵn một token mặc định với hạn mức cơ bản.

```python
# vnbroker/common/client.py

DEFAULT_PAT = "vninvest_pat_dev_free_default_unregistered_key"
```
* **Chính sách của Default PAT**: Hạn mức thấp (Ví dụ: 100 requests/ngày). Vượt quá ngưỡng này sẽ nhận mã lỗi `429` kèm hướng dẫn đăng ký tài khoản để nhận PAT cá nhân miễn phí.

### 4.2. Chế độ dự phòng khẩn cấp khi Gateway Down (Emergency Fallback Mode)
Đề phòng rủi ro Gateway bị nghẽn hoặc sập hoàn toàn (Single Point of Failure), thư viện client-side sẽ tích hợp cơ chế tự động hạ cấp khẩn cấp:

```python
# Logic gửi request của client-side
def dispatch_request(endpoint, payload):
    try:
        # 1. Thử gọi qua API Gateway
        return gateway_client.request(endpoint, json_data=payload)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        # 2. Phát hiện Gateway down -> Chuyển sang Emergency Fallback
        logger.warning("Gateway không phản hồi. Chuyển sang chế độ kết nối trực tiếp khẩn cấp.")
        return local_emergency_dispatch(endpoint, payload)
```
* **Cơ chế khẩn cấp**: Client tự giải quyết bằng cách gọi trực tiếp API của CTCK từ IP local. Để tránh bị CTCK ban IP và lạm dụng chế độ này, client sẽ áp dụng **Strict Rate Limiting cục bộ** (ví dụ: tối đa 10 requests/ngày trong chế độ khẩn cấp).

### 4.3. Giám sát & Cảnh báo (Metrics & Alerting)
Phía Gateway Server sẽ được tích hợp các công cụ quan sát (OpenTelemetry/Prometheus) để theo dõi:
* **API Latency**: Phân tích độ trễ chặng trung gian để điều phối tải hoặc tối ưu hóa routing.
* **Cache Hit Rate**: Đảm bảo hiệu quả tối ưu hóa chi phí API nguồn.
* **Provider Uptime**: Phát hiện sớm khi một CTCK (TCBS, KBS, VCI) bị lỗi hoặc thay đổi API để có biện pháp xử lý kịp thời.

---

## 5. Kế hoạch triển khai mã nguồn cụ thể

### 5.1. Khởi tạo Client hỗ trợ Default PAT & Emergency Mode

```python
# file: vnbroker/common/client.py

import os
from typing import Optional
from vnbroker.core.exceptions import AuthenticationError
from vnbroker.core.utils.gateway_client import GatewayHttpClient

DEFAULT_PAT = "vninvest_pat_dev_free_default_unregistered_key"

class Vnbroker:
    def __init__(
        self, 
        symbol: Optional[str] = None, 
        pat_key: Optional[str] = None,
        gateway_url: Optional[str] = None,
        show_log: bool = True
    ):
        # 1. Lấy PAT Key: user truyền vào -> biến môi trường -> Default PAT
        self.pat_key = pat_key or os.getenv("VNBROKER_PAT_KEY") or DEFAULT_PAT
        
        if not self.pat_key.startswith("vninvest_pat_"):
            raise AuthenticationError("Định dạng PAT Key không hợp lệ. Token phải bắt đầu bằng 'vninvest_pat_'.")
            
        self.symbol = symbol
        self.gateway_url = gateway_url or os.getenv("VNBROKER_GATEWAY_URL", "https://api.vnstocks.com")
        self.show_log = show_log
        
        # Khởi tạo Gateway Client
        self._gateway_client = GatewayHttpClient(pat_key=self.pat_key, base_url=self.gateway_url)
```

### 5.2. Gateway Client tích hợp Fallback Throttling

```python
# file: vnbroker/core/utils/gateway_client.py

import time
import requests
import pandas as pd
from typing import Dict, Any
from vnbroker.core.exceptions import (
    AuthenticationError, 
    AuthorizationError, 
    QuotaExceededError, 
    ProviderError
)

class GatewayHttpClient:
    def __init__(self, pat_key: str, base_url: str):
        self.pat_key = pat_key
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.pat_key}",
            "Content-Type": "application/json",
            "User-Agent": "vnbroker-client-python/1.0.2"
        })
        self._emergency_calls_today = 0
        self._last_reset_time = time.time()

    def request(self, endpoint: str, method: str = "POST", json_data: Dict[str, Any] = None) -> Dict[str, Any]:
        # Reset rate limit khẩn cấp sau mỗi 24h
        if time.time() - self._last_reset_time > 86400:
            self._emergency_calls_today = 0
            self._last_reset_time = time.time()

        url = f"{self.base_url}{endpoint}"
        try:
            # Gửi request lên Gateway
            response = self.session.request(method, url, json=json_data, timeout=5.0)
            
            if response.status_code == 401:
                raise AuthenticationError("PAT Token không hợp lệ hoặc đã hết hạn.")
            elif response.status_code == 403:
                raise AuthorizationError("Token không có quyền (scope) thực hiện tác vụ này.")
            elif response.status_code == 429:
                raise QuotaExceededError("Hết hạn mức cuộc gọi trong ngày. Vui lòng nâng cấp gói để tiếp tục.")
                
            response.raise_for_status()
            return response.json()
            
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # Kích hoạt chế độ khẩn cấp (Gateway Down)
            return self._emergency_fallback(endpoint, json_data)

    def _emergency_fallback(self, endpoint: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        # Giới hạn cực nghiêm ngặt: Tối đa 10 cuộc gọi trực tiếp/ngày khi Gateway sập
        if self._emergency_calls_today >= 10:
            raise QuotaExceededError("Gateway hiện tại không khả dụng và bạn đã dùng hết hạn mức dự phòng khẩn cấp (10 calls/ngày).")
            
        self._emergency_calls_today += 1

        # Gọi trực tiếp qua các local explorer có sẵn (ví dụ: KBS, TCBS)
        # Bằng cách sử dụng các hàm cào dữ liệu gốc dưới client
        from vnbroker.core.dispatch import local_dispatch_fallback
        return local_dispatch_fallback(endpoint, json_data)
```

---

## 6. Lộ trình Triển khai & Chuyển đổi (Migration Path)

1. **Thử nghiệm Beta (Trial Period - 1 tháng)**:
   * Phát hành phiên bản beta giới hạn cho một nhóm nhỏ lập trình viên/đối tác.
   * Đo lường kỹ lưỡng tỷ lệ Cache Hit, độ trễ Gateway và tính ổn định của cụm Redis.
2. **Giai đoạn 1 (Thông báo deprecate)**:
   * Phát hành phiên bản `vnbroker` mới, in cảnh báo ra log khuyên dùng chế độ Gateway.
3. **Giai đoạn 2 (Tự động chuyển đổi)**:
   * Chuyển hướng mặc định sang sử dụng `DEFAULT_PAT` trên Gateway cho toàn bộ các cài đặt không khai báo key.
4. **Giai đoạn 3 (Hard cut-off)**:
   * Tắt hẳn luồng kết nối trực tiếp tự do. Toàn bộ người dùng phải dùng PAT của riêng mình hoặc PAT mặc định có hạn mức.

---

## 7. Khuyến nghị Tiếp theo
* **Hạ tầng HA**: Đầu tư thiết lập cluster cho Gateway (Multi-region, Load Balancer) để biến rủi ro Gateway Down thành cận 0%.
* **Beta Monitoring**: Triển khai Prometheus và Grafana trên server Gateway ngay trong tuần đầu tiên thử nghiệm để có cơ sở dữ liệu tinh chỉnh Quota tối ưu.
* **Trial Plan**: Cho phép dùng thử đầy đủ tính năng Pro trong vòng 14 ngày đầu tiên khi đăng ký tài khoản mới bằng Email.
