import os
import re

from django.conf import settings
from django.http import FileResponse, HttpResponseNotFound, HttpResponseBadRequest


def serve_media(request, path):
    """Serve media files with HTTP Range request support so video seeking works."""
    media_root = os.path.realpath(settings.MEDIA_ROOT)
    full_path = os.path.realpath(os.path.join(media_root, path))
    if os.path.commonpath([media_root, full_path]) != media_root or not os.path.isfile(full_path):
        return HttpResponseNotFound()

    file_size = os.path.getsize(full_path)
    range_header = request.META.get("HTTP_RANGE")

    if range_header:
        match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if not match:
            return HttpResponseBadRequest()
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        f = open(full_path, "rb")
        f.seek(start)
        response = FileResponse(f, status=206)
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response["Content-Length"] = length
        response["Accept-Ranges"] = "bytes"
        return response

    response = FileResponse(open(full_path, "rb"))
    response["Content-Length"] = file_size
    response["Accept-Ranges"] = "bytes"
    return response
