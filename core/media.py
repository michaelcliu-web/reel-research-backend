import mimetypes
import os
import re

from django.conf import settings
from django.http import FileResponse, StreamingHttpResponse, HttpResponseNotFound, HttpResponseBadRequest

CHUNK_SIZE = 64 * 1024


def _read_range(path, start, length):
    """Yield exactly `length` bytes of the file starting at `start`."""
    with open(path, "rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


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

        response = StreamingHttpResponse(_read_range(full_path, start, length), status=206)
        response["Content-Type"] = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response["Content-Length"] = length
        response["Accept-Ranges"] = "bytes"
        return response

    response = FileResponse(open(full_path, "rb"))
    response["Content-Length"] = file_size
    response["Accept-Ranges"] = "bytes"
    return response
