#web   app编写

'''
async web application.
'''

import logging

# 设置日志等级,默认为WARNING.只有指定级别或更高级的才会被追踪记录
logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader
# 从jinja2模板库导入环境与文件系统加载器

import orm
from coroweb import add_routes, add_static

def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    # 设置jinja2的Environment参数    
    options = dict(
        autoescape = kw.get('autoescape', True), # 自动转义xml/html的特殊字符
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        variable_start_string = kw.get('variable_start_string', '{{'), # 变量开始标志
        variable_end_string = kw.get('variable_end_string', '}}'),
        auto_reload = kw.get('auto_reload', True)# 每当对模板发起请求,加载器首先检查模板是否发生改变.若是,则重载模板
    )
    path = kw.get('path', None)# 若关键字参数指定了path,将其赋给path变量, 否则path置为None
    if path is None:
        # 若路径不存在,则将当前目录下的templates(www/templates/)设为jinja2的目录
        # os.path.abspath(__file__), 返回当前脚本的绝对路径(包括文件名)
        # os.path.dirname(), 去掉文件名,返回目录路径
        # os.path.join(), 将分离的各部分组合成一个路径名
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
    # 初始化jinja2环境, options参数,之前已经进行过设置
    # 加载器负责从指定位置加载模板, 此处选择FileSystemLoader,顾名思义就是从文件系统加载模板,前面我们已经设置了path
    env = Environment(loader=FileSystemLoader(path), **options)
    # 设置过滤器
    # 先通过filters关键字参数获取过滤字典
    # 再通过建立env.filters的键值对建立过滤器
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env# 将jinja环境赋给app的__templating__属性

# 一个记录URL日志的logger可以简单定义：
# 每个middle factory接收2个参数,一个app实例,一个handler, 并返回一个新的handler
async def logger_factory(app, handler):
    async def logger(request):
        # 记录日志,包括http method, 和path
        logging.info('Request: %s %s' % (request.method, request.path))
        # 日志记录完毕之后, 调用传入的handler继续处理请求
        # await asyncio.sleep(0.3)
        return (await handler(request))
    return logger

#解析数据
async def data_factory(app, handler):
    async def parse_data(request):
# 解析数据是针对post方法传来的数据,若http method非post,将跳过,直接调用handler处理请求
        if request.method == 'POST':
            # content_type字段表示post的消息主体的类型, 以application/json打头表示消息主体为json
            # request.json方法,读取消息主题,并以utf-8解码
            # 将消息主体存入请求的__data__属性
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            # content type字段以application/x-www-form-urlencodeed打头的,是浏览器表单
            # request.post方法读取post来的消息主体,即表单信息
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form: %s' % str(request.__data__))
        return (await handler(request))# 调用传入的handler继续处理请求
    return parse_data

# 上面factory是在url处理函数之前先对请求进行了处理,以下则在url处理函数之后进行处理
# 其将request handler的返回值转换为web.Response对象
async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...')
        r = await handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))
        # default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response

def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

async def init(loop):
    await orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='www', password='www', db='awesome')
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory
    ])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'handlers')
    add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()