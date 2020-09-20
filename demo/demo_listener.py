#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time:2020.09.12
# @author:xhrg
# @email:634789257@qq.com
import os
import time

from apollo.apollo_client import ApolloClient

apollo_config_url = os.environ.get("APOLLO_CONFIG_URL")

print(apollo_config_url)


# ('update', u'application', u'name', u'12311')
# ('update', u'application', u'name', u'12311111111111111111')
# ('delete', u'application', u'aaa', u'vvv111111')
# ('add', u'application', u'cc', u'dd')
def listener(change_type, namespace, key, value):
    print(change_type, namespace, key, value)


client = ApolloClient(app_id="demo-service", cluster="default", config_url=apollo_config_url,
                      change_listener=listener)
val = client.get_value("name", default_val="defaultVal")

print(val)
time.sleep(100)
