
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api import urlfetch, users
from django.utils import simplejson
import gdata.apps.service
import gdata.apps.groups.service
from google.appengine.api import memcache
import logging, urllib
import keymaster
import time
from datetime import datetime, timedelta
import multipass
import base64

DOMAIN_ACCOUNT = 'api@hackerdojo.com'

def flatten(l):
    out = []
    for item in l:
        if isinstance(item, (list, tuple)):
            out.extend(flatten(item))
        else:
            out.append(item)
    return out

class Domain(object):    
    def __init__(self, domain, token):
        self.domain = domain
        self.apps_client = gdata.apps.service.AppsService(domain=domain)
        self.apps_client.SetClientLoginToken(token)
        self.groups_client = gdata.apps.groups.service.GroupsService(domain=domain)
        self.groups_client.SetClientLoginToken(token)
    
    def _user_dict(self, user):
        return {
            'last_name': user.name.family_name,
            'first_name': user.name.given_name,
            'username': user.login.user_name,
            'suspended': user.login.suspended == 'true',
            'admin': user.login.admin == 'true'}
        
    def groups(self):
        return [g['groupId'].split('@')[0] for g in self.groups_client.RetrieveAllGroups()]
    
    def group(self, group_id):
        return [m['memberId'].split('@')[0] for m in self.groups_client.RetrieveAllMembers(group_id) if m['memberId'].split('@')[1] == self.domain]
    
    def users(self):
        return [e.title.text for e in flatten([u.entry for u in self.apps_client.GetGeneratorForAllUsers()]) if e.login.suspended == 'false']
    
    def user(self, username):
        return self._user_dict(self.apps_client.RetrieveUser(username))
    
    def add_user(self, username, password, first_name, last_name):
        return self._user_dict(self.apps_client.CreateUser(
            user_name   = username,
            password    = password,
            given_name  = first_name,
            family_name = last_name))


class MainHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Try /users or /groups ... %s" % users.get_current_user())


class BaseHandler(webapp.RequestHandler):  
    def domain(self):
        return Domain(DOMAIN_ACCOUNT.split('@')[1], keymaster.get('token'))
      
    def secure(self):
        return keymaster.get(DOMAIN_ACCOUNT) == self.request.get('secret')
    

class GroupsHandler(BaseHandler):
    def get(self):
        groups = self.domain().groups()
        self.response.out.write(simplejson.dumps(groups))

class GroupHandler(BaseHandler):
    def get(self, group_id):
        group = self.domain().group(group_id)
        self.response.out.write(simplejson.dumps(group))

class UsersHandler(BaseHandler):
    def get(self):
        users = self.domain().users()
        self.response.out.write(simplejson.dumps(users))
    
    def post(self):
        if self.secure():
            user = self.domain().add_user(
                username    = self.request.get('username'),
                password    = self.request.get('password'),
                first_name  = self.request.get('first_name'),
                last_name   = self.request.get('last_name'))
            self.response.out.write(simplejson.dumps(user))

class UserHandler(BaseHandler):
    def get(self, username):
        user = self.domain().user(username)
        self.response.out.write(simplejson.dumps(user))

class TokenTask(webapp.RequestHandler):
    def get(self): self.post()
    def post(self):
        client = gdata.apps.service.AppsService(domain=DOMAIN_ACCOUNT.split('@')[1])
        client.ClientLogin(DOMAIN_ACCOUNT, keymaster.get(DOMAIN_ACCOUNT))
        token = client.GetClientLoginToken()
        keymaster.set('token', token)

def Redirect(path):
    class RedirectHandler(webapp.RequestHandler):
        def get(self):
            self.redirect(path)
    return RedirectHandler

class MultipassHandler(webapp.RequestHandler):
    def get(self, action):
        action = urllib.unquote(action)
        to = self.request.GET.get('to')
        if action.startswith('login'):
            user = users.get_current_user()
            if user:
                if ':' in action:
                    action, to = action.split(":")
                    to = base64.b64decode(to)
                token = multipass.token(dict(email=user.email(), expires=(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')))
                self.redirect("%s?sso=%s" % (to, urllib.quote(token)))
            else:
                to = base64.b64encode(to)
                self.redirect(users.create_login_url('/auth/multipass/login:%s' % to))
        elif action.startswith('logout'):
            user = users.get_current_user()
            if user:
                to = base64.b64encode(to or self.request.referrer)
                self.redirect(users.create_logout_url('/auth/multipass/logout:%s' % to))
            else:
                try:
                    action, to = action.split(":")
                    to = base64.b64decode(to)
                except ValueError:
                    pass
                self.redirect(to)
        

def main():
    application = webapp.WSGIApplication([
        ('/', MainHandler),
        ('/auth/login', Redirect(users.create_login_url('/'))),
        ('/auth/logout', Redirect(users.create_logout_url('/'))),
        ('/auth/multipass/(.+)', MultipassHandler),
        ('/users', UsersHandler),
        ('/users/(.+)', UserHandler),
        ('/groups', GroupsHandler),
        ('/groups/(.+)', GroupHandler),
        ('/tasks/token', TokenTask),
        ],debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
