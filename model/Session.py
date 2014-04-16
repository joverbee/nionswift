# standard libraries
import copy
import datetime
import threading
import weakref

# third party libraries
# None

# local libraries
from nion.swift.model import DataGroup
from nion.swift.model import DataItem
from nion.ui import Process


# session object is contained in the document model. there is only one session
# object active at once. the document model may eventually keep a set of sessions
# but only one will be the current one.
# document controllers can also attach themselves to the session so that
# they can respond to changes in the session. only one document controller
# can be attached to the session at once, i.e. the front most document
# controller. this is managed using document_controller_activation_changed.
class Session(object):

    def __init__(self, document_model):
        self.__weak_document_model = weakref.ref(document_model)
        self.__weak_document_controller = None
        self.session_id = None
        self.start_new_session()
        # channel activations keep track of which channels have been activated in the UI for a particular acquisition run.
        self.__channel_activations = dict()  # maps hardware_source_id to a set of activated channels
        self.__channel_activations_mutex = threading.RLock()
        self.__periodic_queue = Process.TaskQueue()

    def periodic(self):
        self.__periodic_queue.perform_tasks()

    def __get_document_model(self):
        return self.__weak_document_model() if self.__weak_document_model else None
    document_model = property(__get_document_model)

    def __get_document_controller(self):
        return self.__weak_document_controller() if self.__weak_document_controller else None
    def __set_document_controller(self, document_controller):
        self.__weak_document_controller = weakref.ref(document_controller) if document_controller else None
    document_controller = property(__get_document_controller, __set_document_controller)

    def document_controller_activation_changed(self, document_controller, activated):
        if activated:
            self.document_controller = document_controller
        elif self.document_controller == document_controller:
            self.document_controller = None

    # this message is received when a hardware source will start playing in this session.
    def will_start_playing(self, hardware_source):
        with self.__channel_activations_mutex:
            self.__channel_activations.setdefault(hardware_source.hardware_source_id, set()).clear()

    # this message is received when a hardware source stopped playing in this session.
    def did_stop_playing(self, hardware_source):
        pass

    def start_new_session(self):
        self.session_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    # return a dictionary of data items indexed by channel
    # thread safe
    def sync_channels_to_data_items(self, channels, hardware_source):

        # these functions will be run on the main thread.
        # be careful about binding the parameter. cannot use 'data_item' directly.
        def insert_data_item(append_data_item):
            self.document_model.insert_data_item(0, append_data_item)
            append_data_item.remove_ref()
        def append_data_item(append_data_item):
            self.document_model.append_data_item(append_data_item)
            append_data_item.remove_ref()
        def activate_data_item(data_item_to_activate):
            if self.document_controller:
                self.document_controller.set_data_item_selection(data_item_to_activate)

        data_item_set = {}

        # for each channel, see if a matching data item exists.
        # if it does, check to see if it matches this hardware source.
        # if no matching data item exists, create one.
        for channel in channels:
            data_item_name = "%s.%s" % (hardware_source.display_name, channel)
            # only use existing data item if it has a data buffer that matches
            data_item = DataGroup.get_data_item_in_container_by_title(self.document_model, data_item_name)
            # to reuse, first verify that the hardware source id, if any, matches
            if data_item:
                hardware_source_id = data_item.properties.get("hardware_source_id")
                if hardware_source_id != hardware_source.hardware_source_id:
                    data_item = None
            # if everything but session or live-ness matches, copy it and re-use.
            # this keeps the users display preferences intact.
            do_copy = False
            if data_item and data_item.properties.get("session_id", str()) != self.session_id:
                do_copy = True
            # finally, verify that this data item is live. if it isn't live, copy it and add the
            # copy to the group, but re-use the original. this helps preserve the users display
            # choices. for the copy, delete derived data. keep only the master.
            if data_item and not data_item.is_live:
                do_copy = True
            if do_copy:
                data_item_copy = copy.deepcopy(data_item)
                data_item_copy.add_ref()  # this will be balanced in append_data_item
                for _ in xrange(len(data_item_copy.data_items)):
                    data_item_copy.data_items.pop()
                data_item.session_id = self.session_id  # immediately update the session id
                self.__periodic_queue.put(lambda value=data_item_copy: append_data_item(value))
            # if we still don't have a data item, create it.
            if not data_item:
                data_item = DataItem.DataItem()
                data_item.add_ref()  # this will be balanced in insert_data_item
                data_item.title = data_item_name
                with data_item.property_changes() as context:
                    context.properties["hardware_source_id"] = hardware_source.hardware_source_id
                self.__periodic_queue.put(lambda value=data_item: insert_data_item(value))
                with self.__channel_activations_mutex:
                    self.__channel_activations.setdefault(hardware_source.hardware_source_id, set()).add(channel)
            data_item.session_id = self.session_id
            data_item_set[channel] = data_item
            # check to see if its been activated. if not, activate it.
            with self.__channel_activations_mutex:
                if channel not in self.__channel_activations.setdefault(hardware_source.hardware_source_id, set()):
                    self.__periodic_queue.put(lambda value=data_item: activate_data_item(value))
                    self.__channel_activations.setdefault(hardware_source.hardware_source_id, set()).add(channel)

        return data_item_set