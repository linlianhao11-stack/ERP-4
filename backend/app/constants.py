"""业务常量定义 — 消除魔法字符串

str(Enum) 直接返回枚举值字符串，可作为 drop-in 替换使用。
例如: OrderType.CASH == "CASH" → True
"""
from enum import Enum


class OrderType(str, Enum):
    """销售订单类型"""
    CASH = "CASH"
    CREDIT = "CREDIT"
    CONSIGN_OUT = "CONSIGN_OUT"
    CONSIGN_SETTLE = "CONSIGN_SETTLE"
    RETURN = "RETURN"

    # 仅在财务导出/寄售汇总中出现
    CONSIGN_RETURN = "CONSIGN_RETURN"

    @classmethod
    def needs_warehouse(cls):
        """需要实体仓库的订单类型"""
        return [cls.CASH.value, cls.CREDIT.value, cls.CONSIGN_OUT.value]

    @classmethod
    def needs_customer(cls):
        """需要客户的订单类型"""
        return [cls.CASH.value, cls.CREDIT.value, cls.CONSIGN_OUT.value, cls.CONSIGN_SETTLE.value, cls.RETURN.value]

    @classmethod
    def shippable(cls):
        """支持发货操作的订单类型"""
        return [cls.CASH.value, cls.CREDIT.value, cls.CONSIGN_OUT.value]

    @classmethod
    def sales_types(cls):
        """计入销售额的订单类型（不含退货）"""
        return [cls.CASH.value, cls.CREDIT.value, cls.CONSIGN_SETTLE.value]

    @classmethod
    def credit_types(cls):
        """挂账类订单"""
        return [cls.CREDIT.value, cls.CONSIGN_SETTLE.value]


class ShippingStatus(str, Enum):
    """订单发货状态（Order.shipping_status）"""
    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ShipmentStatus(str, Enum):
    """物流单状态（Shipment.status）"""
    PENDING = "pending"
    SHIPPED = "shipped"
    SIGNED = "signed"
    CANCELLED = "cancelled"


class InvoiceStatus(str, Enum):
    """发票状态"""
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class BillStatus(str, Enum):
    """应收/应付单状态（ReceivableBill/PayableBill.status）"""
    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReceiptBillStatus(str, Enum):
    """收/付款单状态（ReceiptBill/DisbursementBill.status）"""
    DRAFT = "draft"
    CONFIRMED = "confirmed"


class VoucherStatus(str, Enum):
    """凭证状态"""
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    POSTED = "posted"


class PurchaseOrderStatus(str, Enum):
    """采购单状态"""
    PENDING_REVIEW = "pending_review"
    PENDING = "pending"
    PAID = "paid"
    PARTIAL = "partial"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentSource(str, Enum):
    """收款来源（Payment.source）"""
    CASH = "CASH"
    CREDIT = "CREDIT"
    REFUND = "REFUND"


class SnCodeStatus(str, Enum):
    """SN 码状态"""
    IN_STOCK = "in_stock"
    SHIPPED = "shipped"


class StockChangeType(str, Enum):
    """库存变动类型（StockLog.change_type）"""
    RESTOCK = "RESTOCK"
    SALE = "SALE"
    RETURN = "RETURN"
    CONSIGN_OUT = "CONSIGN_OUT"
    CONSIGN_SETTLE = "CONSIGN_SETTLE"
    CONSIGN_RETURN = "CONSIGN_RETURN"
    ADJUST = "ADJUST"
    PURCHASE_IN = "PURCHASE_IN"
    PURCHASE_RETURN = "PURCHASE_RETURN"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"
    RESERVE = "RESERVE"
    RESERVE_CANCEL = "RESERVE_CANCEL"


# 订单类型中文映射（用于日志、导出等显示场景）
ORDER_TYPE_NAMES = {
    OrderType.CASH: "现款",
    OrderType.CREDIT: "账期",
    OrderType.CONSIGN_OUT: "寄售调拨",
    OrderType.CONSIGN_SETTLE: "寄售结算",
    OrderType.CONSIGN_RETURN: "寄售退货",
    OrderType.RETURN: "退货",
}

# 库存变动类型中文映射
STOCK_CHANGE_TYPE_NAMES = {
    StockChangeType.RESTOCK: "入库",
    StockChangeType.SALE: "销售出库",
    StockChangeType.RETURN: "退货入库",
    StockChangeType.CONSIGN_OUT: "寄售调拨",
    StockChangeType.CONSIGN_SETTLE: "寄售结算",
    StockChangeType.CONSIGN_RETURN: "寄售退货",
    StockChangeType.ADJUST: "库存调整",
    StockChangeType.PURCHASE_IN: "采购入库",
    StockChangeType.PURCHASE_RETURN: "采购退货",
    StockChangeType.TRANSFER_OUT: "调拨出库",
    StockChangeType.TRANSFER_IN: "调拨入库",
    StockChangeType.RESERVE: "库存预留",
    StockChangeType.RESERVE_CANCEL: "取消预留",
}


# API 分页上限
MAX_PAGE_SIZE = 1000


# 锁层级文档（Phase 3.4 死锁防护）
# 获取行级锁时必须按此顺序，防止死锁：
# 1. Order (by order_id ASC)
# 2. OrderItem (by id ASC)
# 3. WarehouseStock (by warehouse_id ASC, product_id ASC)
# 4. Payment (by payment_id ASC)
