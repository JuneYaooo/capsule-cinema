from src.logger import get_logger

logger = get_logger("douyin_utils")


def extract_douyin_reference(douyin_text, enable_transcript=True, enable_video_analysis=True, save_video=False):
    """Return user-provided reference text without platform crawling.

    The standalone douyin downloader/crawler is not bundled in this package.
    """
    del enable_transcript, enable_video_analysis, save_video
    if douyin_text:
        logger.warning("Douyin extraction is not bundled; using the provided text/URL as plain reference text.")
    return str(douyin_text or "")
