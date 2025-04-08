from PIL import Image, ImageOps
import rembg
import claid
import io, os
from pathlib import Path
from tqdm import tqdm
#from prefect import flow, task
#from prefect.futures import wait
#from prefect.task_runners import ThreadPoolTaskRunner

#@task
def load_images(input_folder: str) -> list:
    """
    Load all image paths from the input folder.
    """
    image_paths = [p for p in Path(input_folder).rglob("*")
                   if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"}]
    return image_paths

#@task
def create_output_folder(output_folder: str) -> None:
    """
    Create the output folder if it does not exist.
    """
    os.makedirs(output_folder, exist_ok=True)
    print(f"Output folder ready: {output_folder}")


# Define Prefect flow

#@flow
def image_processing_pipeline(input_folder: str, output_folder: str, config: dict) -> None:
    """
    Flow to process all images in the input folder and save them to the output folder.
    """
    # Step 1: Prepare the output folder
    create_output_folder(output_folder)

    # Step 2: Load all images from the input folder
    image_paths = load_images(input_folder)
    results = []
    # Step 3: Process each image
    for image_path in tqdm(image_paths):
        transform_product_image(image_path, output_folder, config)

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

def position(img: Image, config:dict):
    # Compute space available
    target_w, target_h = config['resize']
    margins = config.get('margins',{})
    margin_top = margins.get('top', 0)
    margin_bottom = margins.get('bottom', 0)
    margin_left = margins.get('left', 0)
    margin_right = margins.get('right', 0)

    gravity = config.get('gravity','center')

    available_w = target_w - margin_left - margin_right
    available_h = target_h - margin_top - margin_bottom

    # Resize to fit within available space (maintain aspect ratio)
    img = ImageOps.contain(img,(available_w, available_h))

    # Create new image with transparent background
    canvas = Image.new("RGBA", (target_w, target_h), config['background_color'])

    # Compute paste position based on gravity
    pw, ph = img.size
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
def remove_bg(f,config):
    background_model = config.get('background_model','u2net')
    if background_model=='claid':
        return claid.remove_background(f)
    else:
        global sam_session
        if sam_session is None:
            sam_session = rembg.new_session(model_name=background_model)
        return rembg.remove(f,session = sam_session)

def transform_product_image(image_path : Path, output_folder:str, config:dict)->None:
    output_path = Path(output_folder) / image_path.name
    if output_path.exists():
        print(f"File already exists: {output_path}. Skipping task.")
        return

    # Open the image
    with open(image_path,"rb") as f:
        img = Image.open(remove_bg(f.read(),config))
        # Ensure image has an alpha channel (RGBA)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        img = img.crop(img.getbbox())  # remove transparent edges

        img = position(img, config)

        # Save the final image
        img = img.convert("RGB")
        img.save(output_path, format="JPEG")


# Example execution
if __name__ == "__main__":
    #input_folder = "/Users/einavitamar/Downloads/165"
    base_input_folder="/Users/einavitamar/Downloads/Prada Images - Need to update Margin"
    subfolder_configs = [("Small Handbags", 250), ("Handbags", 150), ("Backpacks",50), ("Wallets", 100)]
    #input_folder="input_images"
    # claid,isnet-general-use,birefnet-general,bria-rmbg,u2net
    background_model="claid"
    for (subfolder, side_margin) in subfolder_configs:
        input_folder = str(base_input_folder / Path(subfolder))
        #output_folder = str(Path(input_folder) / ("transformed_" + background_model))
        output_folder = input_folder + "_transformed_" + background_model
        config = {
            "background_color": (255,255,255,0),
            "resize": (1200, 1500),
            "gravity":"bottom",
            "margins":{"bottom":150,"left":side_margin,"right":side_margin},
            "background_model":background_model
        }
        if subfolder == "Wallets":
            config["margins"]["top"] = 350
        image_processing_pipeline(input_folder, output_folder, config)