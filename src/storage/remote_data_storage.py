import boto3, csv
import logging

class RemoteDataStorage:
    S3_BUCKET_NAME = "odds-portal-scrapped-odds-cad8822c179f12cg"
    AWE_REGION = "eu-west-3"

    def __init__(
        self, 
        bucket_name: str, 
        region_name: str
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3', region_name=region_name)
        self.logger.info(f"RemoteDataStorage initialized for bucket: {self.bucket_name}")
    
    def _flatten_data(self, data, timestamp):
        flattened_data = []
        for entry in data:
            base_info = {
                'scraped_at': timestamp,
                'date': entry['date'],
                'homeTeam': entry['homeTeam'],
                'awayTeam': entry['awayTeam']
            }
            for odds in entry.get('ft_1x2_odds_data', []):
                row = {**base_info}
                row.update({
                    'bookMakerName_1X2': odds['bookMakerName'],
                    'homeWin': odds['homeWin'],
                    'draw': odds['draw'],
                    'awayWin': odds['awayWin']
                })
                flattened_data.append(row)
            
            for odds in entry.get('over_under_2_5_odds_data', []):
                row = {**base_info}
                row.update({
                    'bookMakerName_OU': odds['bookmakerName'],
                    'oddsOver': odds['oddsOver'],
                    'oddsUnder': odds['oddsUnder']
                })
                flattened_data.append(row)
        return flattened_data
    
    def _save_to_csv(self, data, filename):
        self.logger.info(f"Saving data to CSV file: {filename}")
        try:
            fieldnames = ['scraped_at', 'date', 'homeTeam', 'awayTeam', 'bookMakerName_1X2', 'homeWin', 'draw', 'awayWin', 'bookMakerName_OU', 'oddsOver', 'oddsUnder']

            with open(filename, mode='w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    writer.writerow(row)

        except Exception as e:
            self.logger.error(f"Failed to save data to CSV: {e}")

    def _upload_to_s3(self, filename, object_name=None):
        if object_name is None:
            object_name = filename
        try:
            self.logger.info(f"Uploading {filename} to bucket {self.bucket_name} as {object_name}")
            self.s3_client.upload_file(filename, self.bucket_name, object_name)
            self.logger.info(f"File uploaded successfully to {self.bucket_name}/{object_name}")

        except Exception as e:
            self.logger.error(f"Failed to upload {filename} to S3: {e}")
    
    def process_and_upload(self, data, timestamp, filename, object_name=None):
        try:
            flattened_data = self._flatten_data(data, timestamp)
            self._save_to_csv(flattened_data, filename)
            self._upload_to_s3(filename, object_name)
        except Exception as e:
            self.logger.error(f"Failed to process and upload data: {e}")