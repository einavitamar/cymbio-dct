import requests
from PIL import Image

from io import BytesIO
claid_config='''
{
    "operations": {
        "background": {
            "remove": {
                "clipping": true,
                "category": {
                    "type": "products",
                    "version": "3"
                }
            }
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

def remove_background(file:BytesIO)->BytesIO:
    url = "https://api.claid.ai/v1-beta1/image/edit/upload"
    headers = {
        "Authorization": "Bearer 79604bac855e4d01adbb3a974d13df8d"
    }
    files = {
        "file": ("no_file_name", file),
        "data": (None, claid_config, "application/json")
    }

    response = requests.post(url, headers=headers, files=files)

    #print(response.status_code)
    #print(response.json())
    response_json = response.json()
    tmp_url = response_json['data']['output']['tmp_url']

    # Download the image from tmp_url
    img_response = requests.get(tmp_url)
    img_bytes = BytesIO(img_response.content)
    return img_bytes
    #return Image.open(img_bytes)
