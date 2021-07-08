import json
import os
import traceback

from .process_monitor import process_fingerprint

PREFIX = '[MFB] '

class MFBState(object):

    def __init__(self):
        self._thread_state = {}
        self._channel_name = {}
        self._user_info = {}
        self._monitors = {}

    @classmethod
    def _make_message(cls, **kwargs):
        return '%s`%s`' % (PREFIX, json.dumps(kwargs))

    def _parse_message(self, msg):
        try:
            return json.loads(msg[len(PREFIX) + 1:-1])
        except:
            return {}

    def channel_name(self, chan):
        return self._channel_name.get(chan)

    def user_name(self, user):
        return self._user_info.get(user)

    def get_thread(self, event):
        if event.type == 'state_change':
            return self._parse_message(event.msg).get('thread')
        elif event.type == 'slash_message':
            return event.chan
        else:
            return '%s:%s' % (event.chan, event.thread_ts)

    def get_thread_state(self, thread):
        return self._thread_state.get(thread, {})

    def is_state_match(self, context, event):
        # note that if the event is a state change event, the state
        # is matched against the originating thread, not against the
        # admin thread, which would be pointless
        thread = self._thread_state.get(self.get_thread(event), {})
        return all(thread.get(k) == v for k, v in context.items())

    def is_event_match(self, event, rule):
        msg = self._parse_message(event.msg)
        if msg.get('type') == rule.get('type') == 'set':
            # 'set' sets multiple k-v pairs in the thread state.
            # The rule matches a specified key in the event. It
            # can optionally match the value too.
            attrs = msg.get('attributes', {})
            key = rule.get('key')
            return key in attrs and\
                   ('value' not in rule or rule['value'] == attrs[key])
        else:
            return all(msg.get(k) == v for k, v in rule.items())

    def is_known_thread(self, chan, thread_ts):
        key = '%s:%s' % (chan, thread_ts)
        return key in self._thread_state

    def is_admin_thread_parent(self, msg):
        return self.is_state_message(msg) and\
               self._parse_message(msg).get('type') == 'admin_thread'

    def is_state_message(self, msg):
        return msg and msg.startswith(PREFIX)

    def get_monitors(self):
        return list(self._monitors.items())

    def disable_monitor(self, fingerprint):
        self._monitors.pop(fingerprint, None)

    def update(self, event):
        try:
            msg = self._parse_message(event.msg)
            msg_type = msg['type']
            if msg_type in ('admin_thread', 'noop'):
                pass
            elif msg_type == 'new_thread':
                self._thread_state[msg['thread']] = {}
            elif msg_type == 'channel_info':
                self._channel_name[msg['channel']] = msg['channel_name']
            elif msg_type == 'user_info':
                self._user_info[msg['user']] = msg['user_name']
            elif msg_type == 'set':
                self.update_thread(msg['thread'], msg['attributes'])
            elif msg_type == 'enable_monitor':
                self._monitors[msg['fingerprint']] = msg['thread']
            elif msg_type == 'disable_monitor':
                self.disable_monitor(msg['fingerprint'])
            else:
                return False
            return True
        except:
            traceback.print_exc()
            return False

    def update_thread(self, thread, attributes):
        if thread in self._thread_state:
            thread_state = self._thread_state[thread]
            for k, v in attributes.items():
                if isinstance(v, dict):
                    prev_dict = thread_state.get(k)
                    if prev_dict is None:
                        thread_state[k] = dict(v)
                    else:
                        prev_dict.update(v)
                else:
                    thread_state[k] = v

    @classmethod
    def message_noop(cls):
        return cls._make_message(type='noop')

    @classmethod
    def message_new_thread(cls, thread):
        return cls._make_message(type='new_thread', thread=thread)

    @classmethod
    def message_new_admin_thread(cls):
        return cls._make_message(type='admin_thread')

    @classmethod
    def message_channel_info(cls, channel, channel_name):
        return cls._make_message(type='channel_info',
                                 channel=channel,
                                 channel_name=channel_name)

    @classmethod
    def message_user_info(cls, user, user_name):
        return cls._make_message(type='user_info',
                                 user=user,
                                 user_name=user_name)

    @classmethod
    def message_set_attributes(cls, thread, attributes):
        return cls._make_message(type='set',
                                 attributes=attributes,
                                 thread=thread)

    @classmethod
    def message_enable_monitor(cls, thread):
        return cls._make_message(type='enable_monitor',
                                 fingerprint=process_fingerprint(os.getpid()),
                                 thread=thread)

    @classmethod
    def message_disable_monitor(cls, thread, fingerprint=None):
        if fingerprint is None:
            fingerprint = process_fingerprint(os.getpid())
        return cls._make_message(type='disable_monitor',
                                 fingerprint=fingerprint,
                                 thread=thread)
