import csv, logging
from pathlib import Path
from typing import List, Dict, Union

class LocalDataStorage:
    def __init__(
        self, 
        default_file_path: str = "scraped_data.csv"
    ):
        """
        Initialize LocalDataStorage.

        Args:
            default_file_path (str): Default file path to use if none is provided in append_data.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.default_file_path = default_file_path
        self.logger.info(f"Initialized LocalDataStorage with default file path: {self.default_file_path}")
    
    def save_data(
        self, 
        data: Union[Dict, List[Dict]], 
        file_path: str = None
    ):
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