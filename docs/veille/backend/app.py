from flask import Flask
from flask_cors import CORS

from routes_actualites import bp as bp_actualites
from routes_reglementaire import bp as bp_reglementaire
from routes_pdf_proxy import bp as bp_pdf_proxy

app = Flask(__name__)
CORS(app)

app.register_blueprint(bp_actualites)
app.register_blueprint(bp_reglementaire)
app.register_blueprint(bp_pdf_proxy)

if __name__ == "__main__":
    app.run(port=8002, debug=True)
