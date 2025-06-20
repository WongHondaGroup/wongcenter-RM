# -*- coding: utf-8 -*-
# Project: รายงาน Incentive RM
# Description: Flask web application for displaying and exporting Incentive RM data from SQL Server.
# This script handles database connections, data retrieval, processing, and serves web pages.

import sys
import pyodbc
from flask import Flask, render_template, request, Response, url_for # Web framework and utilities
from datetime import date # For handling dates, like default dates
from decimal import Decimal, ROUND_HALF_UP # For precise monetary calculations
import pandas as pd # For data manipulation and Excel export
import io # For handling in-memory byte streams (for Excel file)

# --- Configuration for stdout encoding (especially for terminal output) ---
# Ensures an UTF-8 encoding for standard output, useful for displaying Thai characters in the console.
if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8") # Python 3.7+
    except Exception as e:
        print(f"Error reconfiguring stdout: {e}")
# --------------------------------------------------------------------

# Initialize Flask application instance
app = Flask(__name__)

# --- Database Connection Settings ---
# These settings define how to connect to the SQL Server database.
server = '171.96.87.57,1433' # SQL Server IP address or hostname
database = 'WongDWH'    # Target database name
username = 'wong'       # SQL Server username
password = 'wongsky99'  # SQL Server password

# ODBC Connection String
# Defines all parameters needed by the ODBC driver to connect to SQL Server.
conn_str = (
    r'DRIVER={ODBC Driver 17 for SQL Server};' # Specifies the ODBC driver to use
    r'SERVER=' + server + ';'
    r'DATABASE=' + database + ';'
    r'UID=' + username + ';'
    r'PWD=' + password + ';'
    r'TrustServerCertificate=yes;' # Bypasses server certificate validation (use with caution in production)
)

