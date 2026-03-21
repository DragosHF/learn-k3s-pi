from flask import Flask

app = Flask(__name__)


@app.route("/")
def hello():
    return "Hello from K3s on Raspberry Pi!"


@app.route("/health")
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
