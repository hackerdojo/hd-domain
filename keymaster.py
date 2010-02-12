from google.appengine.api import urlfetch, memcache
from google.appengine.ext import webapp
import urllib

_keys = {}

def get(keyname):
    return memcache.get(keyname, namespace='keymaster')
    
def request(keyname):
    urlfetch.fetch('http://www.thekeymaster.org/%s' % _keys[keyname][0], method='POST', payload=urllib.urlencode({'secret': _keys[keyname][1]}), deadline=10)
    
class _Handler(webapp.RequestHandler):
    def get(self, keyname):
        request(keyname)
    
    def post(self, keyname):
        key = self.request.get('key')
        if key:
            memcache.set(keyname, key, namespace='keymaster')
            if len(_keys[keyname]) > 2:
                _keys[keyname][2]()

def Handler(keys):
    global _keys
    _keys = keys
    return _Handler
