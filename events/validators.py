import os

from django.core.exceptions import ValidationError

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".ogg"}

MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB


def classify_media_name(name):
    """Return 'image' or 'video' based on the file extension."""
    ext = os.path.splitext(name)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    raise ValidationError(f'"{name}" is not a supported image or video type.')


def validate_media_size(name, media_type, size):
    if media_type == "image" and size > MAX_IMAGE_SIZE:
        raise ValidationError(f'"{name}" is over the 5MB image limit.')
    if media_type == "video" and size > MAX_VIDEO_SIZE:
        raise ValidationError(f'"{name}" is over the 50MB video limit.')
