import os
import shutil
import sys
from pathlib import Path

os.environ["KIVY_NO_CONSOLELOG"] = "1"
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_WINDOW", "sdl2")

# ANGLE is available on Windows, but this machine renders a black frame with it.
# Default to the stable backend and allow overriding from the environment.
preferred_gl_backend = (
    os.environ.get("LATIBURONA_KIVY_GL_BACKEND")
    or os.environ.get("KIVY_GL_BACKEND")
    or "glew"
)
os.environ["KIVY_GL_BACKEND"] = preferred_gl_backend

from kivy.config import Config

Config.set("graphics", "multisamples", "0")
Config.set("graphics", "width", "1500")
Config.set("graphics", "height", "930")
Config.set("graphics", "minimum_width", "1200")
Config.set("graphics", "minimum_height", "760")
Config.set("graphics", "resizable", "1")
Config.set("graphics", "position", "auto")
Config.set("input", "mouse", "mouse,disable_multitouch")

def _clear_project_pycache() -> None:
    project_root = Path(__file__).resolve().parent
    for cache_dir in project_root.rglob("__pycache__"):
        try:
            shutil.rmtree(cache_dir, ignore_errors=True)
            print(f"REMOVED PYCACHE: {cache_dir}", flush=True)
        except Exception as exc:
            print(f"PYCACHE REMOVE ERROR: {cache_dir} -> {exc}", flush=True)


def main() -> None:
    print("RUNNING FROM:", os.getcwd(), flush=True)
    print("ENTRY POINT:", os.path.abspath(__file__), flush=True)
    print("PYTHON EXE:", sys.executable, flush=True)
    _clear_project_pycache()
    from app.bootstrap import build_services
    from kivy_ui import LaTiburonaApp

    services = build_services()
    LaTiburonaApp(services).run()


if __name__ == "__main__":
    main()
