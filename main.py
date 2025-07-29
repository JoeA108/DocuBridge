import os
import traceback

import pandas as pd
import requests
from flask import Flask, render_template, request, session

# Define the model to be used for AI queries

MODEL = "meta-llama/Llama-3.1-8B-Instruct:novita"

# Set the API URL for AI responses
API_URL = "https://router.huggingface.co/v1/chat/completions"

# Set header for API requests, including authentication token
headers = {
     "Authorization": f"Bearer {os.environ['HF_TOKEN']}",
        }

# Function to query the AI API
def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()["choices"][0]["message"]["content"].replace("**", "").replace("*", "")
        
# Initialize the Flask web application
app = Flask(__name__)

app.secret_key = os.urandom(24)

# Allowed file extensions for uploaded Excel files
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

# Maximum allowed file size in bytes
MAX_FILE_SIZE = 5 * 1024 * 1024 

# Function to check if the uploaded file has an allowed extension
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Dictionary to map Excel error codes to readable strings
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

# List of error codes to check against
error_code_list = list(error_lookup.keys())

# Function to scan a DataFrame for known error codes and return their locations
def scan_for_error(df: pd.DataFrame):
    error_string=""
    values = df.to_numpy()

    for row_idx, row in enumerate(values):
        for col_idx, value in enumerate(row):
            if value in error_code_list:
                print("found error")
                error_desc=error_lookup[value]
                error_string += f"Row {str(row_idx)} Column {str(col_idx)} contains the error: {str(error_desc)}"
    print(error_string)
    return error_string
        
# Route for the home page
@app.route("/")

def index():
    return render_template("index.html")
        
# Route to handle file uploads and associated questions
@app.route("/upload", methods=["POST"])

def upload_file():
    try:    
        # Check if the file part exists in the request
        if "excel_file" not in request.files:
            return render_template('upload_success.html', 
                                    message="No file part in the request.", 
                                    filename="", 
                                    question="", 
                                    error=True
                                  )
            
        file = request.files["excel_file"]
        user_question = request.form.get("user_question")
                
        # Check if the user has provided a question
        if not user_question:
            return render_template('upload_success.html', 
                                    message="No question provided.", 
                                    filename="", 
                                    question="", 
                                    error=True
                                  )
                
        # Validate the uploaded file type and size
        if file and allowed_file(file.filename):
            
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0) 
                
            # Check file size against the maximum allowed
            if file_size > MAX_FILE_SIZE:
                return render_template('upload_success.html', 
                                        message=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024 * 1024):.0f} MB.", 
                                        filename=file.filename, 
                                        question=user_question, 
                                        error=True
                                      )
                
            print(f"File received: {file.filename}")
            print(f"Question received: {user_question}")
                
            # Read the Excel file into a DataFrame and get sheet names
            data = pd.read_excel(file)
            print(data)
            session["data"] = str(data)
            sheet_names = pd.ExcelFile(file).sheet_names
            preview_data = data.head()
                
            # Scan for errors in the preview DataFrame and construct a prompt for the AI
            error_string = scan_for_error(preview_data)
            session["error_string"] = error_string
            
            trend_summary = ""
                
            # Identify potential time-related columns for trend analysis
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
                        
            # Construct the prompt for querying the AI
            prompt = (
                f"Here is the data: {data}. "
                f"Here is a question about the data: {user_question}. "
                f"Errors detected: {error_string if error_string else 'None'} If there are no errors, and the question requires a mathematical calculation (e.g., sum, difference, product, quotient, average, percentage)," 
                 f"identify the relevant numerical columns and perform the necessary operation(s) to answer the question. Don't show how you did that calculation just give the answer. "  
                f"Ensure to handle cases like division by zero appropriately by stating it's undefined or not applicable. " 
                f"Trend analysis: {trend_summary if trend_summary else 'No trend data detected.'} "
                "Analyze the data and answer the question in a single concise sentence, including all necessary calculations and their results." 
            )

            print(prompt)
            
            # Query the AI with the created prompt and retrieve the response
            response = query({
                "messages": [{"role": "user", "content": prompt}],
                "model": MODEL
            })
                
            # Render the success template with the relevant information
            return render_template('upload_success.html',
                                    message=f"File received: {file.filename}. Question received: {user_question}",
                                    filename=file.filename,
                                    question=user_question,
                                    sheet_names=sheet_names,
                                    preview_data=preview_data.to_html(classes='data', header=True),
                                    ai_response=response,
                                    error=False
                                    )
        
        else:
            return render_template('upload_success.html', 
                                   message="Invalid file type. .xlsx and .xls. only. ", 
                                   filename=file.filename if file else "", 
                                   question=user_question, 
                                   ai_response="Unavailable", 
                                   error=True
                                   )
                
    except Exception as e:
        traceback.print_exc()
        # Render an error template if any exception occurs during processing
        return render_template("upload_success.html", 
                               message=f"AI Error: {str(e)}", 
                               filename="", 
                               question="", 
                               ai_response="Unavailable", 
                               error=True
                               )

@app.route("/followup", methods=["POST"])

def followup_question():
    try:
        data = session.get("data")
        filename = request.form.get("filename")
        previous_question = request.form.get("previous_question")
        followup_question = request.form.get("followup_question")
        error_string = session.get("error_string")

        if not followup_question:
            return render_template('upload_success.html',
                                   message="No follow-up question provided.",
                                   filename=filename,
                                   question=previous_question,
                                   error=True
                                   )
            
        
        prompt = (
            f"Here is the previous data: {data}. "
            f"Previous question was: {previous_question}. "
            f"Follow-up question: {followup_question}."
            f"Errors detected: {error_string if error_string else 'None'}. Mention these in your answer"
            f"If there are no errors, and the question requires a mathematical calculation (e.g., sum, difference, product, quotient, average, percentage), " 

                 f"identify the relevant numerical columns and perform the necessary operation(s) to answer the question. Don't show how you did that calculation just give the answer. "  

                 f"Ensure to handle cases like division by zero appropriately by stating it's undefined or not applicable. "  

                 "Analyze the data and answer the question in a single concise sentence, including all necessary calculations and their results." 

             ) 

        response = query({"messages": [{"role": "user", "content": prompt}],
                        "model": MODEL
                        })

        return render_template('upload_success.html',
                               message=f"Follow-up question received: {followup_question}",
                               filename=filename,
                               question=followup_question,
                               ai_response=response,
                               error=False
                               )
    except Exception as e:
        traceback.print_exc()
        return render_template("upload_success.html", 
                                message=f"AI Error: {str(e)}", 
                                filename='', 
                                question='', 
                                ai_response="Unavailable", 
                                error=True)

# Start the Flask application if this script is executed directly
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)