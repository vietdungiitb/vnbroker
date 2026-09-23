# SSI live-confirm checklist (MANUAL — chạy tay, ký xác nhận từng mục)

Chạy: `vnbroker_RUN_LIVE_INTEGRATION=1 pytest tests/integration/broker/test_ssi_live.py -v`
Yêu cầu: creds thật (`VNBROKER_BROKER_SSI_API_KEY/SECRET`), OTP người thật,
`VNBROKER_BROKER_SSI_ACCOUNT_NO` cho write-test.

- [ ] 1. WS URL thực tế `wss://stream.ssi.com.vn/ws/v3` (connect + subscribe thành công)
- [ ] 2. price ép `str` trên wire được server chấp nhận (place LO thật → hủy ngay)
- [ ] 3. nanoid length-20 `clientRequestId` được server chấp nhận
- [ ] 4. pending 202/code 401114 khi Smart OTP chưa approve (nếu có thiết bị)
- [ ] 5. cả 3 OTP flows: market-only (không OTP) / otp / transaction_id
- [ ] 6. `From`/`To` hoa ở masterdata (test_master_data_caps xanh)
- [ ] 7. wildcard `"*"` cho order/portfolio subscribe
- [ ] 8. `clientId` chỉ gửi ở balance/positions (orderBook/maxBuySell/FCO-list không gửi)

Xác nhận: _______________  Ngày: _______________
