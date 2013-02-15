import base64
import logging
import sys
import time

sys.path.insert(0, 'gdata.zip')
import gdata.apps.service
import gdata.apps.groups.service
from django.utils import simplejson
from google.appengine.api import memcache

from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

from shared.lib import keymaster
from shared import utils


DOMAIN_ACCOUNT = 'api@hackerdojo.com'


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
        return [e.title.text for e in utils.flatten(
            [u.entry for u in self.apps_client.GetGeneratorForAllUsers()]) if e.login.suspended == 'false']
    
    def user(self, username):
        return self._user_dict(self.apps_client.RetrieveUser(username))
    
    def add_user(self, username, password, first_name, last_name):
        return self._user_dict(self.apps_client.CreateUser(
            user_name   = username,
            password    = password,
            given_name  = first_name,
            family_name = last_name))

    def restore_user(self, username):
        return self._user_dict(self.apps_client.RestoreUser(user_name = username))

    def suspend_user(self, username):
        return self._user_dict(self.apps_client.SuspendUser(user_name = username))

class MainHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write("Try /users or /groups ... %s" % users.get_current_user())


class BaseHandler(webapp.RequestHandler):  
    def domain(self):
        return Domain(DOMAIN_ACCOUNT.split('@')[1], get_token())
      
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
        users_str = memcache.get('users_str')
        if not users_str:
            users = self.domain().users()
            users_str = simplejson.dumps(users)
            memcache.set('users_str', users_str)
        self.response.out.write(users_str)
    
    def post(self):
        if self.secure():
            memcache.delete('users_str')

            user = self.domain().add_user(
                username    = self.request.get('username'),
                password    = self.request.get('password'),
                first_name  = self.request.get('first_name'),
                last_name   = self.request.get('last_name'))
            self.response.out.write(simplejson.dumps(user))


class UsersNoCacheHandler(BaseHandler):
    def get(self):
        users = self.domain().users()
        users_str = simplejson.dumps(users)
        memcache.set('users_str', users_str)
        self.response.out.write(users_str)

class SuspendHandler(BaseHandler):
    def get(self, username):
        self.post(username)
    
    def post(self, username):
        if self.secure():
            memcache.delete('users_str')            
            user = self.domain().suspend_user(username=username)
            self.response.out.write(simplejson.dumps(user))

class RestoreHandler(BaseHandler):
    def get(self, username):
        self.post(username)
    
    def post(self, username):
        if self.secure():
            memcache.delete('users_str')            
            user = self.domain().restore_user(username=username)
            self.response.out.write(simplejson.dumps(user))

class UserHandler(BaseHandler):
    def get(self, username):
        user = self.domain().user(username)
        self.response.out.write(simplejson.dumps(user))

def get_token():
    token = memcache.get('token')
    if token is None:
        token = refresh_token()
    return token

def refresh_token():
    client = gdata.apps.service.AppsService(domain=DOMAIN_ACCOUNT.split('@')[1])
    client.ClientLogin(DOMAIN_ACCOUNT, keymaster.get(DOMAIN_ACCOUNT))
    token = client.GetClientLoginToken()
    memcache.set('token', token)
    return token

class TokenTask(webapp.RequestHandler):
    def get(self): self.post()
    def post(self):
        refresh_token()



def main():
    application = webapp.WSGIApplication([
        ('/', MainHandler),
        ('/restore/(.+)', RestoreHandler),
        ('/suspend/(.+)', SuspendHandler),
        ('/users_nocache', UsersNoCacheHandler),
        ('/users', UsersHandler),
        ('/users/(.+)', UserHandler),
        ('/groups', GroupsHandler),
        ('/groups/(.+)', GroupHandler),
        ('/tasks/token', TokenTask),
        ],debug=True)
    run_wsgi_app(application)

if __name__ == '__main__':
    main()
