# -*- coding: utf-8 -*-

import json
import schedule
import random
import threading

import functions
import nlp
import notifier
import slack
from slack import MsgResource
import utils

class Scheduler(object):

    def __init__(self, text=None):
        self.input = text
        self.slackbot = slack.SlackerAdapter()
        self.data_handler = utils.DataHandler()
        self.fname = "schedule.json"
        self.template = slack.MsgTemplate()

    def create(self, step=0, params=None):

        state = utils.State()

        # 알람 생성 시작
        def step_0(params):
            self.slackbot.send_message(text=MsgResource.SCHEDULER_CREATE_START)
            self.data_handler.read_json_then_add_data(self.fname, "alarm", {})
            state.start("notifier/Scheduler", "create")
            if notifier.Between().read() == "success":
                self.slackbot.send_message(text=MsgResource.SCHEDULER_CREATE_STEP1)
            else:
                self.slackbot.send_message(text=MsgResource.SCHEDULER_CREATE_STEP1_ONLY_TIME)

        # 시간대 지정
        def step_1(params):
            a_index, current_alarm_data = self.data_handler.get_current_data(self.fname, "alarm")

            if params.startswith("#"):
                current_alarm_data["between_id"] = params
                state.next_step()
                self.slackbot.send_message(text=MsgResource.SCHEDULER_CREATE_STEP2)
            else:
                current_alarm_data["time"] = params
                state.next_step(num=2)
                functions.FunctionManager().read()
                self.slackbot.send_message(text=MsgResource.SCHEDULER_CREATE_STEP3)

            self.data_handler.read_json_then_edit_data(self.fname, "alarm", a_index, current_alarm_data)

        # 주기
        def step_2(params):
            a_index, current_alarm_data = self.data_handler.get_current_data(self.fname, "alarm")
            current_alarm_data["period"] = params
            self.data_handler.read_json_then_edit_data(self.fname, "alarm", a_index, current_alarm_data)

            state.next_step()
            functions.FunctionManager().read()
            self.slackbot.send_message(text=MsgResource.SCHEDULER_CREATE_STEP3)

        # 함수
        def step_3(params):
            a_index, current_alarm_data = self.data_handler.get_current_data(self.fname, "alarm")

            if "," in params:
                f_name, f_params = params.split(",")
                current_alarm_data["f_name"] = f_name.strip()
                current_alarm_data["params"] = json.loads(f_params.strip().replace("”", "\"").replace("“", "\""))
            else:
                current_alarm_data["f_name"] = params.strip()
            self.data_handler.read_json_then_edit_data(self.fname, "alarm", a_index, current_alarm_data)

            state.complete()
            self.slackbot.send_message(text=MsgResource.CREATE)

        if state.is_do_something():
            current_step = state.current["step"]
            step_num = "step_" + str(current_step)
            locals()[step_num](params)
        else:
            step_0(params)

    def create_with_ner(self, time_of_day=None, time_unit=None, period=None, functions=None):

        if functions == "not exist":
            self.slackbot.send_message(text=MsgResource.WORKER_FUNCTION_NOT_FOUND)
            return
        else:
            self.slackbot.send_message(text=MsgResource.WORKER_CREATE_START)

        if time_of_day == "not exist":
            time_of_day = "all_day"
        if period == "real-time":
            period = "7 minutes"
        elif period == "interval":
            period = "interval"
        else:
            period = str(random.randint(25, 35)) + " minutes"

        if time_unit == "not exist":
            time = None
        elif len(time_unit) == 1 and period == "interval":
            period = time_unit[0]
            period = period.replace("분", " 분")
            period = period.replace("시", " 시")
            time = None
        else:
            time_of_day = None
            period = None

            time = ":"
            for t in time_unit:
                minute = 0
                if '시' in t:
                    hour = int(t[:t.index('시')])
                if '분' in t:
                    minute = int(t[:t.index('분')])
            time = '{0:02d}'.format(hour) + time + '{0:02d}'.format(minute)

        alarm_data = {
            "between_id": time_of_day,
            "period": period,
            "time": time,
            "f_name": functions
        }
        alarm_data = dict((k, v) for k, v in alarm_data.items() if v)
        self.data_handler.read_json_then_add_data(self.fname, "alarm", alarm_data)
        self.slackbot.send_message(text=MsgResource.CREATE)

    def read(self):
        schedule_data = self.data_handler.read_file(self.fname)
        alarm_data = schedule_data.get('alarm', {})

        if alarm_data == {} or len(alarm_data) == 1:
            self.slackbot.send_message(text=MsgResource.EMPTY)
            return "empty"

        between_data = schedule_data.get('between', {})
        for k,v in alarm_data.items():
            if k == "index":
                continue

            if 'between_id' in v:
                between = between_data[v['between_id']]
                self.__alarm_in_between(between, k, v, repeat=True)
            elif 'time' in v:
                specific = between_data.get("specific time", {})
                specific['time_interval'] = ""
                specific['description'] = "특정 시간"
                between_data["specific time"] = self.__alarm_in_between(specific, k, v)

        attachments = self.template.make_schedule_template("", between_data)
        self.slackbot.send_message(text=MsgResource.READ, attachments=attachments)
        return "success"

    def __alarm_in_between(self, between, a_index, alarm_data, repeat=False):
        f_name = alarm_data['f_name']
        f_detail = functions.FunctionManager().functions[f_name]

        if repeat:
            alarm_detail = "Alarm " + a_index + " (repeat: "+ alarm_data['period'] + ")\n"
        else:
            alarm_detail = "Alarm " + a_index + " (time: " + alarm_data['time'] + ")\n"

        alarm_detail += "            " + f_detail['icon'] + f_name + ", " + str(alarm_data.get('params', ''))
        registered_alarm = "등록된 알람 리스트."
        if registered_alarm in between:
            between[registered_alarm].append(alarm_detail)
        else:
            between[registered_alarm] = [alarm_detail]
        return between

    def update(self, step=0, params=None):
        a_index, input_text, input_period, input_between_id = params[0].split(" + ")
        input_alarm = {"text": input_text, "period": input_period, "between_id": input_between_id}

        result = self.data_handler.read_json_then_edit_data(self.fname, "alarm", a_index, input_alarm)

        if result == "sucess":
            attachments = self.template.make_schedule_template(
                MsgResource.UPDATE,
                {a_index:input_alarm}
            )

            self.slackbot.send_message(attachments=attachments)
        else:
            self.slackbot.send_message(text=MsgResource.ERROR)

    def delete(self, step=0, params=None):

        state = utils.State()

        def step_0(params):
            self.slackbot.send_message(text=MsgResource.SCHEDULER_DELETE_START)
            if self.read() == "success":
                state.start("notifier/Scheduler", "delete")

        def step_1(params):
            a_index = params
            self.data_handler.read_json_then_delete(self.fname, "alarm", a_index)

            state.complete()
            self.slackbot.send_message(text=MsgResource.DELETE)

        if state.is_do_something():
            current_step = state.current["step"]
            step_num = "step_" + str(current_step)
            locals()[step_num](params)
        else:
            step_0(params)

