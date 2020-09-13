#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time:2020.09.12
# @author:xhrg
# @email:634789257@qq.com

import hashlib
import sys
import socket

version = sys.version_info.major

if version == 2:
    from .python_2x import *

if version == 3:
    from .python_3x import *

# 定义常量
CONFIGURATIONS = "configurations"
NOTIFICATION_ID = "notificationId"
NAMESPACE_NAME = "namespaceName"


# 对时间戳，uri，秘钥进行加签
def signature(timestamp, uri, secret):
    import hmac
    import base64
    string_to_sign = '' + timestamp + '\n' + uri
    hmac_code = hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha1).digest()
    return base64.b64encode(hmac_code).decode()


def url_encode_wrapper(params):
    return url_encode(params)


# 返回2个值得，第一个是是否存在，第二个是value值
def get_value_from_dict(namespace_cache, key):
    if namespace_cache:
        kv_data = namespace_cache.get(CONFIGURATIONS)
        if kv_data is None:
            return False, None
        if key in kv_data:
            return True, kv_data[key]
    return False, None


def init_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 53))
        ip = s.getsockname()[0]
        return ip
    finally:
        s.close()
    return ""


# 只有None，则返回default_val，如果是空字符串也返回字符串，因为apollo本身是支持空字符串的。
def val_handler(val, default_val):
    if val is None:
        return default_val
    return val
