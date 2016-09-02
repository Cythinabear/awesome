# 默认的配置文件命名为config_default.py

'''
Default configurations.
'''

__author__ = 'Cythinabear'

configs = {
    'db':{# 定义数据库相关信息
        'host':'127.0.0.1',
        'post':3306,
        'user':'www-data',
        'password':'awesome'
    },
    'session':{
        'secret':'Awesome'
    }
}