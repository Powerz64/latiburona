import os
import shutil
import sys


def _project_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _runtime_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return _project_dir()


def _resource_dir(base_dir: str) -> str:
    if getattr(sys, "frozen", False):
        return os.path.abspath(getattr(sys, "_MEIPASS", base_dir))
    return base_dir


BASE_DIR = _runtime_base_dir()
RESOURCE_DIR = _resource_dir(BASE_DIR)
DATABASE_TEMPLATE_PATH = os.path.join(RESOURCE_DIR, "database.db")
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")


def ensure_database_file() -> str:
    if os.path.exists(DATABASE_PATH):
        return DATABASE_PATH

    if os.path.exists(DATABASE_TEMPLATE_PATH):
        shutil.copy2(DATABASE_TEMPLATE_PATH, DATABASE_PATH)

    return DATABASE_PATH


def ensure_exports_dir() -> str:
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    return EXPORTS_DIR


def export_file_path(filename: str) -> str:
    ensure_exports_dir()
    return os.path.join(EXPORTS_DIR, os.path.basename(filename))
