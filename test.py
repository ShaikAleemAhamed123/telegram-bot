from typing import Dict, Union, List
import json
def main():
    uploaded_videos : Dict[str, Dict[str, Union[str, List[str]]]] = {}
    with open("test.json", "rb") as f:
        uploaded_videos = json.load(f)
        print(type(uploaded_videos))
        print(uploaded_videos)

    uploaded_videos["new_chat_id"] = {"utube_url":"https://"}

    with open("test.json", "w") as f:
        json.dump(uploaded_videos, f)


if __name__ == "__main__":
    main()