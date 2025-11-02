from typing import Dict, Union, List
import json
def main():
    uploaded_videos : Dict[str, Dict[str, Union[str, List[str]]]] = {}
    with open("test.json", "rb") as f:
        data = json.load(f)
        print(type(data))