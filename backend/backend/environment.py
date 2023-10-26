import os
import environ

env = environ.Env(DEBUG=(bool, False))
current_path = environ.Path(__file__) - 1
env_file = current_path(".env")

if os.path.exists(env_file):  # pragma: no cover
    environ.Env.read_env(env_file=env_file)
