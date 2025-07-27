from dotenv import load_dotenv, find_dotenv
import os, pprint, pathlib, sys

load_dotenv(find_dotenv())          # загружаем .env, где бы он ни лежал
print("cwd        :", pathlib.Path.cwd())
print("YC_API_KEY :", os.getenv("YC_API_KEY"))
print("YC_FOLDER_ID:", os.getenv("YC_FOLDER_ID"))
