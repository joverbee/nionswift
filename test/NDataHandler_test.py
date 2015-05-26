# standard libraries
import binascii
import datetime
import json
import logging
import os
import shutil
import StringIO
import unittest
import uuid

# third party libraries
import numpy
import scipy.signal

# local libraries
from nion.swift import NDataHandler
from nion.swift.model import Storage
from nion.ui import Unicode


class TestNDataHandlerClass(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_ndata_handler_basic_functionality(self):
        now = datetime.datetime.now()
        current_working_directory = os.getcwd()
        data_dir = os.path.join(current_working_directory, "__Test")
        Storage.db_make_directory_if_needed(data_dir)
        try:
            h = NDataHandler.NDataHandler(data_dir)
            p = {u"abc": 1, u"def": u"bcd", u"uuid": Unicode.u(uuid.uuid4())}
            # write properties
            h.write_properties("abc", p, now)
            self.assertEqual(h.read_properties("abc")[1], p)
            self.assertIsNone(h.read_data("abc"))
            # write data
            h.write_data("abc", numpy.zeros((4,4), dtype=numpy.float64), now)
            self.assertEqual(h.read_properties("abc")[1], p)
            d = h.read_data("abc")
            self.assertEqual(d.shape, (4, 4))
            self.assertEqual(d.dtype, numpy.float64)
            # rewrite data
            h.write_data("abc", numpy.zeros((12,12), dtype=numpy.float32), now)
            self.assertEqual(h.read_properties("abc")[1], p)
            d = h.read_data("abc")
            self.assertEqual(d.shape, (12, 12))
            self.assertEqual(d.dtype, numpy.float32)
            # rewrite properties
            h.write_properties("abc", p, now)
            self.assertEqual(h.read_properties("abc")[1], p)
            d = h.read_data("abc")
            self.assertEqual(d.shape, (12, 12))
            self.assertEqual(d.dtype, numpy.float32)
        finally:
            #logging.debug("rmtree %s", data_dir)
            shutil.rmtree(data_dir)

    def test_ndata_handler_rewrites_reversed_zip_file(self):
        now = datetime.datetime.now()
        current_working_directory = os.getcwd()
        data_dir = os.path.join(current_working_directory, "__Test")
        Storage.db_make_directory_if_needed(data_dir)
        try:
            p = {u"abc": 1, u"def": u"bcd", u"uuid": Unicode.u(uuid.uuid4())}
            d = numpy.zeros((12,12), dtype=numpy.float32)
            # write zip file where metadata is first
            with open(os.path.join(data_dir, "file.ndata"), "w+b") as fp:
                dir_data_list = list()
                dt = now
                properties = p
                data = d
                if properties is not None:
                    json_io = StringIO.StringIO()
                    json.dump(properties, json_io)
                    json_str = json_io.getvalue()
                    json_len = len(json_str)
                    json_crc32 = binascii.crc32(json_str) & 0xFFFFFFFF
                    def write_json(fp):
                        fp.write(json_str)
                        return binascii.crc32(json_str) & 0xFFFFFFFF
                    offset_json = fp.tell()
                    json_len, json_crc32 = NDataHandler.write_local_file(fp, "metadata.json", write_json, dt)
                    dir_data_list.append((offset_json, "metadata.json", json_len, json_crc32))
                if data is not None:
                    offset_data = fp.tell()
                    def write_data(fp):
                        numpy_start_pos = fp.tell()
                        numpy.save(fp, data)
                        numpy_end_pos = fp.tell()
                        fp.seek(numpy_start_pos)
                        header_data = fp.read(len(data.data) - (numpy_end_pos - numpy_start_pos))  # read the header
                        data_crc32 = binascii.crc32(data.data, binascii.crc32(header_data)) & 0xFFFFFFFF
                        fp.seek(numpy_end_pos)
                        return data_crc32
                    data_len, crc32 = NDataHandler.write_local_file(fp, "data.npy", write_data, dt)
                    dir_data_list.append((offset_data, "data.npy", data_len, crc32))
                dir_offset = fp.tell()
                for offset, name, data_len, crc32 in dir_data_list:
                    NDataHandler.write_directory_data(fp, offset, name, data_len, crc32, dt)
                dir_size = fp.tell() - dir_offset
                NDataHandler.write_end_of_directory(fp, dir_size, dir_offset, len(dir_data_list))
                fp.truncate()
            # make sure read works
            h = NDataHandler.NDataHandler(data_dir)
            self.assertEqual(h.read_properties("file")[1], p)
            dd = h.read_data("file")
            self.assertEqual(dd.shape, d.shape)
            self.assertEqual(dd.dtype, d.dtype)
            # now rewrite
            h.write_properties("file", p, now)
        finally:
            #logging.debug("rmtree %s", data_dir)
            shutil.rmtree(data_dir)

    def test_ndata_handles_discontiguous_data(self):
        logging.getLogger().setLevel(logging.DEBUG)
        now = datetime.datetime.now()
        current_working_directory = os.getcwd()
        data_dir = os.path.join(current_working_directory, "__Test")
        Storage.db_make_directory_if_needed(data_dir)
        try:
            h = NDataHandler.NDataHandler(data_dir)
            data1 = numpy.ones((16, 16), dtype=numpy.float64)
            data = scipy.signal.fftconvolve(data1, data1, mode='same')
            self.assertRaises(AttributeError, lambda: data.data)  # make sure we're getting discontiguous data
            p = {u"uuid": Unicode.u(uuid.uuid4())}
            # write properties
            h.write_properties("abc", p, now)
            # write data
            h.write_data("abc", data, now)
            d = h.read_data("abc")
            self.assertEqual(d.shape, data.shape)
            self.assertEqual(d.dtype, data.dtype)
        finally:
            #logging.debug("rmtree %s", data_dir)
            shutil.rmtree(data_dir)


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
