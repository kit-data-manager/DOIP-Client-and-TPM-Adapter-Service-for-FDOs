#!/usr/bin/env python3
import os
import argparse
import tarfile
import numpy as np
from PIL import Image
import io

def ensure_three_channels(array):
    """
    Convert an array to have exactly 3 channels.
    - For a 2D array, stack it to create 3 channels.
    - For a 3D array:
      * If channels > 3, take the first 3 channels.
      * If channels < 3, duplicate the first channel to fill missing channels.
    """
    if array.ndim == 2:
        # Convert grayscale (2D) to RGB by stacking the array.
        return np.stack((array,) * 3, axis=-1)
    elif array.ndim == 3:
        channels = array.shape[-1]
        if channels == 3:
            return array
        elif channels > 3:
            return array[:, :, :3]
        else:  # channels < 3
            # Duplicate the first channel to fill missing channels.
            needed = 3 - channels
            filler = np.concatenate([array[:, :, 0:1]] * needed, axis=2)
            return np.concatenate([array, filler], axis=2)
    else:
        # If the array has unexpected dimensions, return it unmodified.
        return array

def convert_npy_to_png(npy_file_obj, output_path):
    try:
        # Read the entire file content and wrap it in a BytesIO object.
        file_bytes = npy_file_obj.read()
        array = np.load(io.BytesIO(file_bytes))
    except Exception as e:
        print(f"Error loading npy file: {e}")
        return False

    # Check and convert the array to 3 channels if necessary.
    try:
        if array.ndim == 3 and array.shape[-1] not in (1, 3, 4):
            print(f"Array shape {array.shape} has non-standard channel count. Converting to 3 channels.")
            array = ensure_three_channels(array)
        elif array.ndim == 2:
            # Convert grayscale image to 3 channels.
            array = ensure_three_channels(array)
    except Exception as e:
        print(f"Error processing array shape: {e}")
        return False

    try:
        # Convert the array to an image.
        img = Image.fromarray(array)
    except Exception as e:
        print(f"Error converting array to image: {e}")
        return False

    try:
        # Save the image as PNG.
        img.save(output_path, format='PNG')
    except Exception as e:
        print(f"Error saving PNG image {output_path}: {e}")
        return False

    return True

def process_tar_archive(tar_path, output_dir):
    print(f"Processing archive: {tar_path}")
    try:
        with tarfile.open(tar_path, 'r:gz') as tar:
            for member in tar.getmembers():
                if member.isfile() and member.name.endswith('.npy'):
                    npy_file = tar.extractfile(member)
                    if npy_file is None:
                        continue

                    # Create an output filename using the tar base and member name.
                    tar_base = os.path.splitext(os.path.basename(tar_path))[0]
                    if tar_base.endswith('.tar'):
                        tar_base = tar_base[:-4]
                    member_name = os.path.basename(member.name)
                    output_filename = f"{tar_base}_{os.path.splitext(member_name)[0]}.png"
                    output_filepath = os.path.join(output_dir, output_filename)
                    
                    if convert_npy_to_png(npy_file, output_filepath):
                        print(f"Saved PNG image: {output_filepath}")
                    else:
                        print(f"Failed to convert {member.name} in archive {tar_path}")
    except Exception as e:
        print(f"Error processing tar archive {tar_path}: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Extract npy images from a tar.gz archive and convert them to PNG format."
    )
    parser.add_argument('--file', type=str, required=True,
                        help='Path to the tar.gz archive containing npy images.')
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"The file {args.file} does not exist or is not a file.")
        return

    # Create an output directory (png_images) in the same folder as the tar.gz file.
    tar_dir = os.path.dirname(os.path.abspath(args.file))
    output_dir = os.path.join(tar_dir, "png_images")
    os.makedirs(output_dir, exist_ok=True)

    process_tar_archive(args.file, output_dir)
    print("Conversion complete.")

if __name__ == "__main__":
    main()
