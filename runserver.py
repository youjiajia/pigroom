import os
import sys


if __name__ == "__main__":
    env = sys.argv[1] if len(sys.argv) > 1 else 'Local'
    if env not in ['Local', 'Test', 'Stage', 'Production', 'UnitTest']:
        raise EnvironmentError('The environment variable (WXENV) is invalid ')
    os.environ['WXENV'] = env
    from wanx import app
    app.run(host="0.0.0.0", port=8088)