def get_sql_data(start_date_str, end_date_str):
    """
    Connects to the SQL Server database, executes a query to retrieve Incentive RM data
    for a given date range, processes it, and calculates the overall total amount.

    Args:
        start_date_str (str): The start date for the query (YYYY-MM-DD format).
        end_date_str (str): The end date for the query (YYYY-MM-DD format).

    Returns:
        tuple: A tuple containing:
            - column_names (list): List of column names from the query result.
            - data_rows (list): List of dictionaries, where each dictionary represents a row of data.
                                'amount' is converted to Decimal. Other None values are converted to empty strings.
            - total_amount_overall (Decimal): Sum of the 'amount' column for all retrieved rows.
            - error_message (str or None): An error message if an error occurred, otherwise None.
    """
    conn = None
    cursor = None
    data_rows = [] 
    column_names = []
    total_amount_overall = Decimal('0.00')
    error_message = None

    # Validate that both start and end dates are provided
    if not (start_date_str and end_date_str):
        error_message = "กรุณาเลือกทั้งวันที่เริ่มต้นและวันที่สิ้นสุด"
        return column_names, data_rows, total_amount_overall, error_message
        
    try:
        # Format dates from YYYY-MM-DD to YYYYMMDD for the SQL query
        formatted_start_date = start_date_str.replace('-', '')
        formatted_end_date = end_date_str.replace('-', '')

        # Establish database connection
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # SQL Query to retrieve Incentive RM data
        sql_query = f"""
        WITH LatestFrameData AS (
            SELECT
                FRAME_NO,
                CUSTOMER_NM,
                INVOCE_NO,  -- Column name in CTE from [AI].[dbo].[MR_RM_H]
                ROW_NUMBER() OVER (PARTITION BY FRAME_NO ORDER BY BATCH_DATE DESC) as rn
            FROM
                [AI].[dbo].[MR_RM_H]
        )
        SELECT
            rm.[calc_date],
            rm.[JobNo],
            rm.[invoice_no],
            rm.[TYPE],
            rm.[amount],
            rm.FrameNo,
            ISNULL(hf.CUSTOMER_NM, '') AS CUSTOMER_NM,
            us.[STAFF_FIRST_NAME] + ' ' + ISNULL(us.[STAFF_LAST_NAME], '') AS FullNameStaff,
            rm.[RECEPTIONIST]
        FROM
            [WongDWH].[dbo].[COMM_RMCAR_IDS] rm
        LEFT JOIN
            [AI_10127].[dbo].[MS_SD_STAFF] us ON rm.RECEPTIONIST = us.STAFF_CODE
        LEFT JOIN
            LatestFrameData hf ON rm.FrameNo = hf.FRAME_NO AND hf.rn = 1
        WHERE
            rm.calc_date BETWEEN ? AND ? 
        ORDER BY
            rm.calc_date ASC,
            rm.[JobNo] ASC,
            rm.[TYPE] ASC;
        """
        
        cursor.execute(sql_query, formatted_start_date, formatted_end_date)
        column_names = [column[0] for column in cursor.description] 
        rows_from_db = cursor.fetchall()

        if rows_from_db:
            amount_column_name_in_sql = 'amount'
            for row_tuple in rows_from_db:
                row_dict = dict(zip(column_names, row_tuple))
                current_amount_val = row_dict.get(amount_column_name_in_sql)
                if current_amount_val is not None:
                    try:
                        if not isinstance(current_amount_val, Decimal):
                            current_amount_val_decimal = Decimal(str(current_amount_val))
                        else:
                            current_amount_val_decimal = current_amount_val
                        row_dict[amount_column_name_in_sql] = current_amount_val_decimal
                        total_amount_overall += current_amount_val_decimal
                    except Exception as e_conv:
                        print(f"Warning: Cannot convert amount '{current_amount_val}' to Decimal: {e_conv}")
                        row_dict[amount_column_name_in_sql] = Decimal('0.00')
                else:
                    row_dict[amount_column_name_in_sql] = Decimal('0.00')
                for col_key in column_names:
                    if row_dict.get(col_key) is None:
                        row_dict[col_key] = ''
                data_rows.append(row_dict)
        print(f"get_sql_data (Incentive RM): Retrieved {len(data_rows)} rows, Total Amount: {total_amount_overall:.2f}")
    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        error_message = f"SQL Error: {sqlstate} - {ex}"
        print(f"SQL Error in get_sql_data (Incentive RM): {error_message}")
    except Exception as e:
        error_message = f"Other error in get_sql_data (Incentive RM): {e}"
        print(f"General Error in get_sql_data (Incentive RM): {error_message}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
    return column_names, data_rows, total_amount_overall, error_message

@app.route('/')
def show_data_on_web():
    selected_start_date = request.args.get('start_date')
    selected_end_date = request.args.get('end_date')
    today = date(2025, 6, 2) 
    default_start_date_val = selected_start_date if selected_start_date else today.replace(day=1).strftime('%Y-%m-%d')
    default_end_date_val = selected_end_date if selected_end_date else today.strftime('%Y-%m-%d')
    retrieved_column_names, data_to_show, calculated_total_amount, error = [], [], Decimal('0.00'), None
    if selected_start_date and selected_end_date:
        retrieved_column_names, data_to_show, calculated_total_amount, error = get_sql_data(selected_start_date, selected_end_date)
    formatted_total_amount_str = None
    if data_to_show and calculated_total_amount is not None:
        quantizer = Decimal('0.01')
        formatted_total_amount_str = "{:,.2f}".format(calculated_total_amount.quantize(quantizer, rounding=ROUND_HALF_UP))
    return render_template('show_data.html', 
                           rows=data_to_show, 
                           error_message=error,
                           db_server=server,
                           db_name=database,
                           default_start_date=default_start_date_val,
                           default_end_date=default_end_date_val,
                           selected_start_date=selected_start_date,
                           selected_end_date=selected_end_date,
                           total_amount_display=formatted_total_amount_str)

@app.route('/summary_report')
def summary_report():
    selected_start_date = request.args.get('start_date')
    selected_end_date = request.args.get('end_date')
    today = date(2025, 6, 2) 
    default_start_date_val = selected_start_date if selected_start_date else today.replace(day=1).strftime('%Y-%m-%d')
    default_end_date_val = selected_end_date if selected_end_date else today.strftime('%Y-%m-%d')
    active_start_date = selected_start_date if selected_start_date else default_start_date_val
    active_end_date = selected_end_date if selected_end_date else default_end_date_val

    staff_summary_list_final = []
    grand_total_amount_overall = Decimal('0.00')
    grand_total_items_overall = 0
    error = None

    if not (selected_start_date and selected_end_date):
        error = "กรุณาเลือกช่วงวันที่สำหรับดูรายงานสรุป Incentive RM"
    else:
        column_names_from_sql, raw_data_rows, overall_total_amount_from_get_sql, db_error = get_sql_data(active_start_date, active_end_date)
        if db_error:
            error = db_error
        elif raw_data_rows:
            try:
                df = pd.DataFrame(raw_data_rows)
                required_cols_for_summary = ['FullNameStaff', 'amount', 'TYPE', 'calc_date', 'JobNo', 'invoice_no', 'CUSTOMER_NM', 'FrameNo']
                if not all(col in df.columns for col in required_cols_for_summary):
                    missing_cols = [col for col in required_cols_for_summary if col not in df.columns]
                    error = f"ไม่พบคอลัมน์ที่จำเป็น ({', '.join(missing_cols)}) สำหรับสร้างรายงานสรุป Incentive RM"
                else:
                    for col_str_key in ['FullNameStaff', 'TYPE', 'CUSTOMER_NM', 'calc_date', 'JobNo', 'invoice_no', 'FrameNo']:
                         df[col_str_key] = df[col_str_key].astype(str).fillna('')
                    grouped_by_staff = df.groupby('FullNameStaff')
                    for staff_full_name, group_df in grouped_by_staff:
                        total_amount_for_staff = group_df['amount'].sum()
                        item_count_for_staff = len(group_df)
                        transactions_for_staff = []
                        for _, transaction_row in group_df.iterrows():
                            transactions_for_staff.append({
                                'calc_date': transaction_row.get('calc_date',''),
                                'JobNo': transaction_row.get('JobNo',''),        
                                'invoice_no': transaction_row.get('invoice_no',''),
                                'TYPE': transaction_row.get('TYPE',''),
                                'amount': transaction_row.get('amount', Decimal('0.00')),
                                'CUSTOMER_NM': transaction_row.get('CUSTOMER_NM', ''),
                                'FrameNo': transaction_row.get('FrameNo', '')
                            })
                        quantizer = Decimal('0.01')
                        staff_summary_list_final.append({
                            'FullNameStaff': staff_full_name,
                            'total_amount_per_staff': total_amount_for_staff,
                            'item_count_per_staff': item_count_for_staff,
                            'total_amount_per_staff_display': "{:,.2f}".format(total_amount_for_staff.quantize(quantizer, rounding=ROUND_HALF_UP)),
                            'transactions': transactions_for_staff 
                        })
                    grand_total_amount_overall = overall_total_amount_from_get_sql
                    grand_total_items_overall = len(raw_data_rows)
            except Exception as e_summary:
                error = f"เกิดข้อผิดพลาดในการประมวลผลข้อมูลสรุป Incentive RM: {e_summary}"
                print(f"Error processing summary (Incentive RM): {error}")
        else: 
            if not db_error:
                 print("Summary report (Incentive RM): No data found for the selected dates, not an error.")
                 pass 
    formatted_grand_total_amount_str = None
    if grand_total_amount_overall is not None and grand_total_items_overall > 0:
        quantizer = Decimal('0.01')
        formatted_grand_total_amount_str = "{:,.2f}".format(grand_total_amount_overall.quantize(quantizer, rounding=ROUND_HALF_UP))
    return render_template('summary_report.html',
                           staff_summary=staff_summary_list_final,
                           grand_total_amount_display=formatted_grand_total_amount_str,
                           grand_total_items=grand_total_items_overall,
                           error_message=error,
                           db_server=server,
                           db_name=database,
                           default_start_date=default_start_date_val,
                           default_end_date=default_end_date_val,
                           selected_start_date=selected_start_date, 
                           selected_end_date=selected_end_date,
                           active_start_date=active_start_date, 
                           active_end_date=active_end_date)

@app.route('/download_excel')
def download_excel():
    start_date_param = request.args.get('start_date')
    end_date_param = request.args.get('end_date')
    today_for_download = date(2025, 6, 2) 
    final_start_date = start_date_param if start_date_param else today_for_download.replace(day=1).strftime('%Y-%m-%d')
    final_end_date = end_date_param if end_date_param else today_for_download.strftime('%Y-%m-%d')
    if not (final_start_date and final_end_date):
        return "กรุณาระบุช่วงวันที่สำหรับดาวน์โหลดข้อมูล Incentive RM", 400
        
    column_names_from_sql, data_rows, _, error = get_sql_data(final_start_date, final_end_date)
    if error: return f"เกิดข้อผิดพลาดในการดึงข้อมูล Incentive RM: {error}", 500
    if not data_rows: return "ไม่พบข้อมูล Incentive RM ในช่วงวันที่ที่เลือกสำหรับดาวน์โหลด", 404
    try:
        df = pd.DataFrame(data_rows)
        if not df.empty:
            sort_columns = ['calc_date', 'JobNo', 'TYPE']
            actual_sort_columns = [col for col in sort_columns if col in df.columns]
            if actual_sort_columns:
                df.sort_values(by=actual_sort_columns, ascending=[True, True, True], inplace=True)
        excel_headers_map = {
            'calc_date': 'วันที่', 'JobNo': 'เลขที่เอกสาร', 'invoice_no': 'เลขที่ใบเสร็จ',
            'TYPE': 'รายการ', 'amount': 'ราคา', 'FrameNo': 'หมายเลขตัวถัง',
            'CUSTOMER_NM': 'ชื่อลูกค้า', 'FullNameStaff': 'พนักงาน', 'RECEPTIONIST': 'รหัสพนักงาน'
        }
        df_for_excel = pd.DataFrame()
        ordered_sql_columns_for_excel = [ 
            'calc_date', 'JobNo', 'invoice_no', 'TYPE', 'amount', 
            'FrameNo', 'CUSTOMER_NM', 'FullNameStaff', 'RECEPTIONIST'
        ]
        for sql_col in ordered_sql_columns_for_excel:
            if sql_col in df.columns:
                df_for_excel[excel_headers_map.get(sql_col, sql_col)] = df[sql_col]
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_for_excel.to_excel(writer, index=False, sheet_name='Incentive_RM_Data')
        output.seek(0)
        filename = f"Incentive_RM_Data_{final_start_date}_to_{final_end_date}.xlsx"
        return Response(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment;filename=\"{filename}\""}
        )
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการสร้างไฟล์ Excel (Incentive RM): {e}")
        return "เกิดข้อผิดพลาดในการสร้างไฟล์ Excel (Incentive RM)", 500

