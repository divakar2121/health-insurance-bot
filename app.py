from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import numpy as np
import os
import json
import plotly
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import base64
import zipfile
from datetime import datetime
import logging
import tempfile
import shutil

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
EXTRACTED_FOLDER = 'extracted'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv', 'pdf', 'zip'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXTRACTED_FOLDER'] = EXTRACTED_FOLDER

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXTRACTED_FOLDER, exist_ok=True)

def allowed_file(filename):
    if not filename:
        return False
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Store extracted file info temporarily
extracted_files_registry = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if not file or not file.filename or file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Handle ZIP files - extract and process Excel files inside
        if filename.endswith('.zip'):
            try:
                # Create a temporary directory for extraction
                extract_dir = os.path.join(app.config['EXTRACTED_FOLDER'], filename.replace('.zip', ''))
                # Clean up previous extraction if exists
                if os.path.exists(extract_dir):
                    shutil.rmtree(extract_dir)
                os.makedirs(extract_dir)
                
                # Extract ZIP file
                with zipfile.ZipFile(filepath, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # Find all Excel files in extracted directory
                excel_files = []
                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        if file.endswith(('.xlsx', '.xls')):
                            excel_files.append(os.path.join(root, file))
                
                # Analyze each Excel file
                files_info = []
                for excel_file in excel_files:
                    try:
                        # Get relative path for display
                        rel_path = os.path.relpath(excel_file, extract_dir)
                        df = pd.read_excel(excel_file)
                        
                        file_info = {
                            'filename': rel_path,
                            'full_path': excel_file,
                            'shape': [int(df.shape[0]), int(df.shape[1])],
                            'columns': df.columns.tolist() if df.columns is not None else [],
                            'dtypes': {str(col): str(dtype) for col, dtype in df.dtypes.items()} if df.dtypes is not None else {},
                            'sample_data': df.head(5).to_dict('records') if len(df) > 0 else [],
                            'missing_values': {str(k): int(v) for k, v in df.isnull().sum().items()} if df.isnull().sum() is not None else {},
                            'numeric_columns': df.select_dtypes(include=[np.number]).columns.tolist() if df.select_dtypes(include=[np.number]).columns is not None else [],
                            'categorical_columns': df.select_dtypes(include=['object']).columns.tolist() if df.select_dtypes(include=['object']).columns is not None else []
                        }
                        files_info.append(file_info)
                    except Exception as e:
                        logger.warning(f"Could not read Excel file {excel_file}: {str(e)}")
                        continue
                
                if not files_info:
                    return jsonify({'error': 'No valid Excel files found in ZIP'}), 400
                
                # Store in registry for later access
                registry_key = f"zip_{filename}"
                extracted_files_registry[registry_key] = {
                    'extract_dir': extract_dir,
                    'files': {str(info['filename']): str(info['full_path']) for info in files_info}
                }
                
                return jsonify({
                    'message': 'ZIP file extracted and processed successfully',
                    'filename': filename,
                    'is_zip': True,
                    'files': files_info
                })
                
            except Exception as e:
                logger.error(f"Error processing ZIP file: {str(e)}")
                return jsonify({'error': f'Error processing ZIP file: {str(e)}'}), 500
        
        # Process regular files (Excel, CSV)
        else:
            try:
                df = None
                if filename.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(filepath)
                elif filename.endswith('.csv'):
                    df = pd.read_csv(filepath)
                
                if df is None:
                    return jsonify({'error': 'Unsupported file format'}), 400
                
                # Basic data info
                data_info = {
                    'filename': filename,
                    'shape': [int(df.shape[0]), int(df.shape[1])],
                    'columns': df.columns.tolist() if df.columns is not None else [],
                    'dtypes': {str(col): str(dtype) for col, dtype in df.dtypes.items()} if df.dtypes is not None else {},
                    'sample_data': df.head(10).to_dict('records') if len(df) > 0 else [],
                    'missing_values': {str(k): int(v) for k, v in df.isnull().sum().items()} if df.isnull().sum() is not None else {},
                    'numeric_columns': df.select_dtypes(include=[np.number]).columns.tolist() if df.select_dtypes(include=[np.number]).columns is not None else [],
                    'categorical_columns': df.select_dtypes(include=['object']).columns.tolist() if df.select_dtypes(include=['object']).columns is not None else []
                }
                
                return jsonify({
                    'message': 'File uploaded successfully',
                    'filename': filename,
                    'is_zip': False,
                    'data_info': data_info
                })
                
            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                return jsonify({'error': f'Error processing file: {str(e)}'}), 500
    
    return jsonify({'error': 'File type not allowed'}), 400

def generate_summary(df):
    """Generate summary statistics"""
    if df is None or df.empty:
        return {
            'analysis_type': 'summary',
            'data': {}
        }
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    summary = {}
    
    for col in numeric_cols:
        try:
            summary[col] = {
                'mean': float(df[col].mean()),
                'median': float(df[col].median()),
                'std': float(df[col].std()),
                'min': float(df[col].min()),
                'max': float(df[col].max()),
                'count': int(df[col].count())
            }
        except:
            summary[col] = {
                'mean': 0.0,
                'median': 0.0,
                'std': 0.0,
                'min': 0.0,
                'max': 0.0,
                'count': 0
            }
    
    return {
        'analysis_type': 'summary',
        'data': summary
    }

def generate_trends(df):
    """Generate trend analysis"""
    if df is None or df.empty:
        return {'error': 'No data available for trend analysis'}
    
    # Find date columns
    date_cols = df.select_dtypes(include=['datetime64']).columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    
    if len(date_cols) == 0 and len(numeric_cols) > 0:
        # Create a simple index-based trend
        df_trend = df.copy()
        df_trend['index'] = range(len(df_trend))
        date_col = 'index'
    elif len(date_cols) > 0:
        date_col = date_cols[0]
        df_trend = df.copy()
        df_trend[date_col] = pd.to_datetime(df_trend[date_col], errors='coerce')
        # Remove NaT values
        df_trend = df_trend.dropna(subset=[date_col])
        if len(df_trend) == 0:
            return {'error': 'No valid date values for trend analysis'}
        df_trend = df_trend.sort_values(date_col)
    else:
        return {'error': 'No suitable date or numeric columns for trend analysis'}
    
    trends = {}
    for col in numeric_cols:
        if col != date_col and col in df_trend.columns:
            try:
                fig = px.line(df_trend, x=date_col, y=col, title=f'{col} Trend Over Time')
                fig_json = fig.to_json()
                if fig_json is not None:
                    trends[col] = json.loads(fig_json)
                else:
                    trends[col] = {'error': f'Could not generate trend for {col}'}
            except Exception as e:
                trends[col] = {'error': f'Could not generate trend for {col}: {str(e)}'}
    
    return {
        'analysis_type': 'trends',
        'data': trends
    }

def generate_distribution(df):
    """Generate distribution plots"""
    if df is None or df.empty:
        return {'error': 'No data available for distribution analysis'}
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    distributions = {}
    
    for col in numeric_cols:
        if col in df.columns:
            try:
                fig = px.histogram(df, x=col, title=f'Distribution of {col}')
                fig_json = fig.to_json()
                if fig_json is not None:
                    distributions[col] = json.loads(fig_json)
                else:
                    distributions[col] = {'error': f'Could not generate distribution for {col}'}
            except Exception as e:
                distributions[col] = {'error': f'Could not generate distribution for {col}: {str(e)}'}
    
    return {
        'analysis_type': 'distribution',
        'data': distributions
    }

def generate_correlation(df):
    """Generate correlation matrix"""
    if df is None or df.empty:
        return {'error': 'No data available for correlation analysis'}
    
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df is None or numeric_df.empty:
        return {'error': 'No numeric columns for correlation analysis'}
    
    try:
        corr_matrix = numeric_df.corr()
        fig = px.imshow(corr_matrix, 
                        text_auto=True, 
                        aspect="auto",
                        title="Correlation Matrix")
        fig_json = fig.to_json()
        if fig_json is not None:
            return {
                'analysis_type': 'correlation',
                'data': json.loads(fig_json)
            }
        else:
            return {'error': 'Could not generate correlation matrix'}
    except Exception as e:
        return {'error': f'Could not generate correlation matrix: {str(e)}'}

@app.route('/analyze', methods=['POST'])
def analyze_data():
    data = request.json or {}
    filename = data.get('filename')
    analysis_type = data.get('analysis_type', 'summary')
    
    if not filename:
        return jsonify({'error': 'No filename provided'}), 400
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        # Load data
        df = None
        if filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(filepath)
        elif filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        
        if df is None:
            return jsonify({'error': 'Unsupported file format'}), 400
        
        # Perform analysis based on type
        if analysis_type == 'summary':
            result = generate_summary(df)
        elif analysis_type == 'trends':
            result = generate_trends(df)
        elif analysis_type == 'distribution':
            result = generate_distribution(df)
        elif analysis_type == 'correlation':
            result = generate_correlation(df)
        else:
            return jsonify({'error': 'Invalid analysis type'}), 400
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in analysis: {str(e)}")
        return jsonify({'error': f'Analysis error: {str(e)}'}), 500

@app.route('/analyze_excel_file', methods=['POST'])
def analyze_excel_file():
    """Analyze a specific Excel file from a previously uploaded ZIP"""
    data = request.json or {}
    zip_filename = data.get('zip_filename')
    excel_filename = data.get('excel_filename')
    analysis_type = data.get('analysis_type', 'summary')
    
    if not zip_filename or not excel_filename:
        return jsonify({'error': 'ZIP filename and Excel filename required'}), 400
    
    # Check if this ZIP was processed before
    registry_key = f"zip_{zip_filename}"
    if registry_key not in extracted_files_registry:
        return jsonify({'error': 'ZIP file not found or not processed'}), 404
    
    registry_info = extracted_files_registry[registry_key]
    if excel_filename not in registry_info['files']:
        return jsonify({'error': 'Excel file not found in ZIP'}), 404
    
    excel_filepath = registry_info['files'][excel_filename]
    
    try:
        # Load the specific Excel file
        df = pd.read_excel(excel_filepath)
        
        if df is None or df.empty:
            return jsonify({'error': 'Could not read Excel file or file is empty'}), 400
        
        # Perform analysis based on type
        if analysis_type == 'summary':
            analysis_result = generate_summary(df)
        elif analysis_type == 'trends':
            analysis_result = generate_trends(df)
        elif analysis_type == 'distribution':
            analysis_result = generate_distribution(df)
        elif analysis_type == 'correlation':
            analysis_result = generate_correlation(df)
        else:
            return jsonify({'error': 'Invalid analysis type'}), 400
        
        # Add file info to result
        final_result = dict(analysis_result)  # Make a copy
        file_info_dict = {}
        file_info_dict['zip_filename'] = "" if zip_filename is None else str(zip_filename)
        file_info_dict['excel_filename'] = "" if excel_filename is None else str(excel_filename)
        if df is not None and hasattr(df, 'shape'):
            file_info_dict['shape'] = [int(df.shape[0]), int(df.shape[1])]
        else:
            file_info_dict['shape'] = [0, 0]
        if df is not None and df.columns is not None:
            file_info_dict['columns'] = list(df.columns)
        else:
            file_info_dict['columns'] = []
        final_result['file_info'] = file_info_dict
        
        return jsonify(final_result)
        
    except Exception as e:
        logger.error(f"Error analyzing Excel file: {str(e)}")
        return jsonify({'error': f'Analysis error: {str(e)}'}), 500


@app.route('/get_extracted_files', methods=['GET'])
def get_extracted_files():
    """Get list of extracted Excel files from the data directory"""
    try:
        # Scan the data directory for extracted Excel files
        extracted_files = []
        data_dir = 'data'
        
        # Walk through the data directory to find Excel files
        for root, dirs, files in os.walk(data_dir):
            for file in files:
                if file.endswith(('.xlsx', '.xls')):
                    # Get relative path from data directory
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, data_dir)
                    extracted_files.append(rel_path)
        
        return jsonify({
            'files': extracted_files
        })
        
    except Exception as e:
        logger.error(f"Error getting extracted files: {str(e)}")
        return jsonify({'error': f'Error getting extracted files: {str(e)}'}), 500


