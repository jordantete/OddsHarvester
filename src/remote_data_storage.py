import boto3, csv, os
from io import StringIO
from logger import LOGGER

class RemoteDataStorage:
    def __init__(self, bucket_name, region_name='eu-west-3'):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3', region_name=region_name)

    def write_csv_to_s3(self, data, key):
        # Use StringIO to simulate a file
        with StringIO() as output:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            output.seek(0)  # go back to the start of the StringIO object
            self.s3_client.put_object(Bucket=self.bucket_name, Key=key, Body=output.getvalue())
    
    def upload_csv_s3(data_dictionary, csv_file_name):
        # TODO: CSV ALREADY EXISTS ?
        LOGGER.info(f"Will upload dictionary: {data_dictionary} from csv file: {csv_file_name} to S3 bucket: {self.bucket_name}")

        data_dict = data_dictionary
        data_dict_keys = data_dictionary[0].keys()
        
        # creating a file buffer
        file_buff = StringIO()
        
        # writing csv data to file buffer
        writer = csv.DictWriter(file_buff, fieldnames=data_dict_keys)
        writer.writeheader()
        for data in data_dict:
            writer.writeheader(data)
        
        # placing file to S3, file_buff.getvalue() is the CSV body for the file
        self.s3_client.put_object(Body=file_buff.getvalue(), Bucket=self.bucket_name, Key=csv_file_name)
        print('Done uploading to S3')

    def upload_file_to_s3(self, file_name, key):
        self.s3_client.upload_file(file_name, self.bucket_name, key)

