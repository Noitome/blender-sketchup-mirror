# ops/__init__.py
from . import navigation
from . import push_pull
from . import follow_me
from . import move
from . import rectangle
from . import circle
from . import line
from . import select
from . import offset
from . import transforms

def register():
    navigation.register()
    push_pull.register()
    follow_me.register()
    move.register()
    rectangle.register()
    circle.register()
    line.register()
    select.register()
    offset.register()
    transforms.register()

def unregister():
    transforms.unregister()
    offset.unregister()
    select.unregister()
    line.unregister()
    circle.unregister()
    rectangle.unregister()
    move.unregister()
    follow_me.unregister()
    push_pull.unregister()
    navigation.unregister()
