#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time:2020.09.12
# @author:xhrg
# @email:634789257@qq.com

import json
import os
import threading
import inspect
import ctypes
import logging
import time

from .util import *

version = sys.version_info.major

if version == 2:
    from .python_2x import *

if version == 3:
    from .python_3x import *

logging.basicConfig()


class ApolloClient(object):

    def __init__(self, app_id, cluster=None, apollo_config_url=None, cycle_time=2, secret=''):

        # 配置变量
        self.config_server_url = apollo_config_url
        self.cluster = cluster
        self.app_id = app_id

        self.stopped = False
        self.ip = init_ip()
        self._stopping = False
        self._mycache = {}
        # 休眠时间周期，每次请求结束后会 time.sleep(self._cycle_time)
        if cycle_time <= 1:
            cycle_time = 1
        self._cycle_time = cycle_time
        self._hash = {}
        self._cache_file_path = os.path.expanduser('~') + '/data/apollo/cache/'
        self._path_checker()
        self.long_poll_thread = None
        self.secret = secret
        self.call_time = 0
        self.change_listener = None

        # 私有设置变量
        self._started = False
        self._pull_timeout = 75

    # "add" "delete" "update"
    def set_change_listener(self, change_listener):
        self.change_listener = change_listener

    def get_json_from_net(self, namespace='application'):
        url = '{}/configfiles/json/{}/{}/{}?ip={}'.format(self.config_server_url, self.app_id, self.cluster, namespace,
                                                          self.ip)
        try:
            code, body = http_request(url, timeout=3)
            if code == 200:
                data = json.loads(body)
                return_data = {CONFIGURATIONS: data}
                return return_data
            else:
                return None
        except Exception as e:
            logging.getLogger(__name__).warning(str(e))
            return None

    def get_value(self, key, default_val=None, namespace='application'):
        try:
            # 读取本地缓存
            namespace_cache = self._mycache.get(namespace)
            have, val = get_value_from_dict(namespace_cache, key)
            if have:
                return val_handler(val, default_val)
            # 读取本地文件
            namespace_cache = self._get_local_cache(namespace)
            have, val = get_value_from_dict(namespace_cache, key)
            if have:
                self._update_cache_and_file(namespace_cache, namespace)
                return val_handler(val, default_val)

            # 读取网络配置
            namespace_data = self.get_json_from_net(namespace)
            have, val = get_value_from_dict(namespace_data, key)
            if have:
                self._update_cache_and_file(namespace_data, namespace)
                return val_handler(val, default_val)

            # 如果全部没有获取，则把默认值返回，设置本地缓存为None
            self._set_local_cache_none(key, namespace)
            return default_val
        except Exception as e:
            logging.getLogger(__name__).error("get_value has error, [key is %s], [namespace is %s], [error is %s], ",
                                              key, namespace, e)
            return default_val

    # 设置某个namespace的key为none，这里不设置default_val，是为了保证函数调用实时的正确性。
    # 假设用户2次default_val不一样，然而这里却用default_val填充，则可能会有问题。
    def _set_local_cache_none(self, key, namespace):
        namespace_cache = self._mycache.get(namespace)
        if namespace_cache is None:
            namespace_cache = {}
            self._mycache[namespace] = namespace_cache
        kv_data = namespace_cache.get(CONFIGURATIONS)
        if kv_data is None:
            kv_data = {}
            namespace_cache[CONFIGURATIONS] = kv_data
        val = kv_data.get(key)
        if val not in kv_data:
            kv_data[key] = None

    def start_hot_update(self, catch_signals=True):
        if self._started:
            return
        self._started = True
        if catch_signals:
            import signal
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGABRT, self._signal_handler)
        self.long_poll_thread = threading.Thread(target=self._listener)
        self.long_poll_thread.setDaemon(True)
        self.long_poll_thread.start()

    def stop(self):
        self._stopping = True
        logging.getLogger(__name__).info("Stopping listener...")

    def _async_raise(self, ident, exctype):
        tid = ctypes.c_long(ident)
        if not inspect.isclass(exctype):
            exctype = type(exctype)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
        if res == 0:
            raise ValueError("invalid thread id")
        elif res != 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
            raise SystemError("PyThreadState_SetAsyncExc failed")

    # 调用设置的回调函数，如果异常，直接try掉
    def _call_listener(self, namespace, old_kv, new_kv):
        if self.change_listener is None:
            return
        try:
            for key in old_kv:
                new_value = new_kv.get(key)
                old_value = old_kv.get(key)
                if new_value is None:
                    # 如果newValue 是空，则表示key，value被删除了。
                    self.change_listener("delete", namespace, key, old_value)
                    continue
                if new_value != old_value:
                    self.change_listener("update", namespace, key, new_value)
                    continue
            for key in new_kv:
                new_value = new_kv.get(key)
                old_value = old_kv.get(key)
                if old_value is None:
                    self.change_listener("add", namespace, key, new_value)
        except BaseException as e:
            logging.getLogger(__name__).warning(str(e))

    def _signal_handler(self, signal_num, stack_frame):
        logging.getLogger(__name__).info('You pressed Ctrl+C!')
        logging.getLogger(__name__).info(signal_num)
        logging.getLogger(__name__).info(stack_frame)
        if self.long_poll_thread.is_alive():
            self._stopping = True
            self._async_raise(self.long_poll_thread.ident, SystemExit)

    def _path_checker(self):
        if not os.path.isdir(self._cache_file_path):
            if sys.version_info.major == 3:
                os.makedirs(self._cache_file_path, exist_ok=True)
            else:
                os.makedirs(self._cache_file_path)

    # 更新本地缓存和文件缓存
    def _update_cache_and_file(self, namespace_data, namespace='application'):

        # 更新本地缓存
        self._mycache[namespace] = namespace_data

        # 更新文件缓存
        new_string = json.dumps(namespace_data)
        new_hash = hashlib.md5(new_string.encode('utf-8')).hexdigest()
        if self._hash.get(namespace) == new_hash:
            pass
        else:
            with open(os.path.join(self._cache_file_path, '%s_configuration_%s.txt' % (self.app_id, namespace)),
                      'w') as f:
                f.write(new_string)
            self._hash[namespace] = new_hash

    # 从本地文件获取配置
    def _get_local_cache(self, namespace='application'):
        cache_file_path = os.path.join(self._cache_file_path, '%s_configuration_%s.txt' % (self.app_id, namespace))
        if os.path.isfile(cache_file_path):
            with open(cache_file_path, 'r') as f:
                result = json.loads(f.readline())
            return result
        return {}

    def _long_poll(self):
        notifications = []
        for key in self._mycache:
            namespace_data = self._mycache[key]
            notification_id = -1
            if NOTIFICATION_ID in namespace_data:
                notification_id = self._mycache[key][NOTIFICATION_ID]
            notifications.append({
                NAMESPACE_NAME: key,
                NOTIFICATION_ID: notification_id
            })
        try:
            # 如果长度为0直接返回
            if len(notifications) == 0:
                return
            url = '{}/notifications/v2'.format(self.config_server_url)
            params = {
                'appId': self.app_id,
                'cluster': self.cluster,
                'notifications': json.dumps(notifications, ensure_ascii=False)
            }
            param_str = url_encode_wrapper(params)
            url = url + '?' + param_str
            code, body = http_request(url, self._pull_timeout)
            http_code = code
            if http_code == 304:
                logging.getLogger(__name__).debug('No change, loop...')
                return
            if http_code == 200:
                data = json.loads(body)
                for entry in data:
                    namespace = entry[NAMESPACE_NAME]
                    n_id = entry[NOTIFICATION_ID]
                    logging.getLogger(__name__).info("%s has changes: notificationId=%d", namespace, n_id)
                    self._get_net_and_set_local(namespace, n_id)
                    return
            else:
                logging.getLogger(__name__).warning('Sleep...')
        except Exception as e:
            logging.getLogger(__name__).warning(str(e))

    def _get_net_and_set_local(self, namespace, n_id):
        namespace_data = self.get_json_from_net(namespace)
        namespace_data[NOTIFICATION_ID] = n_id
        self._update_cache_and_file(namespace_data, namespace)

    def _listener(self):
        logging.getLogger(__name__).info('Entering listener loop...')
        while not self._stopping:
            self._long_poll()
            time.sleep(self._cycle_time)
        logging.getLogger(__name__).info("Listener stopped!")
        self.stopped = True

    # 给header增加加签需求
    def _signHeaders(self, url):
        headers = {}
        if self.secret == '':
            return headers
        uri = url[len(self.config_server_url):len(url)]
        time_unix_now = str(int(round(time.time() * 1000)))
        headers['Authorization'] = 'Apollo ' + self.app_id + ':' + signature(time_unix_now, uri, self.secret)
        headers['Timestamp'] = time_unix_now
        return headers
