from pathlib import Path
from django.conf import settings
from django.http import FileResponse, Http404


FRONTEND_DIR = settings.BASE_DIR.parent / "frontend"


def frontend(request, path="index.html"):
    file_path = FRONTEND_DIR / path

    if not file_path.is_file():
        raise Http404("Frontend file not found")

    return FileResponse(open(file_path, "rb"))