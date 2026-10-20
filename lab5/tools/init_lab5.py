"""Create local LR5 secrets once; do not replace keys while sessions exist."""
from pathlib import Path
import secrets


target = Path(__file__).resolve().parents[1] / ".env.lab5"
if target.exists():
    print(f"Existing local configuration retained: {target}")
else:
    target.write_text(
        "LAB5_DB_PASSWORD=" + secrets.token_hex(20) + "\n"
        "LAB5_REDIS_PASSWORD=" + secrets.token_hex(20) + "\n"
        "LAB5_JWT_SECRET=" + secrets.token_hex(40) + "\n"
        "LAB5_PGADMIN_PASSWORD=" + secrets.token_hex(16) + "\n",
        encoding="utf-8",
    )
    print(f"Created local configuration: {target}")
