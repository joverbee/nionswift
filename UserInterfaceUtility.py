# standard libraries
import logging

# third party libraries
# none

# local libraries
from nion.swift import Decorators
from nion.swift import Storage


# format the text of a line edit widget to and from integer value
class IntegerFormatter(object):

    def __init__(self, line_edit):
        self.line_edit = line_edit

    def format(self, text):
        self.value = int(text)

    def __get_value(self):
        return int(self.line_edit.text)
    def __set_value(self, value):
        self.line_edit.text = str(value)
    value = property(__get_value, __set_value)


# format the text of a line edit widget to and from float value
class FloatFormatter(object):

    def __init__(self, line_edit):
        self.line_edit = line_edit

    def format(self, text):
        self.value = float(text)

    def __get_value(self):
        return float(self.line_edit.text)
    def __set_value(self, value):
        self.line_edit.text = "%g" % float(value)
    value = property(__get_value, __set_value)


class FloatToStringConverter(object):
    """
        Convert from float value to string and back.
    """
    def __init__(self, format=None):
        self.__format = format if format else "{:g}"
    def convert(self, value):
        return self.__format.format(value)
    def convert_back(self, str):
        return float(str)


class FloatTo100Converter(object):
    """
        Convert from float value to int (float * 100) and back.
    """
    def convert(self, value):
        return int(value * 100)
    def convert_back(self, value100):
        return value100 / 100.0


class FloatToPercentStringConverter(object):
    """
        Convert from float value to string and back.
    """
    def convert(self, value):
        return str(int(value * 100)) + "%"
    def convert_back(self, str):
        return float(str.strip('%'))/100.0


class CheckedToCheckStateConverter(object):
    """
        Convert from bool value to check state and back.
    """
    def convert(self, value):
        return "checked" if value else "unchecked"
    def convert_back(self, value):
        return value == "checked"


class Binding(Storage.Observable):

    """
        Binds two objects together. Set source_getter, source_setter,
        and target_setter to configure this class.

        The owner should call periodic and close on this object.

        Bindings are not sharable. They are meant to be used to bind
        one ui element to one value.
        However, conversions and binding sources can be shared between
        bindings in most cases.
    """

    def __init__(self, source, converter=None, fallback=None):
        super(Binding, self).__init__()
        self.__task_set = Decorators.TaskSet()
        self.__source = None
        self.__converter = converter
        self.fallback = fallback
        self.source_getter = None
        self.source_setter = None
        self.target_setter = None
        self.source = source

    # not thread safe
    def close(self):
        self.source = None

    # not thread safe
    def periodic(self):
        self.__task_set.perform_tasks()

    # thread safe
    def add_task(self, key, task):
        self.__task_set.add_task(key, task)

    # thread safe
    def __get_source(self):
        return self.__source
    def __set_source(self, source):
        if self.__source:
            self.__source.remove_observer(self)
        self.__source = source
        if self.__source:
            self.__source.add_observer(self)
        self.notify_set_property("source", source)
    source = property(__get_source, __set_source)

    # thread safe
    def __get_converter(self):
        return self.__converter
    converter = property(__get_converter)

    # thread safe
    def __back_converted_value(self, target_value):
        return self.__converter.convert_back(target_value) if self.__converter else target_value

    # thread safe
    def __converted_value(self, source_value):
        return self.__converter.convert(source_value) if self.__converter else source_value

    # thread safe
    def update_source(self, target_value):
        if self.source_setter:
            converted_value = self.__back_converted_value(target_value)
            self.source_setter(converted_value)

    # not thread safe
    def update_target(self, source_value):
        self.update_target_direct(self.__converted_value(source_value))

    # not thread safe
    def update_target_direct(self, converted_value):
        if self.target_setter:
            self.target_setter(converted_value)

    # thread safe
    def get_target_value(self):
        if self.source_getter:
            source = self.source_getter()
            if source is not None:
                return self.__converted_value(source)
        return self.fallback


class ObjectBinding(Binding):

    """
        Binds directly to a source object.

        The owner should call periodic and close on this object.
    """

    def __init__(self, source, converter=None):
        super(ObjectBinding, self).__init__(source, converter)
        self.source_getter = lambda: self.source


class ListBinding(Binding):

    """
        Binds to a source object which is a list. One way from source to target.

        The owner should call periodic and close on this object.
    """

    def __init__(self, source, key_name):
        super(ListBinding, self).__init__(source)
        self.__key_name = key_name
        self.inserter = None
        self.remover = None

    # not thread safe
    def insert_item(self, item, before_index):
        if self.inserter:
            self.inserter(item, before_index)

    # not thread safe
    def remove_item(self, index):
        if self.remover:
            self.remover(index)

    # thread safe
    def item_inserted(self, sender, key, item, before_index):
        if sender == self.source and key == self.__key_name:
            # perform on the main thread
            self.add_task("insert_item", lambda: self.insert_item(item, before_index))

    # thread safe
    def item_removed(self, sender, key, item, index):
        if sender == self.source and key == self.__key_name:
            # perform on the main thread
            self.add_task("remove_item", lambda: self.remove_item(index))

    # thread safe
    def __get_items(self):
        return getattr(self.source, self.__key_name)
    items = property(__get_items)


class PropertyBinding(Binding):

    """
        Binds to a property of a source object.

        Changes to the target are propogated to the source via setattr using the update_source method.

        If target_setter is set, changes to the source are propogated to the target via target_setter
        using the update_target method.

        The owner should call periodic and close on this object.
    """

    def __init__(self, source, property_name, converter=None):
        super(PropertyBinding, self).__init__(source,  converter)
        self.__property_name = property_name
        self.source_setter = lambda value: setattr(self.source, self.__property_name, value)
        self.source_getter = lambda: getattr(self.source, self.__property_name)

    # thread safe
    def property_changed(self, sender, property, value):
        if sender == self.source and property == self.__property_name:
            # perform on the main thread
            self.add_task("update_target", lambda: self.update_target(value))


class TuplePropertyBinding(Binding):

    """
        Binds to a tuple property of a source object.

        Changes to the target are propogated to the source via setattr using the update_source method.

        If target_setter is set, changes to the source are propogated to the target via target_setter
        using the update_target method.

        The owner should call periodic and close on this object.
    """

    def __init__(self, source, property_name, tuple_index, converter=None, fallback=None):
        super(TuplePropertyBinding, self).__init__(source,  converter=converter, fallback=fallback)
        self.__property_name = property_name
        self.__tuple_index = tuple_index
        def source_setter(value):
            tuple_as_list = list(getattr(self.source, self.__property_name))
            tuple_as_list[self.__tuple_index] = value
            setattr(self.source, self.__property_name, tuple(tuple_as_list))
        def source_getter():
            tuple_value = getattr(self.source, self.__property_name)
            return tuple_value[self.__tuple_index] if tuple_value else None
        self.source_setter = source_setter
        self.source_getter = source_getter

    # thread safe
    def property_changed(self, sender, property, value):
        if sender == self.source and property == self.__property_name:
            # perform on the main thread
            if value is not None:
                self.add_task("update_target", lambda: self.update_target(value[self.__tuple_index]))
            else:
                self.add_task("update_target", lambda: self.update_target_direct(self.fallback))