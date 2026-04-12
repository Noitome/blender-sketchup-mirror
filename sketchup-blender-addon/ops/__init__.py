# ops/__init__.py
from . import navigation, push_pull, follow_me, move, rectangle, circle

def register():
    navigation.register()
    push_pull.register()
    follow_me.register()
    move.register()
    rectangle.register()
    circle.register()

def unregister():
    rectangle.unregister()
    circle.unregister()
    move.unregister()
    follow_me.unregister()
    push_pull.unregister()
    navigation.unregister()
