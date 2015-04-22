"""
`appengine_config.py` gets loaded every time a new instance is started.

Use this file to configure app engine modules as defined here:
https://developers.google.com/appengine/docs/python/tools/appengineconfig
"""

import os

from google.appengine.ext import vendor

import deploy


# Use external libraries.
required_externals = file("externals/externals.txt").read().split("\n")
have_externals = os.listdir("externals").remove("externals.txt")

for external in required_externals:
  if (external and not external.startswith("#")):
    # Not vertical whitespace or a comment.
    _, _, _, module_name = deploy.make_name(external)

    try:
      vendor.add(os.path.join("externals", module_name))
    except ValueError:
      raise RuntimeError("Could not find external '%s'."
                         " Did you run using deploy.py?" % (external))
