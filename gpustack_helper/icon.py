from PySide6.QtGui import QIcon, QPixmap
from gpustack_helper.defaults import icon_path


def create_disabled_icon(pixmap: QPixmap) -> QPixmap:
    image = pixmap.toImage()
    for x in range(image.width()):
        for y in range(image.height()):
            color = image.pixelColor(x, y)
            if color.alpha() > 0:
                color.setRgb(128, 128, 128, color.alpha())
                image.setPixelColor(x, y, color)
    return QPixmap.fromImage(image)


def create_white_icon(pixmap: QPixmap) -> QPixmap:
    image = pixmap.toImage()
    for x in range(image.width()):
        for y in range(image.height()):
            color = image.pixelColor(x, y)
            if color.alpha() > 0:
                color.setRgb(255, 255, 255, color.alpha())
                image.setPixelColor(x, y, color)
    return QPixmap.fromImage(image)


def get_icon(disabled: bool = False) -> QIcon:
    pixmap = QPixmap(icon_path)
    if disabled:
        pixmap = create_disabled_icon(pixmap)
    else:
        pixmap = create_white_icon(pixmap)
    icon = QIcon(pixmap)
    icon.setIsMask(not disabled)
    return icon
