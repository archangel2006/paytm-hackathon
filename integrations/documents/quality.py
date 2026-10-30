"""
Image quality checks – blur detection using variance of Laplacian.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from integrations import settings

logger = logging.getLogger(__name__)


def load_and_preprocess(file_path: str, max_width: int = 1600) -> np.ndarray | None:
    """Load an image with OpenCV, resize if wider than ``max_width``, return grayscale."""
    img = cv2.imread(file_path)
    if img is None:
        logger.warning("Could not load image: %s", file_path)
        return None

    h, w = img.shape[:2]
    if w > max_width:
        scale = max_width / w
        img = cv2.resize(img, (max_width, int(h * scale)))

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return gray


def blur_score(gray: np.ndarray) -> float:
    """Return the variance of the Laplacian – higher means sharper."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def is_blurry(gray: np.ndarray, threshold: float | None = None) -> bool:
    """Return True if the image is too blurry."""
    thresh = threshold if threshold is not None else settings.BLUR_THRESHOLD
    score = blur_score(gray)
    logger.debug("Blur score: %.2f (threshold: %.2f)", score, thresh)
    return score < thresh
