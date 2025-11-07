from flask import Flask, render_template, request, redirect, url_for, session, send_file
import pandas as pd
import os
import io

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Replace with a strong secret key in production

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file and file.filename.endswith('.csv'):
        try:
            df = pd.read_csv(file)
            if df.empty:
                return "Error: The CSV file is empty."
            
            # Store original DataFrame in session as JSON
            session['original_df'] = df.to_json()
            
            # Identify all duplicate rows (keep=False marks all occurrences)
            duplicates = df[df.duplicated(keep=False)]
            session['duplicates_df'] = duplicates.to_json()
            
            # Store column names for proper CSV reconstruction
            session['columns'] = list(df.columns)
            
            return render_template('results.html', 
                                 original_data=df.to_html(classes='table table-striped', table_id='original-table'),
                                 duplicate_data=duplicates.to_html(classes='table table-striped', table_id='duplicate-table'),
                                 duplicate_count=len(duplicates),
                                 original_count=len(df))
        except pd.errors.EmptyDataError:
            return "Error: The CSV file is empty or has no valid data."
        except Exception as e:
            return f"Error processing file: {e}"
    return "Invalid file type. Please upload a CSV file."

@app.route('/download')
def download_duplicates():
    """Download the duplicate rows as a CSV file."""
    if 'duplicates_df' not in session:
        return redirect(url_for('index'))
    
    try:
        # Reconstruct DataFrame from session
        duplicates_df = pd.read_json(session['duplicates_df'])
        
        # Create a BytesIO buffer for the CSV
        output = io.BytesIO()
        duplicates_df.to_csv(output, index=False, encoding='utf-8')
        output.seek(0)
        
        # Return the CSV file for download
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name='duplicates.csv'
        )
    except Exception as e:
        return f"Error generating download file: {e}"

if __name__ == '__main__':
    app.run(debug=True)





