#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

    from django.core.management import execute_from_command_line
    if sys.argv[1] == "runserver" and len(sys.argv) == 2:
        import settings
        server = "{0}:{1}".format(settings.SERVER_HOST,
                                  settings.SERVER_HOST)
        sys.argv.append(server)
    print sys.argv
    execute_from_command_line(sys.argv)
