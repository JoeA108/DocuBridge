import pandas as pd
from flask import Flask, redirect, render_template, request, url_for
import requests
import os

MODEL = "meta-llama/Llama-3.1-8B-Instruct:novita"

API_URL = "https://router.huggingface.co/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {os.environ['HF_TOKEN']}",
}

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()


app = Flask(__name__)
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
MAX_FILE_SIZE = 5 * 1024 * 1024 


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
error_lookup={
    "#N/A": "Not available",
    "#VALUE!": "Invalid value",
    "#REF!": "There is no reference",
    "#Name?": "Can't find the name",
    "#DIV/0!": "Division by zero",
    "########": "Unable to display value",
    "#NULL!": "Empty value",
    "#NUM!":"Invalid number",
    "#CALC!":"Calculation Error"
}

error_code_list=list(error_lookup.keys())

def scan_for_error(df: pd.DataFrame):
    error_string=""
    values = df.to_numpy()
    
    for row_idx, row in enumerate(values):
        for col_idx, value in enumerate(row):
            if value in error_code_list:
                print("found error")
                error_desc=error_lookup[value]
                error_string += "Row "+ str(row_idx)+ " Column " + str(col_idx) + " Contains the error: " + str(error_desc)

    print(error_string)
    return error_string

@app.route("/")

def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])

@app.route("/upload", methods=["POST"])
def upload_file():
    import traceback
    try:
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

            data = pd.read_excel(file)
            sheet_names = pd.ExcelFile(file).sheet_names
            preview_data = data.head()

            error_string = scan_for_error(preview_data)


            trend_summary = ""
            time_columns = [col for col in data.columns if "date" in col.lower() or "month" in col.lower() or "year" in col.lower()]

            if time_columns:
                time_col = time_columns[0]
                try:
                    data[time_col] = pd.to_datetime(data[time_col], errors="coerce")
                    data = data.sort_values(by=time_col)

                    numeric_cols = data.select_dtypes(include=["number"]).columns
                    if len(numeric_cols) > 0:
                        main_col = numeric_cols[0]
                        start_val = data[main_col].iloc[0]
                        end_val = data[main_col].iloc[-1]
                        peak_val = data[main_col].max()
                        avg_val = data[main_col].mean()
                        trend_direction = "increased" if end_val > start_val else "decreased"

                        trend_summary = f"The {main_col} has {trend_direction} from {start_val:.2f} at the start to {end_val:.2f} at the end, peaking at {peak_val:.2f}. The average value was {avg_val:.2f}."

                except Exception as e:
                    trend_summary = f"Could not compute trend analysis: {str(e)}"

            prompt = (
                f"Here is the preview data: {preview_data}. "
                f"Here is a question: {user_question}. "
                f"Errors detected: {error_string if error_string else 'None'}. "
                f"Trend analysis: {trend_summary if trend_summary else 'No trend data detected.'} "
                "Answer in one sentence."
            )

            response = query({
                "messages": [{"role": "user", "content": prompt}],
                "model": MODEL
            })

            ai_response = response["choices"][0]["message"]["content"].replace("**", "").replace("*", "")

            return render_template(
                'upload_success.html',
                message=f"File received: {file.filename}. Question received: {user_question}",
                filename=file.filename,
                question=user_question,
                sheet_names=sheet_names,
                preview_data=preview_data.to_html(classes='data', header="true"),
                ai_response=ai_response,
                error=False
            )

        else:
            return render_template('upload_success.html', message="Invalid file type. Only .xlsx and .xls are allowed.", filename=file.filename if file else "", question=user_question, ai_response="Unavailable", error=True)

    except Exception as e:
        traceback.print_exc()
        return render_template("upload_success.html", message=f"Internal Server Error: {str(e)}", filename="", question="", ai_response="Unavailable", error=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)