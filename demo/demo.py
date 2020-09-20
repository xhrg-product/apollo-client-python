#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time:2020.09.12
# @author:xhrg
# @email:634789257@qq.com
import os

from apollo.apollo_client import ApolloClient

apollo_config_url = os.environ.get("APOLLO_CONFIG_URL")

print(apollo_config_url)

client = ApolloClient(app_id="demo-service", cluster="default", config_url=apollo_config_url)
val = client.get_value("name", default_val="defaultVal")

print(val)
