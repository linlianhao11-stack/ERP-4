from app.routers.crud_factory import create_method_router
from app.models import PaymentMethod

router = create_method_router("/api/payment-methods", "收款方式", PaymentMethod, "收款方式")
