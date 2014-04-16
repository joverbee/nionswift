import threading
import time
import weakref


class DataItemProcessor(object):

    def __init__(self, item, cache_property_name):
        self.__weak_item = weakref.ref(item)
        self.__cache_property_name = cache_property_name
        self.__mutex = threading.RLock()
        self.__in_progress = False

    def __get_item(self):
        return self.__weak_item() if self.__weak_item else None
    item = property(__get_item)

    def data_item_changed(self):
        """ Called directly from data item. """
        self.set_cached_value_dirty()

    def item_property_changed(self, key, value):
        """
            Called directly from data item.
            Subclasses should override and call set_cached_value_dirty to add
            property dependencies.
        """
        pass

    def set_cached_value_dirty(self):
        self.item.set_cached_value_dirty(self.__cache_property_name)

    def get_calculated_data(self, ui, data):
        """ Subclasses must implement. """
        raise NotImplementedError()

    def get_default_data(self):
        return None

    def get_data_item(self):
        """ Subclasses must implement. """
        raise NotImplementedError()

    def get_data(self, ui, completion_fn=None):
        if self.item.is_cached_value_dirty(self.__cache_property_name):
            data_item = self.get_data_item()
            if not data_item.closed and (data_item.has_master_data or data_item.has_data_source):
                def load_data_on_thread():
                    time.sleep(0.2)
                    with data_item.data_ref() as data_ref:
                        data = data_ref.data
                        if data is not None:  # for data to load and make sure it has data
                            try:
                                calculated_data = self.get_calculated_data(ui, data)
                            except Exception as e:
                                import traceback
                                traceback.print_exc()
                            self.item.set_cached_value(self.__cache_property_name, calculated_data)
                        else:
                            calculated_data = None
                    if calculated_data is None:
                        calculated_data = self.get_default_data()
                        self.item.remove_cached_value(self.__cache_property_name)
                    if completion_fn:
                        completion_fn(calculated_data)
                    with self.__mutex:
                        self.__in_progress = False
                with self.__mutex:
                    if not self.__in_progress:
                        self.__in_progress = True
                        self.item.add_shared_task(self.__cache_property_name, None, lambda: load_data_on_thread())
        calculated_data = self.item.get_cached_value(self.__cache_property_name)
        if calculated_data is not None:
            return calculated_data
        return self.get_default_data()