
import os
import re
import uuid
import base64

import cv2
import easyocr
import numpy as np

from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

print("Loading OCR model...")
reader = easyocr.Reader(["en"], gpu=False)
print("OCR model loaded!")


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def recognize_number(image):
    height, width = image.shape[:2]

    scale = min(1, 1200 / max(height, width))

    if scale < 1:
        image = cv2.resize(
            image,
            (int(width * scale), int(height * scale))
        )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    edges = cv2.Canny(gray, 30, 200)

    contours, _ = cv2.findContours(
        edges,
        cv2.RETR_TREE,
        cv2.CHAIN_APPROX_SIMPLE
    )

    contours = sorted(
        contours,
        key=cv2.contourArea,
        reverse=True
    )[:40]

    plate = None
    best_area = 0

    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(
            contour, 0.02 * perimeter, True
        )

        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            ratio = w / float(h)
            area = w * h

            if 2.0 <= ratio <= 6.5 and area > best_area:
                best_area = area
                plate = image[y:y+h, x:x+w]

    if plate is None:
        plate = image

    gray_plate = cv2.cvtColor(
        plate, cv2.COLOR_BGR2GRAY
    )

    gray_plate = cv2.resize(
        gray_plate, None,
        fx=2, fy=2,
        interpolation=cv2.INTER_CUBIC
    )

    results = reader.readtext(gray_plate)

    detected = []

    for result in results:
        text = result[1].upper()
        cleaned = re.sub(r"[^A-Z0-9]", "", text)

        if cleaned:
            detected.append(cleaned)

    return " ".join(detected), plate


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/recognize", methods=["POST"])
def recognize_upload():

    if "vehicle_image" not in request.files:
        return "Please select an image", 400

    file = request.files["vehicle_image"]

    if not file.filename:
        return "No image selected", 400

    if not allowed_file(file.filename):
        return "Invalid image format", 400

    filename = secure_filename(file.filename)
    unique_name = str(uuid.uuid4()) + "_" + filename

    filepath = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(filepath)

    image = cv2.imread(filepath)

    if image is None:
        return "Invalid image", 400

    number, plate = recognize_number(image)

    plate_name = "plate_" + unique_name
    plate_path = os.path.join(UPLOAD_FOLDER, plate_name)

    cv2.imwrite(plate_path, plate)

    return render_template(
        "result.html",
        number=number or "Number not recognized",
        image_url="/" + filepath,
        plate_url="/" + plate_path
    )


@app.route("/recognize-frame", methods=["POST"])
def recognize_frame():

    data = request.get_json(silent=True) or {}
    image_data = data.get("image", "")

    if not image_data.startswith("data:image/"):
        return jsonify({"error": "Invalid image"}), 400

    try:
        encoded = image_data.split(",", 1)[1]
        decoded = base64.b64decode(encoded, validate=True)

        if len(decoded) > 5 * 1024 * 1024:
            return jsonify({"error": "Image too large"}), 400

        array = np.frombuffer(decoded, np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)

        if image is None:
            return jsonify({"error": "Invalid image"}), 400

        number, plate = recognize_number(image)

        return jsonify({
            "number": number or "Number not recognized"
        })

    except Exception as error:
        print(error)
        return jsonify({"error": "Recognition failed"}), 500


@app.errorhandler(413)
def too_large(error):
    return "Image must be smaller than 10 MB", 413


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
      
