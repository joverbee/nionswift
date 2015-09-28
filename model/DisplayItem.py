# futures
from __future__ import absolute_import

# standard libraries
import gettext

# third party libraries
# None

# local libraries
from nion.ui import Event

_ = gettext.gettext


class DisplayItem(object):
    """ Provide a simplified interface to a data item for the purpose of display.

        There is typically one display item associated with each data item.

        Provides the following interface:
            (method) close()
            (property, read-only) thumbnail
            (property, read-only) title_str
            (property, read-only) datetime_str
            (property, read-only) format_str
            (property, read-only) status_str
            (method) get_mime_data()
            (method) drag_started(x, y, modifiers), returns mime_data, thumbnail_data
    """

    def __init__(self, data_item, dispatch_task, ui):
        self.data_item = data_item
        self.dispatch_task = dispatch_task
        self.ui = ui
        self.needs_update_event = Event.Event()

        def data_item_content_changed(changes):
            self.needs_update_event.fire()

        self.__data_item_content_changed_event_listener = data_item.data_item_content_changed_event.listen(data_item_content_changed)
        # grab the display specifier and if there is a display, handle thumbnail updating.
        display_specifier = data_item.primary_display_specifier
        display = display_specifier.display
        if display:

            def display_processor_needs_recompute(processor):
                if processor == display.get_processor("thumbnail"):
                    processor.recompute_if_necessary(self.dispatch_task, self.ui)

            def display_processor_data_updated(processor):
                if processor == display.get_processor("thumbnail"):
                    self.needs_update_event.fire()

            self.__display_processor_needs_recompute_event_listener = display.display_processor_needs_recompute_event.listen(display_processor_needs_recompute)
            self.__display_processor_data_updated_event_listener = display.display_processor_data_updated_event.listen(display_processor_data_updated)

    def close(self):
        # remove the listener.
        display_specifier = self.data_item.primary_display_specifier
        if display_specifier.display:
            self.__display_processor_needs_recompute_event_listener.close()
            self.__display_processor_data_updated_event_listener.close()
            self.__display_processor_needs_recompute_event_listener = None
            self.__display_processor_data_updated_event_listener = None
        self.__data_item_content_changed_event_listener.close()
        self.__data_item_content_changed_event_listener = None

    @property
    def thumbnail(self):
        display = self.data_item.primary_display_specifier.display
        if display:
            display.get_processor("thumbnail").recompute_if_necessary(self.dispatch_task, self.ui)
            return display.get_processed_data("thumbnail")
        return None

    @property
    def title_str(self):
        data_item = self.data_item
        return data_item.displayed_title

    @property
    def format_str(self):
        data_item = self.data_item
        display_specifier = data_item.primary_display_specifier
        buffered_data_source = display_specifier.buffered_data_source
        if buffered_data_source:
            data_and_calibration = buffered_data_source.data_and_calibration
            if data_and_calibration:
                return data_and_calibration.size_and_data_format_as_string
        return str()

    @property
    def datetime_str(self):
        data_item = self.data_item
        return data_item.date_for_sorting_local_as_string

    @property
    def status_str(self):
        data_item = self.data_item
        if data_item.is_live:
            display_specifier = data_item.primary_display_specifier
            buffered_data_source = display_specifier.buffered_data_source
            if buffered_data_source:
                data_and_calibration = buffered_data_source.data_and_calibration
                if data_and_calibration:
                    live_metadata = buffered_data_source.metadata.get("hardware_source", dict())
                    frame_index_str = str(live_metadata.get("frame_index", str()))
                    partial_str = "{0:d}/{1:d}".format(live_metadata.get("valid_rows"), data_and_calibration.dimensional_shape[0]) if "valid_rows" in live_metadata else str()
                    return "{0:s} {1:s} {2:s}".format(_("Live"), frame_index_str, partial_str)
        return str()

    def get_mime_data(self):
        data_item = self.data_item
        mime_data = self.ui.create_mime_data()
        mime_data.set_data_as_string("text/data_item_uuid", str(data_item.uuid))
        return mime_data

    def drag_started(self, x, y, modifiers):
        data_item = self.data_item
        mime_data = self.get_mime_data()
        display_specifier = data_item.primary_display_specifier
        display = display_specifier.display
        thumbnail_data = display.get_processed_data("thumbnail") if display else None
        return mime_data, thumbnail_data