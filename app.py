from vetflow import create_app
from vetflow.config import config

app = create_app()


if __name__ == "__main__":
    app.run(host=config.API_HOST, port=config.API_PORT)
