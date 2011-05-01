from fabric.api import local

def init():
    """ Initializes submodules """
    local("git submodule init")
    local("git submodule update")