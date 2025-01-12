from flask import Flask
from routes.template_routes import template_manager

app = Flask(__name__)

app.register_blueprint(template_manager)

if __name__ == "__main__":
    app.run(debug=True)
