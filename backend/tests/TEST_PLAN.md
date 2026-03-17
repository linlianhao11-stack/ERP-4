# 测试扩展计划

## 当前覆盖 (147 tests)
- 模型测试: accounting, AR/AP, business flows
- 服务测试: accounting_init, period_end, ar_ap_service
- 认证测试: password hashing, strength validation

## 缺失测试（按优先级）

### P1: API 集成测试
- [ ] 订单创建完整流程 (CASH/CREDIT/RETURN)
- [ ] 支付确认 + 订单结清
- [ ] 发货确认 + 库存扣减
- [ ] 退货流程 + 库存恢复

### P2: 权限边界测试
- [ ] 非 admin 用户无法访问备份端点
- [ ] 普通用户无法修改其他用户权限
- [ ] account_set_id 隔离验证

### P3: 并发测试
- [ ] 同一商品并发下单不超卖
- [ ] 凭证号并发生成不重复
- [ ] 同一订单并发确认幂等

### P4: 边界测试
- [ ] 数量/金额为 0 或负数
- [ ] 超长字符串输入
- [ ] 不存在的 ID 访问