@app.route('/download_staff_excel')
def download_staff_excel():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    full_name_staff_param = request.args.get('full_name_staff') 
    if not (start_date and end_date and full_name_staff_param):
        return "ข้อมูลไม่ครบถ้วนสำหรับดาวน์โหลด (ต้องการช่วงวันที่และชื่อเต็มพนักงาน)", 400

    _, raw_data_rows, _, db_error = get_sql_data(start_date, end_date)
    if db_error: return f"เกิดข้อผิดพลาดในการดึงข้อมูล Incentive RM: {db_error}", 500
    staff_transactions_to_export = []
    if raw_data_rows:
        for row in raw_data_rows:
            if row.get('FullNameStaff', '') == full_name_staff_param:
                staff_transactions_to_export.append({
                    'calc_date': row.get('calc_date',''), 'JobNo': row.get('JobNo',''),
                    'invoice_no': row.get('invoice_no',''), 'TYPE': row.get('TYPE',''),
                    'amount': row.get('amount', Decimal('0.00')),
                    'CUSTOMER_NM': row.get('CUSTOMER_NM',''), 'FrameNo': row.get('FrameNo','')
                })
    if not staff_transactions_to_export:
        return f"ไม่พบข้อมูลรายการ Incentive RM ของพนักงาน {full_name_staff_param} ในช่วงวันที่ที่เลือกสำหรับดาวน์โหลด", 404
    try:
        staff_excel_columns_map = {
            'calc_date': 'วันที่', 'JobNo': 'เลขที่เอกสาร', 'invoice_no': 'เลขที่ใบเสร็จ',
            'TYPE': 'รายการ', 'amount': 'ราคา', 'CUSTOMER_NM': 'ชื่อลูกค้า', 'FrameNo': 'หมายเลขตัวถัง'
        }
        df_staff = pd.DataFrame(staff_transactions_to_export)
        df_staff_for_excel = pd.DataFrame()
        for sql_col, thai_header in staff_excel_columns_map.items():
            if sql_col in df_staff.columns:
                 df_staff_for_excel[thai_header] = df_staff[sql_col]
        output = io.BytesIO()
        safe_staff_name_for_file = "".join(c if c.isalnum() else "_" for c in full_name_staff_param)
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_staff_for_excel.to_excel(writer, index=False, sheet_name=safe_staff_name_for_file[:30])
        output.seek(0)
        filename = f"Incentive_RM_Staff_{safe_staff_name_for_file}_{start_date}_to_{end_date}.xlsx"
        return Response(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment;filename=\"{filename}\""}
        )
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการสร้างไฟล์ Excel ของพนักงาน (Incentive RM): {e}")
        return "เกิดข้อผิดพลาดในการสร้างไฟล์ Excel ของพนักงาน (Incentive RM)", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)