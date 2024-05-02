import boto3, csv
from logger import LOGGER

S3_BUCKET_NAME = "odds-portal-scrapped-odds-cad8822c179f12cg"
AWE_REGION = "eu-west-3"

class RemoteDataStorage:
    def __init__(self, bucket_name=S3_BUCKET_NAME, region_name=AWE_REGION):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3', region_name=region_name)
        LOGGER.info(f"RemoteDataStorage initialized for bucket: {self.bucket_name}")
    
    def __flatten_data(self, data):
        flattened_data = []
        for entry in data:
            base_info = {
                'date': entry['date'],
                'homeTeam': entry['homeTeam'],
                'awayTeam': entry['awayTeam']
            }
            # Handle ft_1x2_odds_data
            for odds in entry.get('ft_1x2_odds_data', []):
                row = {**base_info}  # Copy base game info
                row.update({
                    'bookMakerName_1X2': odds['bookMakerName'],
                    'homeWin': odds['homeWin'],
                    'draw': odds['draw'],
                    'awayWin': odds['awayWin']
                })
                flattened_data.append(row)
            
            # Handle over_under_2_5_odds_data similarly if needed
            for odds in entry.get('over_under_2_5_odds_data', []):
                row = {**base_info}  # Copy base game info
                row.update({
                    'bookMakerName_OU': odds['bookmakerName'],
                    'oddsOver': odds['oddsOver'],
                    'oddsUnder': odds['oddsUnder']
                })
                flattened_data.append(row)
        return flattened_data
    
    def __save_to_csv(self, data, filename):
        """ Saves the provided data to a CSV file. """
        LOGGER.info(f"Saving data to CSV file: {filename}")
        try:
            fieldnames = ['date', 'homeTeam', 'awayTeam', 'bookMakerName_1X2', 'homeWin', 'draw', 'awayWin', 'bookMakerName_OU', 'oddsOver', 'oddsUnder']
            with open(filename, mode='w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    writer.writerow(row)
        except Exception as e:
            LOGGER.error(f"Failed to save data to CSV: {e}")

    def __upload_to_s3(self, filename, object_name=None):
        """ Uploads a file to an S3 bucket. """
        if object_name is None:
            object_name = filename
        try:
            LOGGER.info(f"Uploading {filename} to bucket {self.bucket_name} as {object_name}")
            self.s3_client.upload_file(filename, self.bucket_name, object_name)
            LOGGER.info(f"File uploaded successfully to {self.bucket_name}/{object_name}")
        except Exception as e:
            LOGGER.error(f"Failed to upload {filename} to S3: {e}")
    
    def process_and_upload(self, data, filename, object_name=None):
        """ Handles the entire flow: flattening data, saving to CSV, and uploading to S3. """
        try:
            flattened_data = self.__flatten_data(data)
            self.__save_to_csv(flattened_data, filename)
            self.__upload_to_s3(filename, object_name)
        except Exception as e:
            LOGGER.error(f"Failed to process and upload data: {e}")