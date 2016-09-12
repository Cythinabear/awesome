__author__ = 'Cythina bear'

' url handlers '

import re, time, json, logging, hashlib, base64, asyncio

from coroweb import get, post

from models import User, Comment, Blog, next_id
from apis import APIResourceNotFoundError, APIValueError, APIError, APIPermissionError, Page
from config import configs


# 此处所列所有的handler都会在app.py中通过add_routes自动注册到app.router上
# 因此,在此脚本尽情地书写request handler即可

COOKIE_NAME = 'awesession'             # cookie名,用于设置cookie
_COOKIE_KEY = configs.session.secret   # cookie密钥,作为加密cookie的原始字符串的一部分

# 匹配邮箱与加密后密码的证得表达式
_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'[0-9a-f]{40}$')

def user2cookie(user, max_age):
    '''Generate cookies str by user.'''
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))# expires(失效时间)是当前时间加上cookie最大存活时间的字符串
    # 利用用户id,加密后的密码,失效时间,加上cookie密钥,组合成待加密的原始字符串
    s = "%s-%s-%s-%s" % (user.id, user.passwd, expires, _COOKIE_KEY)
    # 生成加密的字符串,并与用户id,失效时间共同组成cookie
    L = [user.id, expires, hashlib.sha1(s.encode("utf-8")).hexdigest()]
    return "-".join(L) 

# 解密cookie
@asyncio.coroutine
def cookie2user(cookie_str):
    '''Parse cookie and load user if cookie is valid'''
    # cookie_str就是user2cookie函数的返回值
    if not cookie_str:
        return None
    try:
            # 解密是加密的逆向过程,因此,先通过'-'拆分cookie,得到用户id,失效时间,以及加密字符串
        L = cookie_str.split("-")#返回一个str的list
        if len(L) != 3: # 由上可知,cookie由3部分组成,若拆分得到不是3部分,显然出错了
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time(): # 时间是浮点表示的时间戳,一直在增大.因此失效时间小于当前时间,说明cookie已失效
            return None
        user = yield from User.find(uid)  # 在拆分得到的id在数据库中查找用户信息
        if user is None:
            return None
        # 利用用户id,加密后的密码,失效时间,加上cookie密钥,组合成待加密的原始字符串
        # 再对其进行加密,与从cookie分解得到的sha1进行比较.若相等,则该cookie合法
        s = "%s-%s-%s-%s" % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode("utf-8")).hexdigest():
            logging.info("invalid sha1")
            return None
        # 验证cookie,就是为了验证当前用户是否仍登录着,从而使用户不必重新登录
        # 因此,返回用户信息即可
        user.passwd = "*****"
        return user
    except Exception as e:
        logging.exception(e)
    return None

# 对于首页的get请求的处理
@get('/')
async def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200)
    ]
    return {
        '__template__': 'blogs.html',
        'blogs': blogs
    }

#Day10未完待续



# API: 获取用户信息
@get('/api/users')
async def api_get_users():
    users = await User.findAll(orderBy='created_at desc')
    for u in users:
        u.passwd = '******'
    return dict(users=users)
