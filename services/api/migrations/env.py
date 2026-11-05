import os

from alembic import context
from sqlalchemy import create_engine

from app.core.db import Base
from app.modules.carts import models as cart_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.menu import models as menu_models  # noqa: F401
from app.modules.orders import models as order_models  # noqa: F401
from app.modules.payments import models as payment_models  # noqa: F401
from app.modules.reviews import models as review_models  # noqa: F401

url = os.environ["DATABASE_URL"]
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(url).connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
