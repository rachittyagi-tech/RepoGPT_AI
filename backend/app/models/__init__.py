"""
app/models/__init__.py

Every ORM model MUST be imported here. `app.database.base.Base.metadata`
only knows about classes that have actually been imported somewhere —
Alembic's `env.py` imports this package specifically so `--autogenerate`
can see every table. It also resolves the string-based relationship()
forward-refs in `user.py` / `session.py` by ensuring both classes are
registered on the same mapper registry before first use.
"""

from app.models.session import LoginSession, RefreshToken
from app.models.user import User, UserRole

__all__ = ["User", "UserRole", "RefreshToken", "LoginSession"]
