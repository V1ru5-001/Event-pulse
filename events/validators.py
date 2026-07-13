import os

from django.core.exceptions import ValidationError

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".ogg"}

MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB


def classify_and_validate_media(uploaded_file):
    """Classify a gallery upload as 'image' or 'video', enforcing size limits.

    Raises ValidationError for unsupported types or oversized files.
    """
    ext = os.path.splitext(uploaded_file.name)[1].lower()

    if ext in IMAGE_EXTENSIONS:
        if uploaded_file.size > MAX_IMAGE_SIZE:
            raise ValidationError(f'"{uploaded_file.name}" is over the 5MB image limit.')
        return "image"

    if ext in VIDEO_EXTENSIONS:
        if uploaded_file.size > MAX_VIDEO_SIZE:
            raise ValidationError(f'"{uploaded_file.name}" is over the 50MB video limit.')
        return "video"

    raise ValidationError(f'"{uploaded_file.name}" is not a supported image or video type.')