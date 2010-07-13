
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
        self.response.out.write("Nothing here. %s" % users.get_current_user())

class BaseHandler(webapp.RequestHandler):
    def login(self, service=gdata.apps.service.AppsService):
        self.client = service(domain='hackerdojo.com')
        self.client.ClientLogin('api@hackerdojo.com', keymaster.get('api@hackerdojo.com'))
        return True
    
    def secure(self):
        return keymaster.get('api@hackerdojo.com') == self.request.get('secret')

def user_dict(user):
    return {
        'last_name': user.name.family_name,
        'first_name': user.name.given_name,
        'username': user.login.user_name,
        'suspended': user.login.suspended == 'true',
        'admin': user.login.admin == 'true'}

class GroupsHandler(BaseHandler):
    def get(self):
        if self.login(gdata.apps.groups.service.GroupsService):
            self.response.out.write(simplejson.dumps(
                [g['groupId'].split('@')[0] for g in self.client.RetrieveAllGroups()]))

class GroupHandler(BaseHandler):
    def get(self, group_id):
        if self.login(gdata.apps.groups.service.GroupsService):
            self.response.out.write(simplejson.dumps(
                [m['memberId'].split('@')[0] for m in self.client.RetrieveAllMembers(group_id) if m['memberId'].split('@')[1] == 'hackerdojo.com']))

class UsersHandler(BaseHandler):
    def get(self):
        if self.login():
            self.response.out.write(simplejson.dumps(
                [e.title.text for e in flatten([u.entry for u in self.client.GetGeneratorForAllUsers()]) if e.login.suspended == 'false']))        
    
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
        ],debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
