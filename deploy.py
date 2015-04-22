#!/usr/bin/python

import argparse
import os
import re
import shutil
import subprocess
import sys
import unittest


""" Generates a name for the directory that this module will reside in.
external: The line from externals.txt for this external.
Returns: A tuple of four containing the name, comparator, and version for this
external as well as the generated module directory name. """
def make_name(external):
  name, comparison, version = external.split()

  module_name = "%s_v%s" % (name, version)
  return (name, comparison, version, module_name)


""" Make sure that we have the proper version of the required external library.
external: The external dependency to check for.
"""
def get_external(external):
  """ Compares versions.
  installed: The version installed.
  needed: The version required.
  comparator: The logical operand to use.
  Returns: True if the installed version fits the requirements, False otherwise.
  """
  def compare_versions(installed, needed, comparator):
    return eval("%s %s %s" % (installed, comparator, needed))

  try:
    name, comparison, version, module_name = make_name(external)
  except ValueError:
    print "ERROR: Could not parse line '%s' in externals.txt." % (external)
    os._exit(1)

  # Get all the subdirectories where we've installed modules.
  subdirectories = [x for x in os.listdir("externals") \
      if os.path.isdir(os.path.join("externals", x))]

  # Remove anything extraneous.
  to_delete = []
  for installed in subdirectories:
    # Check that it matches the form of the names we give directories for
    # installed modules.
    if not re.findall(r"\w+\_v\d+", installed):
      to_delete.append(installed)
  for item in to_delete:
    subdirectories.remove(item)

  # Delete any other versions of the module.
  for installed in subdirectories:
    have_name, have_version = installed.split("_v")
    if have_name == name:
      if compare_versions(have_version, version, comparison):
        # We already have it; we're done.
        return
      else:
        # Wrong version.
        print "Found unusable version of '%s'" % (name)
        shutil.rmtree(os.path.join("externals", installed))

  os.mkdir(os.path.join("externals", module_name))

  pip_location = get_location("pip")

  # Install the module.
  try:
    subprocess.check_call([os.path.join(pip_location, "pip"), "install", "-t",
        os.path.join("externals", module_name), external.replace(" ", "")])
  except subprocess.CalledProcessError:
    print "ERROR: Installation of '%s' failed." % (name)
    os._exit(0)

""" Runs all the unit tests.
sdk_path: The path to the appengine sdk.
Returns: True or False depending on whether tests succeed. """
def run_tests(sdk_path, *args):
    sys.path.insert(0, sdk_path)
    import dev_appserver
    dev_appserver.fix_sys_path()

    suite = unittest.loader.TestLoader().discover("tests")
    test_result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not test_result.wasSuccessful():
      print "ERROR: Unit tests failed."
      return False

    return True

""" Runs the dev server.
sdk_location: Path to the GAE sdk.
args: Options from the command line.
forward_args: Arguments to forward to dev_appserver. """
def dev_server(sdk_location, args, forward_args):
  if (not run_tests(sdk_location) and not args.force):
    os._exit(1)

  command = [os.path.join(sdk_location, "dev_appserver.py"), "app.yaml"]
  command.extend(forward_args)
  try:
    subprocess.call(command)
  except KeyboardInterrupt:
    # User killed the dev server.
    return

""" Uses appcfg.py to update the application.
sdk_location: Path to the GAE sdk.
args: Options from the command line.
forward_args: Arguments to forward to appcfg. """
def gae_update(sdk_location, args, forward_args):
  if (not run_tests(sdk_location) and not args.force):
    os._exit(1)

  command = [os.path.join(sdk_location, "appcfg.py"), "update", "app.yaml"]
  command.extend(forward_args)
  subprocess.call(command)

""" Figures out where a particular executable is located on the user's system.
program: The name of the executable to find.
Returns: The path to the program. """
def get_location(program):
  # Get the location of the GAE installation.
  try:
    output = subprocess.check_output(["/usr/bin/which", program])
  except subprocess.CalledProcessError:
    print "ERROR: Could not find '%s'." % (program)
    os._exit(1)

  location = output.decode("utf-8").rstrip("%s\n" % (program))
  return location

def main():
  # Parse options.
  parser = argparse.ArgumentParser( \
      description="Safely deploy and test application.")
  parser.add_argument("-f", "--force", action="store_true",
      help="Takes requested action even if unit tests fail.")
  subparsers = parser.add_subparsers()
  test_parser = subparsers.add_parser("test",
      help="Runs the unit tests and exits.")
  dev_server_parser = subparsers.add_parser("dev-server",
      help="Runs the dev server")
  update_parser = subparsers.add_parser("update",
      help="Updates the application on GAE.")

  test_parser.set_defaults(func=run_tests)
  dev_server_parser.set_defaults(func=dev_server)
  update_parser.set_defaults(func=gae_update)

  args, forward_args = parser.parse_known_args()

  # Get the location of the GAE installation.
  gae_installation = get_location("appcfg.py")
  print "Using gae installation directory: %s" % (gae_installation)

  # Check for required packages. Pip can't be trusted to deal with
  # already-installed packages correctly, so we're going to install each one
  # separately.
  required = open("externals/externals.txt").read().split("\n")
  for requirement in required:
    if (requirement and not requirement.startswith("#")):
      # Not a comment or vertical whitespace.
      get_external(requirement)

  # Do the requested action.
  if not args.func(gae_installation, args, forward_args):
    os._exit(1)


if __name__ == "__main__":
  main()
