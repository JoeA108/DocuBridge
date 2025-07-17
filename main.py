from flask import Flask, redirect, render_template, request, url_for
import os

app = Flask(__name__)
app.secret_key = "your_secret_key_here" 
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
MAX_FILE_SIZE = 5 * 1024 * 1024 

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "excel_file" not in request.files:
        return render_template('upload_success.html', message="No file part in the request.", filename="", question="", error=True)

    file = request.files["excel_file"]
    user_question = request.form.get("user_question")

    if file.filename == "":
        return render_template('upload_success.html', message="No selected file.", filename="", question="", error=True)

    if not user_question:
        return render_template('upload_success.html', message="No question provided.", filename="", question="", error=True)

    if file and allowed_file(file.filename):
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0) 

        if file_size > MAX_FILE_SIZE:
            return render_template('upload_success.html', message=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024 * 1024):.0f} MB.", filename=file.filename, question=user_question, error=True)

        print(f"File received: {file.filename}")
        print(f"Question received: {user_question}")
        return render_template('upload_success.html', message=f"File received: {file.filename}. Question received: {user_question}", filename=file.filename, question=user_question, error=False)
    else:
        return render_template('upload_success.html', message="Invalid file type. Only .xlsx and .xls are allowed.", filename=file.filename if file else "", question=user_question, error=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)