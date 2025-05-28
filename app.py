from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import pandas as pd
import io
from fpdf import FPDF
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

df = None  # global dataframe to hold uploaded CSV
ROWS_PER_PAGE = 50  # number of rows per page


def apply_filters(dataframe, filters):
    filtered_df = dataframe.copy()

    class_filter = filters.get('class')
    if class_filter:
        normalized_filter = class_filter.replace(" ", "").lower()
        filtered_df = filtered_df[
            filtered_df['Class'].astype(str)
            .apply(lambda x: normalized_filter in x.replace(" ", "").lower())
        ]

    from_date_str = filters.get('from_date')
    to_date_str = filters.get('to_date')

    if 'Date' in filtered_df.columns:
        filtered_df['Date'] = pd.to_datetime(filtered_df['Date'], errors='coerce')

        if from_date_str:
            try:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d')
                filtered_df = filtered_df[filtered_df['Date'] >= from_date]
            except ValueError:
                flash("Invalid From Date format. Use YYYY-MM-DD.")

        if to_date_str:
            try:
                to_date = datetime.strptime(to_date_str, '%Y-%m-%d')
                filtered_df = filtered_df[filtered_df['Date'] <= to_date]
            except ValueError:
                flash("Invalid To Date format. Use YYYY-MM-DD.")

    return filtered_df


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    global df
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            try:
                df = pd.read_csv(file)
                flash(f"File uploaded successfully! Rows: {len(df)} Columns: {len(df.columns)}")
                return redirect(url_for('show_data'))
            except Exception as e:
                flash(f"Error reading CSV file: {e}")
                return redirect(request.url)
    return render_template('upload.html')


@app.route('/data', methods=['GET'])
def show_data():
    global df
    if df is None:
        flash("Please upload a CSV file first.")
        return redirect(url_for('upload_file'))

    class_filter = request.args.get('class', default='', type=str).strip()
    from_date = request.args.get('from_date', default='', type=str).strip()
    to_date = request.args.get('to_date', default='', type=str).strip()
    page = request.args.get('page', default=1, type=int)

    filters = {
        'class': class_filter,
        'from_date': from_date,
        'to_date': to_date
    }

    filtered_df = apply_filters(df, filters)

    total_rows = len(filtered_df)
    total_pages = (total_rows + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1

    start_idx = (page - 1) * ROWS_PER_PAGE
    end_idx = start_idx + ROWS_PER_PAGE
    page_data = filtered_df.iloc[start_idx:end_idx]

    return render_template('data.html',
                           columns=filtered_df.columns,
                           data=page_data.to_dict(orient='records'),
                           page=page,
                           total_pages=total_pages,
                           total_rows=total_rows,
                           filters=filters)


@app.route('/export/csv')
def export_csv():
    global df
    if df is None:
        flash("No data to export. Upload CSV first.")
        return redirect(url_for('upload_file'))

    filters = {
        'class': request.args.get('class', default='', type=str).strip(),
        'from_date': request.args.get('from_date', default='', type=str).strip(),
        'to_date': request.args.get('to_date', default='', type=str).strip()
    }

    filtered_df = apply_filters(df, filters)

    csv_bytes = filtered_df.to_csv(index=False).encode('utf-8')
    return send_file(io.BytesIO(csv_bytes),
                     mimetype='text/csv',
                     as_attachment=True,
                     download_name='filtered_data.csv')


@app.route('/export/pdf')
def export_pdf():
    global df
    if df is None:
        flash("No data to export. Upload CSV first.")
        return redirect(url_for('upload_file'))

    filters = {
        'class': request.args.get('class', default='', type=str).strip(),
        'from_date': request.args.get('from_date', default='', type=str).strip(),
        'to_date': request.args.get('to_date', default='', type=str).strip()
    }

    filtered_df = apply_filters(df, filters)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Load a Unicode-compatible font
    font_path = os.path.join('static', 'fonts', 'DejaVuSans.ttf')
    if not os.path.exists(font_path):
        flash("Missing font file: static/fonts/DejaVuSans.ttf")
        return redirect(url_for('show_data'))

    pdf.add_font('DejaVu', '', font_path, uni=True)
    pdf.set_font("DejaVu", '', 10)

    col_width = pdf.w / (len(filtered_df.columns) + 1)
    row_height = 8

    # Header
    for col in filtered_df.columns:
        pdf.cell(col_width, row_height, str(col), border=1)
    pdf.ln(row_height)

    for _, row in filtered_df.head(50).iterrows():
        for item in row:
            pdf.cell(col_width, row_height, str(item), border=1)
        pdf.ln(row_height)

    pdf_bytes = pdf.output(dest='S').encode('latin1', 'replace')
    return send_file(io.BytesIO(pdf_bytes),
                     mimetype='application/pdf',
                     as_attachment=True,
                     download_name='filtered_data.pdf')


if __name__ == '__main__':
    app.run(debug=True)
