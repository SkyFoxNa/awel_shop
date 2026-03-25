from .start import router as start_router
from .common import router as common_router
from .product_search import router as product_search_router
from .profile import router as profile_router
from .admin_users import router as admin_users_router
from .admin_promos import router as admin_promos_router
# from .admin_shares import router as admin_shares_router
from .user_promos import router as user_promos_router
from .errors import router as errors_router
from .unknown_message import router as unknown_message_router

routers = [
    start_router,
    common_router,
    product_search_router,
    profile_router,
    admin_users_router,
    admin_promos_router,
    # admin_shares_router,
    user_promos_router,
    errors_router, # Завжди перед останній!
    unknown_message_router # Завжди останній!
]
