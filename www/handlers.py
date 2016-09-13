__author__ = 'Cythina bear'

' url handlers '

import re, time, json, logging, hashlib, base64, asyncio

from coroweb import get, post

from models import User, Comment, Blog, next_id
from apis import APIResourceNotFoundError, APIValueError, APIError, APIPermissionError
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

@get('/register')
def register():
    return{
        '__template__': 'register.html'
    }

@get('/signin')
def signin():
    return{
        '__template__': 'signin.html'
    }

@get('/signout')
def signout(request):
    # 请求头部的referer,表示从哪里链接到当前页面,即上一个页面
    # 用户登出时,实际转到了/signout路径下,因此为了使登出毫无维和感,获得"当前"url
    referer = request.headers.get("Referer")
    # 若无前一个网址,可能是用户新打开了一个标签页,则登录后转到首页
    r = web.HTTPFound(referer or '/')
    # 以设置cookie的最大存活时间来删除cookie
    r.set_cookies(COOKIES_NAME, "-deleted-", max_age=0, httponly=True)
    logging.info("user sign out.")
    return r


# API: 获取用户信息
@get('/api/users')
async def api_get_users():
    page_index = get_page_index
    num = await User.findNumber("count(id)")
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = await User.findAll(orderBy='created_at desc')
    for u in users:
        u.passwd = '******'
    # 以dict形式返回,并且未指定__template__,将被app.py的response factory处理为json
    return dict(page=p, users=users)

# API: 创建用户
@post('/api/users')
def api_register_user(*,name, email, passwd): # 注册信息包括用户名,邮箱与密码
    # 验证输入的正确性
    if not name or not name.strip():
        raise APIValueError("name")
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError("email")
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError("passwd")
    # 在数据库里查看是否已存在该email
    users = yield from User.findAll('email=?', [email]) # mysql parameters are listed in list
    if len(users) > 0: # findAll的结果不为0,说明数据库已存在同名email,抛出异常报错
        raise APIError('register:failed', 'email', 'Email is already in use.')

    # 数据库内无相应的email信息,说明是第一次注册
    uid = next_id() # 利用当前时间与随机生成的uuid生成user id
    sha1_passwd = '%s:%s' % (uid, passwd) # 将user id与密码的组合赋给sha1_passwd变量
    # 创建用户对象, 其中密码并不是用户输入的密码,而是经过复杂处理后的保密字符串
    # unicode对象在进行哈希运算之前必须先编码
    # sha1(secure hash algorithm),是一种不可逆的安全算法.这在一定程度上保证了安全性,因为用户密码只有用户一个人知道
    # hexdigest()函数将hash对象转换成16进制表示的字符串
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image="http://www.gravatar.com/avatar/%s?d=mm&s=120" % hashlib.md5(email.encode('utf-8')).hexdigest())
    yield from user.save() # 将用户信息储存到数据库中,save()方法封装的实际是数据库的insert操作

    # 这其实还是一个handler,因此需要返回response. 此时返回的response是带有cookie的响应
    r = web.Response()
    # 刚创建的的用户设置cookiei(网站为了辨别用户身份而储存在用户本地终端的数据)
    # http协议是一种无状态的协议,即服务器并不知道用户上一次做了什么.
    # 因此服务器可以通过设置或读取Cookies中包含信息,借此维护用户跟服务器会话中的状态
    # user2cookie设置的是cookie的值
    # max_age是cookie的最大存活周期,单位是秒.当时间结束时,客户端将抛弃该cookie.之后需要重新登录
    r.set_cookie(COOKIE_NAME, user2cookie(user, 600), max_age=600, httponly=True)  # 设置cookie最大存会时间为10min
    # r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)  #86400s=24h
    user.passwd = '*****' # 修改密码的外部显示为*
    # 设置content_type,将在data_factory中间件中继续处理
    r.content_type = 'application/json'
    # json.dumps方法将对象序列化为json格式
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

# API: 用户验证
@post("/api/authenticate")
def authenticate(*, email, passwd): # 通过邮箱与密码验证登录
    # 验证邮箱与密码的合法性
    if not email:
        raise APIValueError("email", "Invalid email")
    if not passwd:
        raise APIValueError("passwd", "Invalid password")
    users = yield from User.findAll("email=?", [email]) # 在数据库中查找email,将以list形式返回
    if len(users) == 0: # 查询结果为空,即数据库中没有相应的email记录,说明用户不存在
        raise APIValueError("email", "Email not exits")
    user = users[0] # 取得用户记录.事实上,就只有一条用户记录,只不过返回的是list
    # 验证密码
    # 数据库中存储的并非原始的用户密码,而是加密的字符串
    # 我们对此时用户输入的密码做相同的加密操作,将结果与数据库中储存的密码比较,来验证密码的正确性
    # 以下步骤合成为一步就是:sha1 = hashlib.sha1((user.id+":"+passwd).encode("utf-8"))
    # 对照用户时对原始密码的操作(见api_register_user),操作完全一样
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode("utf-8"))
    sha1.update(b":")
    sha1.update(passwd.encode("utf-8"))
    if user.passwd != sha1.hexdigest():
        raise APIValueError("passwd", "Invalid password")
    # 用户登录之后,同样的设置一个cookie,与注册用户部分的代码完全一样
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 600), max_age=600, httponly=True)
    # r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    # r.set_cookie(COOKIE_NAME, user2cookie(user, 600), max_age=600, httponly=True)
    user.passwd = "*****"
    r.content_type = "application/json"
    r.body = json.dumps(user, ensure_ascii=False).encode("utf-8")
    return r