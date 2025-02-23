import os
from pathlib import Path
import subprocess


# ===== Video Transform =====

def transform_to_audio(src_fp, audio_format='.wav', ffmpeg_cmd_fp='ffmpeg'):

    tmp_wave_fp = Path(src_fp).with_suffix(audio_format).as_posix()

    if os.path.exists(tmp_wave_fp):
        os.remove(tmp_wave_fp)

    # whisper.cpp only accept .wav
    if not os.path.exists(tmp_wave_fp):
        subprocess.run([
            ffmpeg_cmd_fp, 
            "-y",
            "-loglevel", "error",
            "-i", src_fp,
            "-acodec", "pcm_s16le",
            "-ac", "1",
            "-ar", "16000",
            tmp_wave_fp,
            # tmp_wave_fp.absolute().as_posix(),
        ])

    return tmp_wave_fp


# ===== File Util =====

def get_all_file_with_ext(dir_fp, ext, recursive=True):

    for fn in os.listdir(dir_fp):
        fp = os.path.join(dir_fp, fn)

        if os.path.isfile(fp):
            if not fn.endswith(ext):
                continue
            yield fp

        elif os.path.isdir(fp) and recursive:
            for f in get_all_file_with_ext(fp, ext):
                yield f


def make_sure_dir_exists(dir_fp):
    if os.path.exists(dir_fp) and os.path.isdir(dir_fp):
        return
    os.makedirs(dir_fp)


def make_dirs_for_fp(fp):
    if os.path.exists(fp):
        return
    parent_dir = Path(fp).parent.as_posix() 
    if os.path.exists(parent_dir) and os.path.isdir(parent_dir):
        return
    os.makedirs(parent_dir)