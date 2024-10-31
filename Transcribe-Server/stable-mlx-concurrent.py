import mlx_whisper
import time
import stable_whisper
from pyannote.audio import Pipeline
import torch
import torchaudio
import json
import concurrent.futures

def inference(audio, **kwargs) -> dict:
    output = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo="mlx-community/whisper-base.en-mlx",
        word_timestamps=True,
        language="en",
        verbose=True
    )
    return output

def transcribe_audio(audio_file):
    print("Starting transcription...")
    whisperResult = stable_whisper.transcribe_any(inference, audio_file, vad=True)
    return whisperResult.to_dict()

def diarize_audio(audio_file):
    print("Starting diarization...")
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token="YOUR_HF_TOKEN"
    )
    pipeline.to(device)
    waveform, sample_rate = torchaudio.load(audio_file)
    audio_data = {"waveform": waveform.to(device), "sample_rate": sample_rate}
    return pipeline(audio_data)

# Start timer
start = time.time()
audio_file = "./audio3.wav"

# Select device
if torch.cuda.is_available():
    device = torch.device("cuda")
elif torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")

print(f"Using device: {device}")

# Run transcription and diarization in parallel
with concurrent.futures.ThreadPoolExecutor() as executor:
    future_transcription = executor.submit(transcribe_audio, audio_file)
    future_diarization = executor.submit(diarize_audio, audio_file)
    result = future_transcription.result()
    diarization = future_diarization.result()

# Efficient Speaker Matching
new_segments = []
transcript_segments = result["segments"]
diarization_turns = list(diarization.itertracks(yield_label=True))

i, j = 0, 0
while i < len(transcript_segments) and j < len(diarization_turns):
    segment = transcript_segments[i]
    turn, _, speaker = diarization_turns[j]

    segment_start = segment["start"]
    segment_end = segment["end"]
    diar_start = turn.start
    diar_end = turn.end

    if diar_end <= segment_start:
        j += 1
    elif segment_end <= diar_start:
        i += 1
    else:
        # Overlapping segment
        new_segments.append({
            "start": segment_start,
            "end": segment_end,
            "speaker": speaker,
            "text": segment["text"],
            "words": segment["words"]
        })
        i += 1  # Move to the next transcript segment

# Assign 'Unknown' speaker to any remaining transcript segments
for segment in transcript_segments[i:]:
    new_segments.append({
        "start": segment["start"],
        "end": segment["end"],
        "speaker": "Unknown",
        "text": segment["text"],
        "words": segment["words"]
    })

diarized_result = {
    "text": result["text"],
    "segments": new_segments,
    "language": result["language"]
}

# Save the new structure as a JSON file
with open('diarized.json', 'w') as f:
    json.dump(diarized_result, f, indent=4)

# End timer
end = time.time()
print(f"Time taken: {end - start} seconds")