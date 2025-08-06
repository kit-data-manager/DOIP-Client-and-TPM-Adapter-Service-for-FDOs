import os
import argparse
import tarfile
import numpy as np
from PIL import Image
import io
import zstandard as zstd

def ensure_three_channels(array):
    """
    Convert an array to have exactly 3 channels.
    """
    if array.ndim == 2:
        return np.stack((array,) * 3, axis=-1)
    elif array.ndim == 3:
        channels = array.shape[-1]
        if channels == 3:
            return array
        elif channels > 3:
            return array[:, :, :3]
        else:
            needed = 3 - channels
            filler = np.concatenate([array[:, :, 0:1]] * needed, axis=2)
            return np.concatenate([array, filler], axis=2)
    else:
        return array

def convert_npy_to_png(npy_file_obj, output_path):
    try:
        file_bytes = npy_file_obj.read()
        array = np.load(io.BytesIO(file_bytes))
    except Exception as e:
        print(f"Error loading npy file: {e}")
        return False

    try:
        if array.ndim == 3 and array.shape[-1] not in (1, 3, 4):
            print(f"Array shape {array.shape} has non-standard channel count. Converting to 3 channels.")
            array = ensure_three_channels(array)
        elif array.ndim == 2:
            array = ensure_three_channels(array)
    except Exception as e:
        print(f"Error processing array shape: {e}")
        return False

    try:
        img = Image.fromarray(array)
    except Exception as e:
        print(f"Error converting array to image: {e}")
        return False

    try:
        img.save(output_path, format='PNG')
    except Exception as e:
        print(f"Error saving PNG image {output_path}: {e}")
        return False

    return True

def is_zst_file(file_path):
    """
    Check if the file starts with the Zstandard magic number.
    """
    try:
        with open(file_path, 'rb') as f:
            magic = f.read(4)
            return magic == b'\x28\xb5\x2f\xfd'
    except Exception as e:
        print(f"Error checking file type: {e}")
        return False

def process_tar_archive(tar_path, output_dir):
    print(f"Processing archive: {tar_path}")
    try:
        if is_zst_file(tar_path):
            print("Detected Zstandard-compressed tar archive.")
            with open(tar_path, 'rb') as compressed:
                dctx = zstd.ZstdDecompressor()
                with dctx.stream_reader(compressed) as reader:
                    with tarfile.open(fileobj=reader, mode='r|') as tar:
                        for member in tar:
                            if member.isfile() and member.name.endswith('.npy'):
                                npy_file = tar.extractfile(member)
                                if npy_file is None:
                                    continue
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
        else:
            print("Assuming gzip-compressed tar archive.")
            with tarfile.open(tar_path, 'r:gz') as tar:
                for member in tar.getmembers():
                    if member.isfile() and member.name.endswith('.npy'):
                        npy_file = tar.extractfile(member)
                        if npy_file is None:
                            continue
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
        description="Extract npy images from a tar archive (.tar.zst or .tar.gz) and convert them to PNG format."
    )
    parser.add_argument('--file', type=str, required=True,
                        help='Path to the archive containing .npy images.')
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"The file {args.file} does not exist or is not a file.")
        return

    tar_dir = os.path.dirname(os.path.abspath(args.file))
    output_dir = os.path.join(tar_dir, "png_images")
    os.makedirs(output_dir, exist_ok=True)

    process_tar_archive(args.file, output_dir)
    print("Conversion complete.")

if __name__ == "__main__":
    main()
