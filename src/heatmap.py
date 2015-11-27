from abc import ABCMeta, abstractmethod
import io
import os
import random

from matplotlib.colors import LinearSegmentedColormap
import numpy
from PIL import Image
from PySide import QtCore, QtGui


class Heatmapper:
    def __init__(self, point_diameter=50, alpha_strength=0.2, opacity=0.65,
                 colours='default',
                 grey_heatmapper='PySide'):
        """
        :param opacity: opacity (between 0 and 1) of the generated heatmap overlay
        :param colours: Either 'default', 'reveal',
                        OR the path to horizontal image which will be converted to a scale
                        OR a matplotlib LinearSegmentedColorMap instance.
        :param grey_heatmapper: Required to draw points on an image as a greyscale
                                heatmap. If not using the default, this must be an object
                                which fulfils the GreyScaleHeatmap interface.
        """

        self._opacity = opacity

        if isinstance(colours, LinearSegmentedColormap):
            self.cmap = colours
        else:
            local_file = lambda file: os.path.join(os.path.dirname(__file__), file)
            files = {
                'default': local_file('default.png'),
                'reveal': local_file('reveal.png'),
            }
            scale_path = files.get(colours) or colours
            self.cmap = self._cmap_from_image_path(scale_path)

        if grey_heatmapper == 'PySide':
            self.grey_heatmapper = PySideGreyHeatmapper(point_diameter, alpha_strength)
        else:
            self.grey_heatmapper = grey_heatmapper

    def heatmap(self, width, height, points, base_path=None, base_img=None):
        """
        :param points: sequence of tuples of (x, y), eg [(9, 20), (7, 3), (19, 12)]
        :return: If base_path of base_img provided, a heat map from the given points
                 is overlayed on the image. Otherwise, the heat map alone is returned
                 with a transparent background.
        """
        heatmap = self.grey_heatmapper.heatmap(width, height, points)
        heatmap = self._colourise(heatmap)
        heatmap = self._to_opacity(heatmap, self._opacity)

        if not (base_path or base_img):
            return heatmap

        background = Image.open(base_path) if base_path else base_img
        return Image.alpha_composite(background.convert('RGBA'), heatmap)

    @staticmethod
    def _cmap_from_image_path(img_path):
        img = Image.open(img_path)
        img = img.resize((256, img.height))
        colours = (img.getpixel((x, 0)) for x in range(256))
        colours = [(r/255, g/255, b/255, a/255) for (r, g, b, a) in colours]
        return LinearSegmentedColormap.from_list('from_image', colours)

    def heatmap_on_base_path(self, points, base_path):
        width, height = Image.open(base_path).size
        return self.heatmap(width, height, points, base_path=base_path)

    def heatmap_on_img(self, points, img):
        width, height = img.size
        return self.heatmap(width, height, points, base_img=img)

    def _colourise(self, img):
        """ maps values in greyscale image to colours """
        arr = numpy.array(img)
        rgba_img = self.cmap(arr, bytes=True)
        return Image.fromarray(rgba_img)

    @staticmethod
    def _to_opacity(img, opacity):
        img = img.copy()
        alpha = img.split()[3]
        alpha = alpha.point(lambda p: int(p * opacity))
        img.putalpha(alpha)
        return img


class GreyHeatMapper(metaclass=ABCMeta):
    @abstractmethod
    def __init__(self, point_diameter, point_strength):
        self.dm = point_diameter
        self.point_strength = point_strength

    @abstractmethod
    def heatmap(self, width, height, points):
        """
        :param points: sequence of tuples of (x, y), eg [(9, 20), (7, 3), (19, 12)]
        :return: a white image of size width x height with black areas painted at
                 the given points
        """
        pass


class PySideGreyHeatmapper(GreyHeatMapper):
    def __init__(self, point_diameter, point_strength):
        super().__init__(point_diameter, point_strength)
        self.point_strength = int(point_strength * 255)

    def heatmap(self, width, height, points):
        base_image = QtGui.QImage(width, height, QtGui.QImage.Format_ARGB32)
        base_image.fill(QtGui.QColor(255, 255, 255, 255))

        self._paint_points(base_image, points)
        return self._qimage_to_pil_image(base_image).convert('L')

    def _paint_points(self, img, points):
        painter = QtGui.QPainter(img)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        for point in points:
            self._paint_point(point, painter)
        painter.end()

    def _paint_point(self, point, painter):
        pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 0))
        pen.setWidth(0)
        painter.setPen(pen)

        x, y = point

        grad = QtGui.QRadialGradient(x, y, self.dm/2)
        grad.setColorAt(0, QtGui.QColor(0, 0, 0, max(self.point_strength, 0)))
        grad.setColorAt(1, QtGui.QColor(0, 0, 0, 0))
        brush = QtGui.QBrush(grad)
        painter.setBrush(brush)
        painter.drawEllipse(x - self.dm/2, y - self.dm/2, self.dm, self.dm)

    @staticmethod
    def _qimage_to_pil_image(qimg):
        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.ReadWrite)
        qimg.save(buffer, "PNG")

        bytes_io = io.BytesIO()
        bytes_io.write(buffer.data().data())
        buffer.close()
        bytes_io.seek(0)
        return Image.open(bytes_io)


if __name__ == '__main__':
    randpoint = lambda max_x, max_y: (random.randint(0, max_x), random.randint(0, max_y))
    example_img = Image.open('home-cat.jpg')
    example_points = (randpoint(*example_img.size) for _ in range(300))

    heatmapper = Heatmapper(colours='reveal')
    heatmapper.heatmap_on_img(example_points, example_img).save('drawn.png')