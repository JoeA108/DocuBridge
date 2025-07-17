from flask import Flask, flash, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "excel_file" not in request.files:
        flash("No file selected")
        return redirect(url_for("index"))

    file = request.files["excel_file"]
    user_question = request.form.get("user_question", "")

    if file.filename == "":
        flash("No file selected")
        return redirect(url_for("index"))

    if file and file.filename.lower().endswith((".xlsx", ".xls")):
        flash(f"File '{file.filename}' uploaded successfully!")
        flash(f"Question received: '{user_question}'")
        return render_template('upload_success.html')
    else:
        flash("Invalid file format. Please upload an Excel file.")
        return redirect(url_for("index")) 

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)


