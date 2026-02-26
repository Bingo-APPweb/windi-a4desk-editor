from flask import request, send_file
from studio.renderer import render_procurement_form
import uuid
import os

@app.route("/api/studio/procurement-pdf", methods=["POST"])
def generate_procurement_pdf():
    data = request.json

    filename = f"/tmp/{uuid.uuid4()}.pdf"

    render_procurement_form(data, filename)

    return send_file(filename, as_attachment=True, download_name="procurement.pdf")
