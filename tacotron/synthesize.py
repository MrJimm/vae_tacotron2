import argparse
import os
import re
from hparams import hparams, hparams_debug_string
from tacotron.synthesizer import Synthesizer
import tensorflow as tf
import time
from tqdm import tqdm
from tacotron.utils.audio import load_wav, melspectrogram
import numpy as np
from datasets import audio

def run_eval(args, checkpoint_path, output_dir, sentences):
	print(hparams_debug_string())
	synth = Synthesizer()
	synth.load(checkpoint_path)
	eval_dir = os.path.join(output_dir, 'eval')
	log_dir = os.path.join(output_dir, 'logs-eval')
	wav = load_wav(args.reference_audio)
	reference_mel = melspectrogram(wav).transpose()
	#Create output path if it doesn't exist
	os.makedirs(eval_dir, exist_ok=True)
	os.makedirs(log_dir, exist_ok=True)
	os.makedirs(os.path.join(log_dir, 'wavs'), exist_ok=True)
	os.makedirs(os.path.join(log_dir, 'plots'), exist_ok=True)

	with open(os.path.join(eval_dir, 'map.txt'), 'w') as file:
		for i, text in enumerate(tqdm(sentences)):
			start = time.time()
			mel_filename = synth.synthesize(text, i+1, eval_dir, log_dir, None, reference_mel)

			file.write('{}|{}\n'.format(text, mel_filename))
	print('synthesized mel spectrograms at {}'.format(eval_dir))

def run_synthesis(args, checkpoint_path, output_dir, sentences):
	metadata_filename = os.path.join(args.input_dir, 'train.txt')
	print(hparams_debug_string())
	synth = Synthesizer()
	synth.load(checkpoint_path, gta=args.GTA)

	wav = load_wav(args.reference_audio)
	reference_mel = melspectrogram(wav).transpose()

	with open(metadata_filename, encoding='utf-8') as f:
		metadata = [line.strip().split('|') for line in f]
		frame_shift_ms = hparams.hop_size / hparams.sample_rate
		hours = sum([int(x[4]) for x in metadata]) * frame_shift_ms / (3600)
		print('Loaded metadata for {} examples ({:.2f} hours)'.format(len(metadata), hours))

	if args.GTA==True:
		synth_dir = os.path.join(output_dir, 'gta')
	else:
		synth_dir = os.path.join(output_dir, 'natural')

	#Create output path if it doesn't exist
	os.makedirs(synth_dir, exist_ok=True)
	os.makedirs(os.path.join(synth_dir, 'wavs/'), exist_ok=True)

	print('starting synthesis')
	with open(os.path.join(synth_dir, 'map.txt'), 'w') as file:
		#for i, meta in enumerate(tqdm(metadata)):
			#text = meta[5]
		for i, text in enumerate(tqdm(sentences)):
			mel_output_filename = synth.synthesize(text=text, index=i+1, out_dir=synth_dir, log_dir=None, mel_filename=None, reference_mel=reference_mel)

			mels = np.load(mel_output_filename)
			wav = audio.inv_mel_spectrogram(mels.T)
			audio.save_wav(wav, os.path.join(synth_dir, 'wavs/speech-wav-{:05d}-mel.wav'.format(i+1)))

			with open(os.path.join(synth_dir, 'wavs/speech-wav-{:05d}.txt'.format(i+1)), 'w') as tf:
				tf.write(text)

			if hparams.predict_linear:
				# save wav (linear -> wav)
				wav = audio.inv_linear_spectrogram(linear.T)
				audio.save_wav(wav, os.path.join(synth_dir, 'wavs/speech-wav-{:05d}-linear.wav'.format(i+1)))

		#file.write('{}|{}|{}|{}\n'.format(text, mel_filename, mel_output_filename, wav_filename))
	print('synthesized mel spectrograms at {}'.format(synth_dir))

def tacotron_synthesize(args):
	hparams.parse(args.hparams)
	os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
	output_dir = 'tacotron_' + args.output_dir

	if args.text_list != '':
		with open(args.text_list, 'rb') as f:
			sentences = list(map(lambda l: l.decode("utf-8")[:-1], f.readlines()))
	else:
		sentences = hparams.sentences

	try:
		checkpoint_path = tf.train.get_checkpoint_state(args.checkpoint).model_checkpoint_path
		print('loaded model at {}'.format(checkpoint_path))
	except:
		raise AssertionError('Cannot restore checkpoint: {}, did you train a model?'.format(args.checkpoint))

	if args.mode == 'eval':
		run_eval(args, checkpoint_path, output_dir, sentences)
	else:
		run_synthesis(args, checkpoint_path, output_dir, sentences)
