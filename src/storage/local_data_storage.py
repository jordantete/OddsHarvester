import csv, logging
from pathlib import Path

class LocalDataStorage:
    def __init__(self, file_path: str = 'scraped_data.csv'):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.file_path = file_path
        self.file_exists = Path(self.file_path).exists()
        self.logger.info(f"Initialized LocalDataStorage with file path: {file_path}")
    
    def append_data(self, data):
        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise ValueError("Data must be a dictionary or a list of dictionaries.")

        try:
            if data:
                with open(self.file_path, mode='a', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=data[0].keys())

                    if not self.file_exists:
                        writer.writeheader()
                        self.file_exists = True
                    
                    for row in data:
                        writer.writerow(row)
                self.logger.info(f"Successfully appended {len(data)} records to {self.file_path}")
        except Exception as e:
            self.logger.error(f"Error appending data to file: {str(e)}", exc_info=True)
            raise