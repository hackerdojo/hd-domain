
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

class BaseHandler(webapp.RequestHandler):
    def login(self):
        self.client = gdata.apps.service.AppsService(domain='hackerdojo.com')
        token = memcache.get('token')
        if token:
            self.client.SetClientLoginToken(token)
            return True
        else:
            request_token()
            self.response.set_status(503)
            self.response.out.write("Refreshing token. Please try again.")
            return False
    
    def secure(self):
        secret = keymaster.get('api-secret')
        if secret:
            return secret == self.request.get('secret')
        else:
            keymaster.request('api-secret')
            self.response.set_status(503)
            self.response.out.write("Refreshing secret. Please try again.")
            return False

def user_dict(user):
    return {
        'last_name': user.name.family_name,
        'first_name': user.name.given_name,
        'username': user.login.user_name,
        'suspended': user.login.suspended == 'true',
        'admin': user.login.admin == 'true'}

class UsersHandler(BaseHandler):
    def get(self):
        if self.login():
            self.response.out.write(simplejson.dumps(
                [e.title.text for e in flatten([u.entry for u in self.client.GetGeneratorForAllUsers()])]))        
    
    def post(self):
        if self.login() and self.secure():
            self.response.out.write(simplejson.dumps(user_dict(self.client.CreateUser(
                user_name=self.request.get('username'),
                password=self.request.get('password'),
                given_name=self.request.get('first_name'),
                family_name=self.request.get('last_name')))))

class UserHandler(BaseHandler):
    def get(self, username):
        if self.login():
            self.response.out.write(simplejson.dumps(user_dict(self.client.RetrieveUser(username))))
            

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
        ('/users/(.+)', UserHandler),
        ('/token/fetch', TokenFetchHandler),
        ('/key/(.+)', keymaster.Handler({
            'domain-pass': ('6f7e71752e29e6d4b4e64daceb2a7348', '1iuy010y', request_token),
            'api-secret': ('fa9985a40110cd254c8a36e00844d0b8', '1nty764u'),
            })),
        ],debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
