import re
from datetime import datetime

def calculate_lapsed(datetime_range):
    try:
        parts = str(datetime_range).strip().split(' ')
        if len(parts) < 2: return "00:00:00"
        times = parts[1].split('-')
        if len(times) < 2: return "00:00:00"
        fmt = '%H:%M:%S'
        start_t = datetime.strptime(times[0], fmt)
        end_t = datetime.strptime(times[1], fmt)
        delta = end_t - start_t
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0: total_seconds += 86400
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except: return "00:00:00"
