import os
import traceback

import re
import pandas as pd
import requests
from flask import Flask, render_template, request, session

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64

# Set the model to be used for AI responses
MODEL = "deepseek-ai/DeepSeek-R1:novita"  

# Set the API URL for AI responses
API_URL = "https://router.huggingface.co/v1/chat/completions"

# Set header for API requests, including authentication token
headers = {
     "Authorization": f"Bearer {os.environ['HF_TOKEN']}",
        }

# Function to query the AI API
def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    print(response.json())
    cleaned_response = re.sub(r'<think>.*?</think>', '', 
                                response.json()["choices"][0]["message"]["content"],                          
                                flags=re.DOTALL
                              )
    return cleaned_response
        
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
                                    message="No file part in the request, please submit a file before asking a question.", 
                                    filename="", 
                                    question="", 
                                    error=True
                                  )
            
        file = request.files["excel_file"] # Get the uploaded file
        user_question = request.form.get("user_question") # Get the user's question
                
        # Check if the user has provided a question
        if not user_question:
            return render_template('upload_success.html', 
                                    message="No question provided, please try typing a question into the text area.", 
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
                                        message=f"File too large, please try uploading a smaller file. Maximum size is {MAX_FILE_SIZE / (1024 * 1024):.0f} MB.", 
                                        filename=file.filename, 
                                        question=user_question, 
                                        error=True
                                      )
                
            # Read the Excel file into a DataFrame and get sheet names
            data = pd.read_excel(file)
            print(data)
            session["data"] = str(data) # Store data in session for follow-up
            sheet_names = pd.ExcelFile(file).sheet_names
            preview_data = data.head()
                
            # Scan for errors in the preview DataFrame and construct a prompt for the AI
            error_string = scan_for_error(preview_data)
            session["error_string"] = error_string # Store error string in session for follow-up
            
            trend_summary = ""
            chart_img = None
                
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
                        
                        # Generate trend chart
                        plt.figure(figsize=(6, 4))
                        plt.plot(data[time_col], data[main_col], marker='o', color='#3b3575')
                        plt.title(f"Trend of {main_col} Over Time", fontsize=14)
                        plt.xlabel(time_col.capitalize())
                        #plt.ylabel(main_col)
                        plt.grid(True)
                        plt.tight_layout()

                        # Save to base64
                        img = io.BytesIO()
                        plt.savefig(img, format='png')
                        img.seek(0)
                        chart_img = base64.b64encode(img.getvalue()).decode('utf-8')
                        plt.close()
                except Exception as e:
                    trend_summary = f"Could not compute trend analysis: {str(e)}"
                    chart_img = None

                        
            # Construct the prompt for querying the AI
            prompt = (
                f"Here is the data: {data}. "
                f"Here is a question about the data: {user_question}. "
                f"Errors detected: {error_string if error_string else 'None'} If there are no errors, don't mention that unless prompted."  
                "Ensure to handle cases like division by zero appropriately by stating it's undefined or not applicable. " 
                f"Trend analysis: {trend_summary if trend_summary else 'No trend data detected.'} "
                "Don't show how you did that calculation just give the answer. Answer the question in a single concise sentence."
                "If asked how to do something make this concise and simple."
            )

            print(prompt)
            
            # Query the AI with the created prompt and retrieve the response
            response = query({"messages": [{"role": "user", "content": prompt}],
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
                                    chart_img=chart_img,
                                    error=False
                                    )
        
        else:
            return render_template('upload_success.html', 
                                   message="Invalid file type, please try .xlsx or .xls. instead. ", 
                                   filename="", 
                                   question="", 
                                   ai_response="Unavailable", 
                                   error=True
                                   )
                
    except Exception:
        traceback.print_exc()
        # Render an error template if any exception occurs during processing
        return render_template("upload_success.html", 
                               message="There was a problem with the AI model, please try again later.", 
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
                                   message="No follow-up question provided, please try entering a follow up question in the text area.",
                                   filename=filename,
                                   question=previous_question,
                                   error=True
                                   )
            
        
        prompt = (
            f"Here is the previous data: {data}. "
            f"Previous question was: {previous_question}. "
            f"Follow-up question: {followup_question}."
            f"Errors detected: {error_string if error_string else 'None'} If there are no errors, don't mention that unless prompted."  
            "Ensure to handle cases like division by zero appropriately by stating it's undefined or not applicable. " 
            #f"Trend analysis: {trend_summary if trend_summary else 'No trend data detected.'} "
            "Don't show how you did that calculation just give the answer. Answer the question in a single concise sentence."
            "If asked how to do something make this concise and simple."
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
    except Exception:
        traceback.print_exc()
        return render_template("upload_success.html", 
                                message="There was a problem with the AI model, please try again later.", 
                                filename='', 
                                question='', 
                                ai_response="Unavailable", 
                                error=True)

# Start the Flask application if this script is executed directly
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)