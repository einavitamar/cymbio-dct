import json

from PIL import Image, ImageOps
import rembg
import claid
import copy
import io, os
from io import BytesIO
from pathlib import Path
from tqdm import tqdm
#from prefect import flow, task
#from prefect.futures import wait
#from prefect.task_runners import ThreadPoolTaskRunner
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("processing_errors.log"),
        logging.StreamHandler()
    ]
)

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png','.gif','.bmp','.tiff')
#@task
def create_output_folder(output_folder: str) -> None:
    """
    Create the output folder if it does not exist.
    """
    os.makedirs(output_folder, exist_ok=True)
    print(f"Output folder ready: {output_folder}")


# Define Prefect flow

def resize_old(img : Image,config:dict)->Image:
    # Get original dimensions
    width, height = img.size
    # Determine the new size based on aspect ratio requirements
    if width > height:  # Landscape
        new_width = min(max(width, 1080), 6000)
        new_height = int(new_width * 2 / 3)
        product_max_width = int (new_width * 0.6)
        product_max_height = int(new_height * 0.9)
    elif height > width:  # Portrait
        new_height = min(max(height, 1080), 6000)
        new_width = int(new_height * 2 / 3)
        product_max_height = int (new_height * 0.6)
        product_max_width = int(new_width * 0.9)
    else:  # Square
        new_width = new_height = max(1080, min(width, 6000))
        product_max_height = int (new_height * 0.9)
        product_max_width = int(new_width * 0.9)

    # Resize image with padding to maintain aspect ratio
    img = ImageOps.contain(img, (product_max_width, product_max_height))
    ImageOps.fit()
    # Create a blank white canvas with the required dimensions
    canvas = Image.new("RGB", (new_width, new_height),config['background_color'])

    # Calculate the position to paste the product centrally
    x_offset = (new_width - img.width) // 2
    y_offset = (new_height - img.height) // 2
    canvas.paste(img, (x_offset, y_offset), mask=img)
    return canvas


from PIL import Image


def override_config_on_zoomed_in_images(img : Image, bbox : tuple,current_config: dict)->dict:
    config = copy.deepcopy(current_config)
    left, top, right, bottom = bbox
    img_w, img_h = img.size

    if top == 0 and bottom==img_h and left == 0 and right == img_w:
        config["resize"]["fit"] = 'fill'
    if top == 0:
        config['margins']['top'] = 0
        config['gravity'] = 'top'
    if bottom == img_h:
        config['margins']['bottom'] = 0
        config['gravity'] = 'bottom'
    if left == 0:
        config['margins']['left'] = 0
        config['gravity'] = 'left'
    if right == img_w:
        config['margins']['right'] = 0
        config['gravity'] = 'right'
    return config


def position(img: Image, config:dict):

    if not config.get("resize"):
        config["resize"] = {}
    if not config['resize'].get('fit'):
        config['resize']['fit'] = 'contain'
    bbox = img.getbbox()
    config = override_config_on_zoomed_in_images(img,bbox,config) #override config['margins'] and config['resize']['fit']
    # Compute space available
    margins = config.get('margins',{})
    margin_top = margins.get('top', 0)
    margin_bottom = margins.get('bottom', 0)
    margin_left = margins.get('left', 0)
    margin_right = margins.get('right', 0)

    target_w = config['resize'].get('width',img.size[0])
    target_h = config['resize'].get('height',img.size[1])
    available_w = target_w - margin_left - margin_right
    available_h = target_h - margin_top - margin_bottom

    # crop / Resize
    fit = config['resize']['fit']
    img = img.crop(bbox)  # remove transparent edges
    if fit== 'cover':
        img = ImageOps.cover(img, (available_w, available_h))
    elif fit=='stretch'or fit=='fill':
        img = img.resize((available_w, available_h))
    else: #contain
        img = ImageOps.contain(img,(available_w, available_h))

    # Create new image with transparent background
    canvas = Image.new("RGBA", (target_w, target_h), tuple(config['background_color']))

    # Compute paste position based on gravity
    pw, ph = img.size
    gravity = config.get('gravity','center')
    if gravity == 'top':
        x = margin_left + (available_w - pw) // 2
        y = margin_top
    elif gravity == 'bottom':
        x = margin_left + (available_w - pw) // 2
        y = target_h - margin_bottom - ph
    elif gravity == 'left':
        x = margin_left
        y = margin_top + (available_h - ph) // 2
    elif gravity == 'right':
        x = target_w - margin_right - pw
        y = margin_top + (available_h - ph) // 2
    else:  # center
        x = margin_left + (available_w - pw) // 2
        y = margin_top + (available_h - ph) // 2

    # Paste product onto canvas
    canvas.paste(img, (x, y), img)
    return canvas

sam_session = None
def remove_bg(f:bytes,config:dict)->bytes:
    # background models: claid,isnet-general-use,birefnet-general,bria-rmbg,u2net
    background_model = config.get('background_model','u2net')
    if background_model=='claid':
        return claid.remove_background(f)
    else:
        global sam_session
        if sam_session is None:
            sam_session = rembg.new_session(model_name=background_model)
        return rembg.remove(f,session = sam_session)


def process_product_image(image_path : str, output_path:str, config:dict)->bool:
        if Path(output_path).exists():
            print(f"File already exists: {output_path}. Skipping task.")
            return False

        # Open the image
        with open(image_path,"rb") as f:
            img = Image.open(BytesIO(remove_bg(f.read(),config)))
            # Ensure image has an alpha channel (RGBA)
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            if config.get("resize") or config.get("margins") or config.get("gravity"):
                img = position(img, config)

            # Save the final image
            img = img.convert("RGB")
            img.save(output_path, format="JPEG")
            return True


def merge_configs(parent_config, override_config):
    """Merge two configs with the override_config taking priority."""
    merged = copy.deepcopy(parent_config)

    for key, value in override_config.items():
        if isinstance(value, dict) and key in merged:
            merged[key].update(value)
        else:
            merged[key] = value
    return merged

def load_config(path):
    config_path = os.path.join(path, 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


def process_folder(input_folder :str, output_folder :str, parent_config:dict = None) -> int:
    local_config = load_config(input_folder)
    config = merge_configs(parent_config or {}, local_config)

    os.makedirs(output_folder, exist_ok=True)
    max_images = config.get("max_images",9e14)
    n_processed = 0

    for entry in tqdm(os.listdir(input_folder)):
        if entry == 'config.json':
            continue
        input_path = os.path.join(input_folder, entry)
        output_path = os.path.join(output_folder, entry)

        if os.path.isdir(input_path):
            n_processed+=process_folder(input_path, output_path, config)
        elif entry.lower().endswith(IMAGE_EXTENSIONS):
            try:
                if process_product_image(input_path, output_path, config):
                    n_processed+=1
            except Exception as e:
                logging.error(f"Failed to process {input_path}: {e}", exc_info=True)
        if n_processed >= max_images:
            break
    return n_processed

# Example execution

#If the bb is on one of the borders: (1) change all margins to zero (2)change fit model to "strech"
if __name__ == "__main__":
    input_folder = "/Users/einavitamar/Downloads/Archive 5"
    #input_folder = "/Users/einavitamar/Downloads/Fabletics 4.2"
    #input_folder="images/Prada"
    process_folder(input_folder,input_folder + "_processed")
