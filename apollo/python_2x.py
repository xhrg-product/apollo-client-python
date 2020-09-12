#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time:2020.09.12
# @author:xhrg
# @email:634789257@qq.com

import urllib2
from urllib import urlencode


def http_request(url, timeout):
    try:
        res = urllib2.urlopen(url, timeout=timeout)
        body = res.read().decode("utf-8")
        return res.code, body
    except urllib2.HTTPError as e:
        if e.code == 304:
            return 304, None
        raise e


def urlencode(params):
    return urlencode(params)
