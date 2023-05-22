import pandas as pd


def conversion_file_csv_to_dict(file_csv, sheet="Sheet1") -> dict:
    read_file = pd.read_csv(file_csv, sheet)
    datas = read_file.to_dict()

    return datas

def conversion_file_xlsx_to_dict(file_xlsx, sheet="Sheet1") -> dict:
    read_file = pd.read_excel(file_xlsx, sheet)
    datas = read_file.to_dict()

    return datas


def conversion_file_csv_merger_to_dict(file_csv, sheet="Sheet1", method='ffill', columns_fillna=[], axis=0) -> dict:
    read_file = pd.read_csv(file_csv, sheet)
    if columns_fillna:
        read_file[columns_fillna] = read_file[columns_fillna].fillna(method=method, axis=axis)
    else:
        read_file = read_file.fillna(method=method, axis=axis)
    datas = read_file.to_dict()

    return datas

def conversion_file_xlsx_merger_to_dict(file_xlsx, sheet="Sheet1", method='ffill', columns_fillna=[], axis=0) -> dict:
    read_file = pd.read_excel(file_xlsx, sheet)
    if columns_fillna:
        read_file[columns_fillna] = read_file[columns_fillna].fillna(method=method, axis=axis)
    else:
        read_file = read_file.fillna(method=method, axis=axis)
    datas = read_file.to_dict()

    return datas


def get_excel_sheets_names(file_xlsx) -> dict:
    _read_file = pd.ExcelFile(file_xlsx)
    _names = _read_file.sheet_names
    return _names