import hashlib
import requests
import os
import pickle
from functools import wraps
from dotenv import load_dotenv
load_dotenv()

def hash_file(f):
    hasher = hashlib.sha256()
    hasher.update(f)
    return hasher.hexdigest()


def disk_cache(cache_dir='cache', key_fn=lambda *args, **kwargs: str(args) + str(kwargs)):
    os.makedirs(cache_dir, exist_ok=True)
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs)
            safe_key = key.replace(os.sep, "_")  # avoid directory traversal
            cache_path = os.path.join(cache_dir, f'{safe_key}.pkl')

            if os.path.exists(cache_path):
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)

            result = func(*args, **kwargs)
            with open(cache_path, 'wb') as f:
                pickle.dump(result, f)
            return result

        return wrapper

    return decorator

claid_config='''
{
    "operations": {
        "background": {
            "remove": {
                "category": "products",
                "clipping":false
            },
            "color": "transparent"
        }
    },
    "output": {
        "format": {
            "type": "png",
            "compression": "optimal"
        }
    }
}
'''


@disk_cache(key_fn=hash_file)
def remove_background(file:bytes) -> bytes:
    url = "https://api.claid.ai/v1-beta1/image/edit/upload"
    headers = {
        "Authorization": "Bearer " + os.getenv('CLAID_API_KEY')
    }
    files = {
        "file": ("no_file_name", file),
        "data": (None, claid_config, "application/json")
    }
    #session = get_retry_session(retries=5, backoff_factor=1)

    response = requests.post(url, headers=headers, files=files,timeout=(3, 30))
    response.raise_for_status()

    response_json = response.json()
    tmp_url = response_json['data']['output']['tmp_url']

    # Download the image from tmp_url
    img_response = requests.get(tmp_url,timeout=(3, 30))
    img_response.raise_for_status()
    return img_response.content
