"""Test package marker.

Cần để pytest phân biệt các file trùng basename ở khác thư mục
(vd test_quote.py có ở cả tests/unit/explorer và tests/integration/explorer).
Thiếu file này -> "import file mismatch" và cả collection fail.
"""