@app.route('/load_extracted_file', methods=['POST'])
def load_extracted_file():
    """Load a specific extracted Excel file for analysis"""
    data = request.json or {}
    filename = data.get('filename')
    
    if not filename:
        return jsonify({'error': 'Filename required'}), 400
    
    # Construct full path
    filepath = os.path.join('data', filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        # Load the Excel file
        if filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(filepath)
        elif filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            return jsonify({'error': 'Unsupported file format'}), 400
        
        if df is None or df.empty:
            return jsonify({'error': 'Could not read file or file is empty'}), 400
        
        # Return file info similar to upload endpoint
        data_info = {
            'filename': filename,
            'shape': [int(df.shape[0]), int(df.shape[1])],
            'columns': df.columns.tolist() if df.columns is not None else [],
            'dtypes': {str(col): str(dtype) for col, dtype in df.dtypes.items()} if df.dtypes is not None else {},
            'sample_data': df.head(10).to_dict('records') if len(df) > 0 else [],
            'missing_values': {str(k): int(v) for k, v in df.isnull().sum().items()} if df.isnull().sum() is not None else {},
            'numeric_columns': df.select_dtypes(include=[np.number]).columns.tolist() if df.select_dtypes(include=[np.number]).columns is not None else [],
            'categorical_columns': df.select_dtypes(include=['object']).columns.tolist() if df.select_dtypes(include=['object']).columns is not None else []
        }
        
        return jsonify({
            'message': 'File loaded successfully',
            'filename': filename,
            'is_zip': False,
            'data_info': data_info
        })
        
    except Exception as e:
        logger.error(f"Error loading extracted file: {str(e)}")
        return jsonify({'error': f'Error loading file: {str(e)}'}), 500

@app.route('/dashboard', methods=['POST'])
def create_dashboard():
    data = request.json or {}
    filename = data.get('filename')
    chart_type = data.get('chart_type', 'bar')
    x_column = data.get('x_column')
    y_column = data.get('y_column')
    
    if not filename:
        return jsonify({'error': 'No filename provided'}), 400
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        # Load data
        df = None
        if filename and filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(filepath)
        elif filename and filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        
        if df is None:
            return jsonify({'error': 'Unsupported file format'}), 400
        
        # Validate columns
        if x_column not in df.columns or y_column not in df.columns:
            return jsonify({'error': 'Invalid column selection'}), 400
        
        # Create chart based on type
        if chart_type == 'bar':
            fig = px.bar(df, x=x_column, y=y_column, title=f'{y_column} by {x_column}')
        elif chart_type == 'line':
            fig = px.line(df, x=x_column, y=y_column, title=f'{y_column} over {x_column}')
        elif chart_type == 'scatter':
            fig = px.scatter(df, x=x_column, y=y_column, title=f'{y_column} vs {x_column}')
        elif chart_type == 'pie':
            fig = px.pie(df, names=x_column, values=y_column, title=f'{y_column} distribution by {x_column}')
        elif chart_type == 'histogram':
            fig = px.histogram(df, x=x_column, title=f'Distribution of {x_column}')
        elif chart_type == 'area':
            fig = px.area(df, x=x_column, y=y_column, title=f'{y_column} over {x_column}')
        elif chart_type == 'box':
            fig = px.box(df, x=x_column, y=y_column, title=f'{y_column} distribution by {x_column}')
        elif chart_type == 'violin':
            fig = px.violin(df, x=x_column, y=y_column, title=f'{y_column} distribution by {x_column}')
        elif chart_type == 'heatmap':
            # For heatmap, we need numeric columns
            numeric_df = df.select_dtypes(include=[np.number])
            if numeric_df.empty:
                return jsonify({'error': 'No numeric columns available for heatmap'}), 400
            fig = px.imshow(numeric_df.corr(), text_auto=True, aspect="auto", title="Correlation Heatmap")
        else:
            return jsonify({'error': 'Invalid chart type'}), 400
        
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return jsonify({'graph': graphJSON})
        
    except Exception as e:
        logger.error(f"Error creating dashboard: {str(e)}")
        return jsonify({'error': f'Dashboard error: {str(e)}'}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)