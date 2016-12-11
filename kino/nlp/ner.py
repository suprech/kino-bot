# -*- coding: utf-8 -*-

import re

from utils.data_handler import DataHandler

class NamedEntitiyRecognizer(object):
    class __NER:
        def __init__(self):
            self.data_handler = DataHandler()
            self.fname = "ner.json"
            self.ner = self.__read_ner()

            self.kino = self.ner['kino']
            self.behave = self.ner['behave']
            self.classname = self.ner['classname']
            self.functions = self.ner['functions']
            self.params = self.ner['params']
            self.period = self.ner['period']
            self.time_of_day = self.ner['time_of_day']
            self.time_unit = self.ner['time_unit']

        def __read_ner(self):
            return self.data_handler.read_file(self.fname)

        def parse(self, item, text, get_all=False):
            ner_list = []
            for item_name, item_pattern in item.items():
                item_pattern_type = type(item_pattern)
                if item_pattern_type == type({}):
                    sub_ner = self.parse(item_pattern, text)
                    if sub_ner:
                        ner_list.append((item_name, sub_ner))
                elif item_pattern_type == type([]):
                    if any([p for p in item_pattern if p in text]):
                        if get_all:
                            ner_list.append(item_name)
                        else:
                            return item_name
                elif item_pattern_type == type(""):
                    result =  re.findall(item_pattern, text)
                    if get_all:
                        ner_list += result
                    else:
                        return result[0]
            if len(ner_list) == 0:
                return None
            else:
                return ner_list

    instance = None
    def __init__(self):
        if not NamedEntitiyRecognizer.instance:
            NamedEntitiyRecognizer.instance = NamedEntitiyRecognizer.__NER()

    def __getattr__(self, name):
        return getattr(self.instance, name)