from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.backend.db import SessionLocal, init_db
from app.backend.services.auth_service import ADMIN_EMAIL, reset_admin_user, serialize_user


def main() -> int:
    admin_password = os.getenv("LATIBURONA_ADMIN_PASSWORD", "").strip()
    if not admin_password:
        print("LATIBURONA_ADMIN_PASSWORD no esta configurada. No se realizo ningun cambio.", file=sys.stderr)
        return 1

    init_db()
    with SessionLocal() as session:
        user = reset_admin_user(session, admin_password)
        payload = serialize_user(user)

    print("Admin sincronizado correctamente:")
    print(f"  email: {payload['email']}")
    print(f"  display_name: {payload['display_name']}")
    print(f"  full_name: {payload['full_name']}")
    print(f"  is_admin: {payload['is_admin']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
