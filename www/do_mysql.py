import orm
import asyncio
import sys
from models import User, Blog, Comment

@asyncio.coroutine
def test(loop):
    yield from orm.create_pool(loop=loop, user='www-data', password='www-data', db='awesome')
    u = User(name='test77',email='test77@test.com',passwd='test',image='about:blank')
    u1 = User(name='test77',email='test55@test.com',passwd='test',image='about:blank')   
    u2 = User(name='test77',email='test44@test.com',passwd='test',image='about:blank')  
    # u = yield from User.find("001472977973753f58eea93e7c24e5194ae5cf0f4271465000")
    yield from u.save()
    yield from u1.save()
    yield from u2.save()
    # yield from u.remove()

loop = asyncio.get_event_loop()
loop.run_until_complete(test(loop))
loop.close()
if loop.is_closed():
    sys.exit(0)