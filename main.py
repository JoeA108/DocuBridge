from flask import Flask, flash, redirect, render_template, request, url_for

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "excel_file" not in request.files:
        return redirect(url_for("index"))

    file = request.files["excel_file"]

    if file.filename == "":
        return redirect(url_for("index"))

    if file and file.filename.lower().endswith((".xlsx", ".xls")):
        return redirect(url_for("index"))
    else:
        return redirect(url_for("index")) 

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)


