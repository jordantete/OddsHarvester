from datetime import datetime

def get_current_date_time_string():
    now = datetime.now()
    date_time_string = now.strftime('%Y-%m-%d %H:%M:%S')
    return date_time_string