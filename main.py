
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api import urlfetch
from django.utils import simplejson
import gdata.apps.service
from google.appengine.api import memcache
import logging, urllib
import keymaster

def flatten(l):
    out = []
    for item in l:
        if isinstance(item, (list, tuple)):
            out.extend(flatten(item))
        else:
            out.append(item)
    return out

class MainHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Nothing here")

class UsersHandler(webapp.RequestHandler):
    def get(self):
        client = gdata.apps.service.AppsService(domain='hackerdojo.com')
        token = memcache.get('token')
        if token:
            client.SetClientLoginToken(token)
            self.response.out.write(simplejson.dumps(
                [e.title.text for e in flatten([u.entry for u in client.GetGeneratorForAllUsers()])]))
        else:
            request_token()
            self.response.set_status(503)
            self.response.out.write("Refreshing token. Please try again.")
        

class TokenFetchHandler(webapp.RequestHandler):
    def get(self):
        self.post()
        
    def post(self):
        request_token()
        self.response.out.write(memcache.get('token'))
            
def request_token():
    if keymaster.get('domain-pass'):
        client = gdata.apps.service.AppsService(domain='hackerdojo.com')
        client.ClientLogin('jeff@hackerdojo.com', keymaster.get('domain-pass'))
        token = client.GetClientLoginToken()
        if not memcache.set('token', token, 3600*24):
            logging.error("Memcache set failed.")
        else:
            logging.info('Token fetched: %s' % token)
    else:
        keymaster.request('domain-pass')

def main():
    application = webapp.WSGIApplication([
        ('/', MainHandler),
        ('/users', UsersHandler),
        ('/token/fetch', TokenFetchHandler),
        ('/key/(.+)', keymaster.Handler({
            'domain-pass': ('6f7e71752e29e6d4b4e64daceb2a7348', '1iuy010y', request_token),
            })),
        ],debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
