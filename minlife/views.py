from django.conf import settings
from django.http import FileResponse

def favicon(request):
    file = (settings.BASE_DIR / "favicon.ico").open("rb")
    return FileResponse(file)
