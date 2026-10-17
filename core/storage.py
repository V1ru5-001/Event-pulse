import logging

from django.core.files.storage import FileSystemStorage
from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class ForgivingStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    WhiteNoise's hashed static storage, except that a {% static %} reference to
    a file that doesn't exist links to the plain path (the browser gets a 404
    for that one file) instead of raising and turning the whole page into a 500.
    """

    def url(self, name, force=False):
        try:
            return super().url(name, force)
        except ValueError:
            logger.warning('Static file not found: %s', name)
            return FileSystemStorage.url(self, name)
