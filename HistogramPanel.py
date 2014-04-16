# standard libraries
import gettext

# third party libraries
# None

# local libraries
from nion.swift import Panel
from nion.ui import CanvasItem
from nion.ui import ThreadPool

_ = gettext.gettext


class AdornmentsCanvasItem(CanvasItem.AbstractCanvasItem):

    def __init__(self):
        super(AdornmentsCanvasItem, self).__init__()
        self.display_limits = (0,1)

    def _repaint(self, drawing_context):

        # canvas size
        canvas_width = self.canvas_size[1]
        canvas_height = self.canvas_size[0]

        left = self.display_limits[0]
        right = self.display_limits[1]

        # draw left display limit
        drawing_context.save()
        drawing_context.begin_path()
        drawing_context.move_to(left * canvas_width, 1)
        drawing_context.line_to(left * canvas_width, canvas_height-1)
        drawing_context.line_width = 2
        drawing_context.stroke_style = "#000"
        drawing_context.stroke()
        drawing_context.restore()

        # draw right display limit
        drawing_context.save()
        drawing_context.begin_path()
        drawing_context.move_to(right * canvas_width, 1)
        drawing_context.line_to(right * canvas_width, canvas_height-1)
        drawing_context.line_width = 2
        drawing_context.stroke_style = "#FFF"
        drawing_context.stroke()
        drawing_context.restore()

        # draw border
        drawing_context.save()
        drawing_context.begin_path()
        drawing_context.move_to(0,0)
        drawing_context.line_to(canvas_width,0)
        drawing_context.line_to(canvas_width,canvas_height)
        drawing_context.line_to(0,canvas_height)
        drawing_context.close_path()
        drawing_context.line_width = 1
        drawing_context.stroke_style = "#000"
        drawing_context.stroke()
        drawing_context.restore()


class SimpleLineGraphCanvasItem(CanvasItem.AbstractCanvasItem):

    def __init__(self):
        super(SimpleLineGraphCanvasItem, self).__init__()
        self.__data = None
        self.__background_color = None

    def __get_data(self):
        return self.__data
    def __set_data(self, data):
        self.__data = data
        self.update()
    data = property(__get_data, __set_data)

    def __get_background_color(self):
        return self.__background_color
    def __set_background_color(self, background_color):
        self.__background_color = background_color
        self.update()
    background_color = property(__get_background_color, __set_background_color)

    def _repaint(self, drawing_context):

        # canvas size
        canvas_width = self.canvas_size[1]
        canvas_height = self.canvas_size[0]

        # draw background
        if self.background_color:
            drawing_context.save()
            drawing_context.begin_path()
            drawing_context.move_to(0,0)
            drawing_context.line_to(canvas_width,0)
            drawing_context.line_to(canvas_width,canvas_height)
            drawing_context.line_to(0,canvas_height)
            drawing_context.close_path()
            drawing_context.fill_style = self.background_color
            drawing_context.fill()
            drawing_context.restore()

        # draw the data, if any
        if (self.data is not None and len(self.data) > 0):

            # draw the histogram itself
            drawing_context.save()
            drawing_context.begin_path()
            drawing_context.move_to(0, canvas_height)
            drawing_context.line_to(0, canvas_height * (1 - self.data[0]))
            for i in xrange(1,canvas_width,2):
                drawing_context.line_to(i, canvas_height * (1 - self.data[int(len(self.data)*float(i)/canvas_width)]))
            drawing_context.line_to(canvas_width, canvas_height)
            drawing_context.close_path()
            drawing_context.fill_style = "#888"
            drawing_context.fill()
            drawing_context.line_width = 1
            drawing_context.stroke_style = "#00F"
            drawing_context.stroke()
            drawing_context.restore()


