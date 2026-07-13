import mimetypes
import os
import re

from django.conf import settings
from django.http import FileResponse, HttpResponse, HttpResponseNotFound
from django.utils._os import safe_join

RANGE_RE = re.compile(r"bytes\s*=\s*(\d+)-(\d*)", re.I)
CHUNK_SIZE = 8192


def serve_media(request, path):
    """Dev-only media file server with HTTP Range support.

    Browsers need Range requests to seek into <video>/<audio> files — without
    it they can fail to locate the moov atom (common in phone-recorded MP4s
    where it sits at the end of the file) and silently drop the audio track
    even though frames keep rendering. Django's default FileResponse doesn't
    implement Range at all, so this fills that gap for local development.
    """
    try:
        full_path = safe_join(settings.MEDIA_ROOT, path)
    except ValueError:
        return HttpResponseNotFound()

    if not os.path.isfile(full_path):
        return HttpResponseNotFound()

    file_size = os.path.getsize(full_path)
    content_type, _ = mimetypes.guess_type(full_path)
    content_type = content_type or "application/octet-stream"

    range_match = RANGE_RE.match(request.META.get("HTTP_RANGE", ""))
    if not range_match:
        response = FileResponse(open(full_path, "rb"), content_type=content_type)
        response["Accept-Ranges"] = "bytes"
        return response

    start = int(range_match.group(1))
    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
    end = min(end, file_size - 1)

    if start > end or start >= file_size:
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{file_size}"
        return response

    length = end - start + 1

    def stream():
        with open(full_path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    response = HttpResponse(stream(), status=206, content_type=content_type)
    response["Content-Length"] = str(length)
    response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    response["Accept-Ranges"] = "bytes"
    return response
