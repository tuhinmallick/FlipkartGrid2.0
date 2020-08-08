import model
import torch
import numpy as np
from audio_utils import read_wav, write_wav
import os
from glob import glob
from pesq import pesq
import time
from table_logger import TableLogger
import json
import requests
import warnings
warnings.filterwarnings("ignore")
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--ckpt", default="best.pth", type=str, help="path to checkpoint")
parser.add_argument("--input_dir", required=True, type=str, help="path to input folder")
parser.add_argument("--asr", default=False, type=bool, help="flag for asr on/off")
parser.add_argument("--sr", default=16000, type=int, help="sampling_rate")
parser.add_argument("--format", default="*wav", type=str, help="audio format")
parser.add_argument("--output_dir", required=True, type=str, help="path to output folder")
args = parser.parse_args()

def ASR(audio_sample):
    headers = {'Authorization': 'Token 3715119fd7753d33bedbd3c2832752ee7b0a10c7'}
    data = {'user' : '310' ,'language' : 'HI'}
    files = {'audio_file' : open(audio_sample,'rb')}
    url = 'https://dev.liv.ai/liv_transcription_api/recordings/'
    res = (requests.post(url, headers = headers, data = data, files = files)).json()
    return res

if __name__ == "__main__":

    checkpoint_path = args.ckpt
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    denoiser = model.Model().to(device)
    ckpt = torch.load(checkpoint_path)
    denoiser.load_state_dict(ckpt)

    print("Loading saved model from {}".format(checkpoint_path))
    print("Model initialised, number of params : {}M".format(sum(p.numel() for p in denoiser.parameters())/1e6))

    noisy_dir = args.input_dir
    output_dir = args.output_dir
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_audio = os.path.join(output_dir, "audio")
    if not os.path.exists(output_audio):
        os.makedirs(output_audio)
    output_trans = os.path.join(output_dir, "transcripts")
    if not os.path.exists(output_trans):
        os.makedirs(output_trans)

    sr = args.sr
    
    noisy_files = sorted(glob(os.path.join(noisy_dir, args.format)))
    time_counter = []
    pesq_counter = []
    tb = TableLogger(columns="FILE,TIME (secs),PESQ",float_format='{:,.2f}'.format, default_colwidth=15)

    for f in noisy_files:
        audio = read_wav(f, sr)
        start = time.time()
        with torch.no_grad():
            raw = torch.tensor([audio], dtype=torch.float32, device=device)
            out = denoiser(raw)
            out = [np.squeeze(s.detach().cpu().numpy()) for s in out]
        
        t = time.time() - start
        score = pesq(sr, out[0], audio, 'wb')
        time_counter.append(t)
        pesq_counter.append(score)
        tb(os.path.basename(f).split(".")[0], t, score)
	    
        write_wav(os.path.join(output_audio, os.path.basename(f).split(".")[0] + "_clean.wav"), out[0], sr)
        write_wav(os.path.join(output_audio, os.path.basename(f).split(".")[0] + "_noise.wav"), out[1], sr)

        if args.asr:
            transcript = ASR(os.path.join(output_audio, os.path.basename(f).split(".")[0] + "_clean.wav"))
            with open(os.path.join(transcript_dir, os.path.basename(o).split(".")[0] + ".json"), 'w') as outfile:
                json.dump(transcript, outfile)

    print("\n")
    print("Time stats: min: {:.2f} mean: {:.2f} max: {:.2f}".format(min(time_counter), sum(time_counter)/len(time_counter), max(time_counter)))
    print("PESQ stats: min: {:.2f} mean: {:.2f} max: {:.2f}".format(min(pesq_counter), sum(pesq_counter)/len(pesq_counter), max(pesq_counter)))

# import pandas as pd
# from jiwer import wer
# import jiwer
# import os
# from glob import glob
# import json

# data = pd.read_excel("original.xlsx")
# wer_score = []
# transcript_files = sorted(glob(os.path.join("transcript", '*_clean.json')))

# for i in range(len(transcript_files)):
#     f = os.path.basename(transcript_files[i]).split("_")[0]
#     orig = data["Transcription "][int(f)]
#     orig = orig.replace("@", "")
#     orig = orig.replace("_", "")
#     orig = orig.strip()
#     if orig != "":
#         with open(transcript_files[i]) as t:
#             tr = json.load(t)
#         pred = tr["transcriptions"][0]["utf_text"]
#         pred = pred.replace("@", "")
#         pred = pred.replace("_", "")
#         orig = orig.strip()

#         transformation = jiwer.Compose([
#         jiwer.Strip(),
#         jiwer.SentencesToListOfWords(),
#         jiwer.RemoveEmptyStrings()
#         ])
#         error = wer(orig, pred,truth_transform=transformation,hypothesis_transform=transformation)
        
#         if error < 1:
#             print(transformation(pred))
#             print(transformation(orig))
#             print(error)
#             exit()
#         wer_score.append(error)
#         # exit()
# print("min: {}, mean: {}, max: {}".format(min(wer_score), sum(wer_score)/len(wer_score), max(wer_score)))