class HistogramCanvasItem(CanvasItem.CanvasItemComposition):

    def __init__(self):
        super(HistogramCanvasItem, self).__init__()
        self.adornments_canvas_item = AdornmentsCanvasItem()
        self.simple_line_graph_canvas_item = SimpleLineGraphCanvasItem()
        # canvas items get added back to front
        self.add_canvas_item(self.simple_line_graph_canvas_item)
        self.add_canvas_item(self.adornments_canvas_item)
        self.__display = None
        self.__pressed = False

        self.__shared_thread_pool = ThreadPool.create_thread_queue()

        self.preferred_aspect_ratio = 1.618  # golden ratio

    def close(self):
        self.__shared_thread_pool.close()
        self.__shared_thread_pool = None
        self.update_display(None)
        super(HistogramCanvasItem, self).close()

    # pass this along to the simple line graph canvas item
    def __get_background_color(self):
        return self.simple_line_graph_canvas_item.background_color
    def __set_background_color(self, background_color):
        self.simple_line_graph_canvas_item.background_color = background_color
    background_color = property(__get_background_color, __set_background_color)

    # _get_display is only used for testing
    def _get_display(self):
        return self.__display
    def _set_display(self, display):
        # this will get invoked whenever the data item changes. it gets invoked
        # from the histogram thread which gets triggered via the display_updated method.
        self.__display = display
        # if the user is currently dragging the display limits, we don't want to update
        # from changing data at the same time. but we _do_ want to draw the updated data.
        if not self.__pressed:
            self.adornments_canvas_item.display_limits = (0, 1)
        # this will get called twice: once with the initial return values
        # and once with the updated return values once the thread completes.
        def update_histogram_data(histogram_data):
            self.simple_line_graph_canvas_item.data = histogram_data
            self.adornments_canvas_item.update()
        histogram_data = self.__display.get_processed_data("histogram", None, completion_fn=update_histogram_data) if self.__display else None
        update_histogram_data(histogram_data)

    # TODO: histogram gets updated unnecessarily when dragging graphic items
    def update_display(self, display):
        if self.__shared_thread_pool and display:
            def update_histogram_data_on_thread():
                self._set_display(display)
            # note: display is passed to add_task to keep a reference until task finishes.
            self.__shared_thread_pool.add_task("update-histogram-data", display, lambda: update_histogram_data_on_thread())

    def __set_display_limits(self, display_limits):
        self.adornments_canvas_item.display_limits = display_limits
        self.adornments_canvas_item.update()

    def mouse_double_clicked(self, x, y, modifiers):
        if super(HistogramCanvasItem, self).mouse_double_clicked(x, y, modifiers):
            return True
        self.__set_display_limits((0, 1))
        if self.__display:
            self.__display.display_limits = None
        return True

    def mouse_pressed(self, x, y, modifiers):
        if super(HistogramCanvasItem, self).mouse_pressed(x, y, modifiers):
            return True
        self.__pressed = True
        self.start = float(x)/self.canvas_size[1]
        self.__set_display_limits((self.start, self.start))
        return True

    def mouse_released(self, x, y, modifiers):
        if super(HistogramCanvasItem, self).mouse_released(x, y, modifiers):
            return True
        self.__pressed = False
        display_limit_range = self.adornments_canvas_item.display_limits[1] - self.adornments_canvas_item.display_limits[0]
        if self.__display and (display_limit_range > 0) and (display_limit_range < 1):
            data_min, data_max = self.__display.display_range
            lower_display_limit = data_min + self.adornments_canvas_item.display_limits[0] * (data_max - data_min)
            upper_display_limit = data_min + self.adornments_canvas_item.display_limits[1] * (data_max - data_min)
            self.__display.display_limits = (lower_display_limit, upper_display_limit)
        return True

    def mouse_position_changed(self, x, y, modifiers):
        if super(HistogramCanvasItem, self).mouse_position_changed(x, y, modifiers):
            return True
        canvas_width = self.canvas_size[1]
        if self.__pressed:
            current = float(x)/canvas_width
            self.__set_display_limits((min(self.start, current), max(self.start, current)))
        return True


class HistogramPanel(Panel.Panel):

    def __init__(self, document_controller, panel_id, properties):
        super(HistogramPanel, self).__init__(document_controller, panel_id, _("Histogram"))

        self.data_item_binding = document_controller.create_selected_data_item_binding()

        self.root_canvas_item = CanvasItem.RootCanvasItem(document_controller.ui, properties={"min-height": 80, "max-height": 80})
        self.histogram_canvas_item = HistogramCanvasItem()
        self.root_canvas_item.add_canvas_item(self.histogram_canvas_item)

        self.stats_column1 = self.ui.create_column_widget(properties={"min-width": 140, "max-width": 140})
        self.stats_column2 = self.ui.create_column_widget(properties={"min-width": 140, "max-width": 140})
        self.stats_column1_label = self.ui.create_label_widget()
        self.stats_column2_label = self.ui.create_label_widget()
        self.stats_column1.add(self.stats_column1_label)
        self.stats_column1.add_stretch()
        self.stats_column2.add(self.stats_column2_label)
        self.stats_column2.add_stretch()

        stats_section = self.ui.create_row_widget(properties={"spacing": 6})
        stats_section.add_spacing(13)
        stats_section.add(self.stats_column1)
        stats_section.add_stretch()
        stats_section.add(self.stats_column2)
        stats_section.add_spacing(13)

        column = self.ui.create_column_widget(properties={"min-height": 18 * 3, "max-height": 18 * 3})
        column.add(self.root_canvas_item.canvas)
        column.add_spacing(6)
        column.add(stats_section)
        column.add_spacing(6)

        self.widget = column

        # connect self as listener. this will result in calls to data_item_binding_display_changed
        self.data_item_binding.add_listener(self)
        # initial data item changed message
        self.data_item_binding_display_changed(self.data_item_binding.display)

    def close(self):
        self.root_canvas_item.close()
        # disconnect data item binding
        self.data_item_binding_display_changed(None)
        self.data_item_binding.remove_listener(self)
        self.data_item_binding.close()
        super(HistogramPanel, self).close()

    # this message is received from the data item binding.
    def data_item_binding_display_changed(self, display):
        def update_statistics(statistics_data):
            statistic_strs = list()
            for key in sorted(statistics_data.keys()):
                statistic_str = "{0} {1:n}".format(key, statistics_data[key])
                statistic_strs.append(statistic_str)
            self.stats_column1_label.text = "\n".join(statistic_strs[:(len(statistic_strs)+1)/2])
            self.stats_column2_label.text = "\n".join(statistic_strs[(len(statistic_strs)+1)/2:])
        def update_statistics_data(statistics_data):
            self.add_task("statistics", lambda: update_statistics(statistics_data))
        self.histogram_canvas_item.update_display(display)
        statistics_data = display.get_processed_data("statistics", None, completion_fn=update_statistics_data) if display else dict()
        update_statistics_data(statistics_data)
