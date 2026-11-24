import cv2
import numpy as np
import pytest
from media import analyze_image, image_report, validate_image, MAX_IMAGE_BYTES


def test_image_analysis_reports_measured_properties():
    image = np.full((80, 120, 3), (50, 90, 160), dtype=np.uint8)
    good, encoded = cv2.imencode('.png', image)
    assert good
    result = analyze_image(encoded.tobytes())
    assert result['width'] == 120
    assert result['height'] == 80
    assert 0 <= result['brightness'] <= 255
    assert 'Local image inspection' in image_report(result)


def test_invalid_image_fails_cleanly():
    with pytest.raises(ValueError):
        analyze_image(b'not an image')


def test_validate_image_accepts_png_and_rejects_type_and_size():
    image = np.zeros((20, 30, 3), dtype=np.uint8)
    good, encoded = cv2.imencode('.png', image)
    assert good
    data = encoded.tobytes()
    assert validate_image(data, 'image/png', 'scene.png') == 'image/png'
    with pytest.raises(ValueError, match='Unsupported image type'):
        validate_image(data, 'image/gif', 'scene.gif')
    with pytest.raises(ValueError, match='no larger than 8 MB'):
        validate_image(b'x' * (MAX_IMAGE_BYTES + 1), 'image/png', 'large.png')
