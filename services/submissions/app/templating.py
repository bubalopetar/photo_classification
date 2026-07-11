from pathlib import Path

from starlette.templating import Jinja2Templates

from app.config import settings

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
# The home page (welcome + submissions list) lives on the Auth service.
templates.env.globals["home_url"] = f"{settings.auth_public_url}/"
