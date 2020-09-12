#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time:2020.09.12
# @author:xhrg
# @email:634789257@qq.com

import urllib.request
from urllib.error import HTTPError
from urllib import parse


def http_request(url, timeout):
    try:
        res = urllib.request.urlopen(url, timeout=timeout)
        body = res.read().decode("utf-8")
        return res.code, body
    except HTTPError as e:
        if e.code == 304:
            return 304, None
        raise e


def urlencode(params):
    return parse.urlencode(params)
