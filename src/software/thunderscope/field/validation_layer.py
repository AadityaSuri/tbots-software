import pyqtgraph as pg
import time
from proto.import_all_protos import *

from pyqtgraph.Qt import QtCore, QtGui

from software.thunderscope.constants import Colors
from software.py_constants import *
from software.networking.threaded_unix_listener import ThreadedUnixListener
from software.thunderscope.field.field_layer import FieldLayer
from software.thunderscope.thread_safe_buffer import ThreadSafeBuffer


class ValidationLayer(FieldLayer):

    PASSED_VALIDATION_PERSISTANCE_TIMEOUT_S = 1.0

    def __init__(self, buffer_size=10, test_name_pos_x=0, test_name_pos_y=3200):
        """Visualizes validation

        :param buffer_size: The buffer size, set higher for smoother plots.
                            Set lower for more realtime plots. Default is arbitrary
        :param test_name_pos_x: The x position of the test name
        :param test_name_pos_y: The y position of the test name

        """
        FieldLayer.__init__(self)

        # Validation protobufs are generated by simulated tests
        self.validation_set_buffer = ThreadSafeBuffer(buffer_size, ValidationProtoSet)
        self.cached_eventually_validation_set = ValidationProtoSet()
        self.cached_always_validation_set = ValidationProtoSet()

        self.test_name = pg.TextItem("")
        self.test_name.setParentItem(self)
        self.test_name.setPos(test_name_pos_x, test_name_pos_y)

        self.passed_validation_timeout_pairs = []

    def draw_validation(self, painter, validation):
        """Draw Validation

        :param painter: The painter object to draw with
        :param validation: Validation proto

        """
        if validation.status == ValidationStatus.PASSING:
            painter.setPen(pg.mkPen(Colors.VALIDATION_PASSED_COLOR, width=3))

        if validation.status == ValidationStatus.FAILING:
            painter.setPen(pg.mkPen(Colors.VALIDATION_FAILED_COLOR, width=3))

        for circle in validation.geometry.circles:
            painter.drawEllipse(self.createCircle(circle.origin, circle.radius))

        for polygon in validation.geometry.polygons:
            polygon_points = [
                QtCore.QPoint(
                    int(MILLIMETERS_PER_METER * point.x_meters),
                    int(MILLIMETERS_PER_METER * point.y_meters),
                )
                for point in polygon.points
            ]

            poly = QtGui.QPolygon(polygon_points)
            painter.drawPolygon(poly)

        for segment in validation.geometry.segments:
            painter.drawLine(
                QtCore.QLine(
                    int(segment.start.x_meters),
                    int(segment.start.y_meters),
                    int(segment.end.x_meters),
                    int(segment.end.y_meters),
                )
            )

    def paint(self, painter, option, widget):
        """Paint this layer

        :param painter: The painter object to draw with
        :param option: Style information (unused)
        :param widget: The widget that we are painting on

        """

        # Consume the validation set buffer
        for _ in range(self.validation_set_buffer.queue.qsize()):
            self.validation_set = self.validation_set_buffer.get()

            if self.validation_set.validation_type == ValidationType.ALWAYS:
                self.cached_always_validation_set = self.validation_set
            else:
                self.cached_eventually_validation_set = self.validation_set

        # Draw test name
        if (
            self.test_name.toPlainText()
            != self.cached_eventually_validation_set.test_name
        ):
            self.test_name.setText(self.cached_eventually_validation_set.test_name)

        # Draw Always Validation
        for validation in self.cached_always_validation_set.validations:
            self.draw_validation(painter, validation)

        # Draw Eventually Validation
        for validation in self.cached_eventually_validation_set.validations:
            if validation.status == ValidationStatus.PASSING:
                self.passed_validation_timeout_pairs.append(
                    (
                        validation,
                        time.time()
                        + ValidationLayer.PASSED_VALIDATION_PERSISTANCE_TIMEOUT_S,
                    )
                )

            self.draw_validation(painter, validation)

        # Draw cached validation
        for validation, stop_drawing_time in list(self.passed_validation_timeout_pairs):
            if time.time() < stop_drawing_time:
                self.draw_validation(painter, validation)
            else:
                self.passed_validation_timeout_pairs.remove(
                    (validation, stop_drawing_time)
                )
