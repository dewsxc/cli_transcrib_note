import re
import os

from setup import ServiceSetup


class SimpleRecorder:

    @classmethod
    def check_if_had_read(cls, proj_setup:ServiceSetup, main_id, id):
        record_fp = proj_setup.get_record_for(main_id)
        print("Checking record for: {} {} {}".format(main_id, id, record_fp))
        
        if not os.path.exists(record_fp):
            return False
        with open(record_fp, 'r') as f:
            r = re.findall(id, f.read())
            return len(r) >= 1

    @classmethod
    def mark_video_as_read(cls, proj_setup:ServiceSetup, main_id, id):
        record_fp = proj_setup.get_record_for(main_id)

        if cls.check_if_had_read(proj_setup, main_id, id):
            return
        with open(record_fp, 'a') as f:
            f.write(id + '\n')
        print("Marked read: {} {}".format(main_id, id))