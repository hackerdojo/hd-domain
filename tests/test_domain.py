""" Tests for the admin directories API. """

# We need our external libraries to be present.
import appengine_config

import os
import time
import unittest

from google.appengine.ext import testbed

from oauth2client.client import SignedJwtAssertionCredentials

import domain


""" Test case for the domain class. """
class DomainTests(unittest.TestCase):
  """ Makes the specified number of new users.
  num_users: How many new users to add."""
  def __make_test_users(self, num_users):
    for i in range(0, num_users):
      user = {}
      user["first_name"] = "%s%d" % (self.first_name, len(self.users))
      user["last_name"] = self.last_name
      user["username"] = "%s.%s" % (user["first_name"].lower(),
                                    user["last_name"].lower())
      user["password"] = self.password

      response = self.domain.add_user(user["username"], user["password"],
                                      user["first_name"], user["last_name"])
      user["response"] = response

      self.users.append(user)

    # Occasionally, a rapid request will miss new users, so wait a moment before
    # going on.
    time.sleep(1)

  """ Set up for every test. """
  def setUp(self):
    # Create and activate testbed instance.
    self.testbed = testbed.Testbed()
    self.testbed.activate()

    # The basic names that we will use to test things.
    self.first_name = "Testy"
    self.last_name = "Testerson"
    self.password = "verysecretpassword"

    self.domain = domain.Domain("hackerdojo.com")

    self.users = []

  """ Cleanup for every test. """
  def tearDown(self):
    # Cleanup testing users.
    for user in self.users:
      self.domain.remove_user(user["username"])

    self.testbed.deactivate()

  """ Tests that we can create and delete a test user. """
  def test_create_and_delete(self):
    self.__make_test_users(1)

    response = self.users[0]["response"]
    first_name = self.first_name + "0"
    self.assertEqual(first_name, response["name"]["givenName"])
    self.assertEqual(self.last_name, response["name"]["familyName"])
    self.assertEqual("%s.%s@hackerdojo.com" % (first_name.lower(),
                     self.last_name.lower()), response["primaryEmail"])
    self.assertFalse(response["isAdmin"])

  """ Tests that we can list all the users. """
  def test_list_users(self):
    self.__make_test_users(3)

    users = self.domain.list_users()

    # Our three users should be in here.
    username_format = "%s%d.%s"
    self.assertIn(username_format % (self.first_name.lower(), 0,
        self.last_name.lower()), users)
    self.assertIn(username_format % (self.first_name.lower(), 1,
        self.last_name.lower()), users)
    self.assertIn(username_format % (self.first_name.lower(), 2,
        self.last_name.lower()), users)

  """ Tests that we can list all the groups. """
  def test_list_groups(self):
    # We don't really have mechanisms for adding and removing groups, so it's
    # basically testing that nothing throws an exception.
    print "\nExisting groups: %s" % (self.domain.list_groups())

  """ Tests that we can get data for an individual user. """
  def test_get_user(self):
    self.__make_test_users(1)

    username = "%s%d.%s" % (self.first_name.lower(), 0, self.last_name.lower())
    user_data = self.domain.get_user(username)

    self.assertEqual(self.first_name + "0", user_data["first_name"])
    self.assertEqual(self.last_name, user_data["last_name"])
    self.assertEqual(username, user_data["username"])
    self.assertFalse(user_data["suspended"])
    self.assertFalse(user_data["admin"])

  """ Tests that we can suspend and restore users. """
  def test_suspend_and_restore(self):
    self.__make_test_users(1)
    username = "%s%d.%s" % (self.first_name.lower(), 0, self.last_name.lower())

    user_data = self.domain.get_user(username)
    self.assertFalse(user_data["suspended"])

    user_data = self.domain.suspend_user(username)
    self.assertTrue(user_data["suspended"])

    user_data = self.domain.restore_user(username)
    self.assertFalse(user_data["suspended"])
