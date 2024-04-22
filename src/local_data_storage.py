import csv
from pathlib import Path

DEFAULT_FILE_PATH = 'scraped_data.csv'

class LocalDataStorage:
    def __init__(self, file_path = DEFAULT_FILE_PATH):
        self.file_path = file_path
        self.file_exists = Path(self.file_path).exists()
    
    def append_data(self, data):
        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise ValueError("Data must be a dictionary or a list of dictionaries.")

        if data:
            with open(self.file_path, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=data[0].keys())

                if not self.file_exists:
                    writer.writeheader()
                    self.file_exists = True
                
                for row in data:
                    writer.writerow(row)