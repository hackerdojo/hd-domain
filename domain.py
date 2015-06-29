""" Class for accessing data about a domain using the admin directories API. """


import json
import logging
import os

from apiclient.discovery import _add_query_parameter
from apiclient.discovery import build_from_document
from apiclient.discovery import DISCOVERY_URI
from apiclient.errors import HttpError

from google.appengine.api.app_identity import get_application_id
from google.appengine.api import memcache, urlfetch

import httplib2

from oauth2client.client import SignedJwtAssertionCredentials

import uritemplate


class Domain:
  _OAUTH_SCOPES = ["https://www.googleapis.com/auth/admin.directory.user",
                   "https://www.googleapis.com/auth/admin.directory.group"]
  _CLIENT_EMAIL = \
      "1007593845094-0f7l6inabhc81ra9cm2d5ib7iutldepu" \
      "@developer.gserviceaccount.com"

  """ domain: The google apps domain. """
  def __init__(self, domain):
    # Make it wait a little longer before aborting fetches.
    urlfetch.set_default_fetch_deadline(30)

    self.domain = domain

    self.__authorize_http_instance()
    discovery_doc = self.__get_discovery_doc("admin", "directory_v1",
                                             http=self.authorized_http)
    self.service = build_from_document(discovery_doc,
                                       http=self.authorized_http)

    self.users = self.service.users()
    self.groups = self.service.groups()
    self.members = self.service.members()

  """ Retrieves and stores the discovery document for a given API so that we
  don't have to do it every time a request comes in. Most of the code is taken
  from here:
  https://cloud.google.com/appengine/articles/
          efficient_use_of_discovery_based_apis
  If a discovery doc is already in the memcache, it uses that instead.
  It takes the same arguments as the discovery build function.
  Returns: The contents of the discovery doc. """
  def __get_discovery_doc(self, service_name, version, http=None,
                            discovery_service_url=DISCOVERY_URI):
    # Returned a cached copy if we have it.
    cached = memcache.get("discovery_doc")
    if cached:
      return cached
    logging.info("Cache miss in discovery document.")

    params = {'api': service_name, 'apiVersion': version}
    requested_url = uritemplate.expand(discovery_service_url, params)

    # REMOTE_ADDR is defined by the CGI spec [RFC3875] as the environment
    # variable that contains the network address of the client sending the
    # request. If it exists then add that to the request for the discovery
    # document to avoid exceeding the quota on discovery requests.
    if 'REMOTE_ADDR' in os.environ:
      requested_url = _add_query_parameter(requested_url, 'userIp',
                                          os.environ['REMOTE_ADDR'])

    http = http or httplib2.Http()
    resp, content = http.request(requested_url)
    if resp.status >= 400:
      raise HttpError(resp, content, uri=requested_url)

    # Store it in the memcache.
    memcache.set("discovery_doc", content, time=60 * 60 * 24)

    return content

  """ Creates and authorizes an httplib2.Http instance with oauth2. """
  def __authorize_http_instance(self):
    # Get the key.
    try:
      private_key = file("hd-domain-hrd.pem", "rb").read()
    except IOError:
      raise IOError("Could not find hd-domain-hrd.pem file. Did you create it?")

    logging.debug("Authorizing for scopes: %s." % (self._OAUTH_SCOPES))
    credentials = SignedJwtAssertionCredentials(self._CLIENT_EMAIL,
        private_key, scope=self._OAUTH_SCOPES,
        sub="daniel.petti@hackerdojo.com")

    self.authorized_http = credentials.authorize(httplib2.Http(cache=memcache))

  """ Stores the critical information from a user response in a nice dict.
  Returns: A dict with the following keys:
      last_name: User's last name.
      first_name: User's first name.
      username: User's username.
      suspended: Whether user is suspended.
      admin: Whether user is an admin.
  """
  def __user_dict(self, user):
    return {
        'last_name': user["name"]["familyName"],
        'first_name': user["name"]["givenName"],
        'username': user["primaryEmail"].split("@")[0],
        'suspended': user["suspended"],
        'admin': user["isAdmin"]}

  """ Builds a request for user creation with the given parameters.
  first_name: User's first name.
  last_name: User's last name.
  username: The username of the user.
  password: The user's password.
  Returns: A string that can be passed to users.insert. """
  def __make_user_request(self, first_name, last_name, username, password):
    email = "%s@hackerdojo.com" % (username)
    user_dict = {"name": {"givenName": first_name, "familyName": last_name},
                 "primaryEmail": email, "password": password}
    return user_dict

  """ Processes a request that returns paginated results.
  request: The request object to process.
  next_func: The function to call for getting the next page. Should take
             arguments previous request and response.
  Returns: A list of the responses for all the pages. """
  def __get_all_pages(self, request, next_func):
    response = request.execute()
    pages = [response]

    # We have to get all the pages of the response.
    while True:
      request = next_func(request, response)
      if not request:
        # No more pages.
        break

      response = request.execute()
      logging.debug("Got response: %s" % (response))
      pages.append(response)

    return pages

  """ Lists all the groups on the domain.
  Returns: A list of the first part (without the "@hackerdojo") of each group's
           email. """
  def list_groups(self):
    request = self.groups.list(domain=self.domain)
    pages = self.__get_all_pages(request, self.groups.list_next)

    groups = []
    for page in pages:
      groups.extend(page["groups"])

    return [g["email"].split('@')[0] for g in groups]

  """ Gets the users in a specific group.
  group_id: The first part of the group's email. (without the "@hackerdojo")
  Returns: A dictionary containing usernames for all the members of the group.
  """
  def get_group_members(self, group_id):
    email = "%s@%s" % (group_id, self.domain)
    request = self.members.list(groupKey=email)
    pages = self.__get_all_pages(request, self.members.list_next)

    emails = []
    for page in pages:
      emails.extend([member["email"] for member in page["members"]])

    return [email.split("@")[0] for email in emails]

  """ Lists all the users on the domain.
  Returns: A list of the usernames of all the users. """
  def list_users(self):
    request = self.users.list(domain=self.domain)
    pages = self.__get_all_pages(request, self.users.list_next)

    users = []
    for page in pages:
      users.extend(page["users"])

    return [u["primaryEmail"].split("@")[0] for u in users]

  """ Gets information for a specific user.
  username: The username of the user to get information for.
  Retruns: A dictionary. See documentation for the __user_dict return value for
           what it looks like. """
  def get_user(self, username):
    email = "%s@%s" % (username, self.domain)
    return self.__user_dict(self.users.get(userKey=email).execute())

  """ Adds a new user to the domain.
  username: The username of the user.
  password: The user's password.
  first_name: The user's first name.
  last_name: The user's last name.
  Returns: A dictionary with information about the new user, including their
           name and primary email. """
  def add_user(self, username, password, first_name, last_name):
    user_info = self.__make_user_request(first_name, last_name, username,
                                         password)
    response = self.users.insert(body=user_info).execute()
    logging.debug("Got response: %s" % (response))
    return response

  """ Removes a user from the domain.
  username: The username of the user to remove. """
  def remove_user(self, username):
    email = "%s@%s" % (username, self.domain)
    self.users.delete(userKey=email).execute()

  """ Restores a user that has been suspended.
  username: The username of the user to restore.
  Returns: A dictionary with information about the user, including their name
           and primary email. """
  def restore_user(self, username):
    patch_body = {"suspended": False}
    email = "%s@%s" % (username, self.domain)

    response = self.users.patch(userKey=email, body=patch_body).execute()
    logging.debug("Got response: %s" % (response))
    return self.__user_dict(response)

  """ Suspends a user.
  username: The username of the user to suspend.
  Returns: A dictionary with information about the user, including their name
           and primary email. """
  def suspend_user(self, username):
    patch_body = {"suspended": True}
    email = "%s@%s" % (username, self.domain)

    response = self.users.patch(userKey=email, body=patch_body).execute()
    logging.debug("Got response: %s" % (response))
    return self.__user_dict(response)
