"""Run retention cleanup independent of CUDA worker availability."""
from .db import initialize
from .settings import Settings
from .worker import purge_expired


def main():
    settings=Settings.load()
    initialize(settings.data_dir)
    print("expired_projects_deleted=",purge_expired(settings))


if __name__=="__main__":
    main()
