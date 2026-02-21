from app.routers.crud_factory import create_method_router
from app.models import DisbursementMethod

router = create_method_router("/api/disbursement-methods", "付款方式", DisbursementMethod, "付款方式")
