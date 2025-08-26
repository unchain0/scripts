#!/usr/bin/env -S uv run --script

"""
Video to Text Transcription Tool

Este script transcreve áudio de vídeos usando Google Speech Recognition API.
Suporta processamento paralelo e divisão inteligente por silêncio.
"""

import argparse
import concurrent.futures
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Set

import speech_recognition as sr
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from pydub.silence import split_on_silence
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

SUPPORTED_EXTENSIONS: Set[str] = {
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
    ".m4v",
    ".flv",
}
DEFAULT_CHUNK_LENGTH_MS = 30000
MIN_CHUNK_DURATION_MS = 500
AUDIO_SAMPLE_RATE = 16000
MAX_PARALLEL_WORKERS = 4
MAX_API_WORKERS = 3

logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def check_audio_quality(audio_segment: AudioSegment) -> AudioSegment:
    if audio_segment.dBFS < -40.0:
        audio_segment = audio_segment.apply_gain(25)
    elif audio_segment.dBFS < -30.0:
        audio_segment = audio_segment.apply_gain(15)

    normalized = audio_segment.normalize().high_pass_filter(300)

    if len(normalized) > 1000:
        normalized = normalized.fade_in(100)

    return normalized


@retry(wait=wait_exponential(multiplier=1, max=10), stop=stop_after_attempt(3))
def transcribe_chunk(
    recognizer: sr.Recognizer, audio_data: sr.AudioData, language: str
) -> str:
    try:
        return recognizer.recognize_google(audio_data, language=language)
    except (sr.UnknownValueError, sr.RequestError):
        try:
            return recognizer.recognize_sphinx(audio_data, language=language)
        except Exception:
            return ""


def process_chunk(
    chunk: AudioSegment,
    recognizer: sr.Recognizer,
    index: int,
    tmp_dir: str,
    language: str,
) -> str:
    chunk_path = os.path.join(tmp_dir, f"chunk_{index:03d}.wav")
    chunk.export(chunk_path, format="wav")

    try:
        with sr.AudioFile(chunk_path) as source:
            recognizer.energy_threshold = 100
            audio_data = recognizer.record(source)
            result = transcribe_chunk(recognizer, audio_data, language)
            return result.strip()
    except Exception:
        return ""
    finally:
        if os.path.exists(chunk_path):
            os.remove(chunk_path)


def transcrever_video(video_path: str, language: str = "pt-BR") -> Dict:
    resultado = {"texto": "", "duracao": 0.0, "tempo_transcricao": 0.0}
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with tqdm(
                total=5, desc=f"Processando {Path(video_path).name}"
            ) as main_pbar:
                main_pbar.set_description("Extraindo áudio")
                audio_temp = os.path.join(tmp_dir, "temp_audio.wav")
                with VideoFileClip(video_path) as video:
                    resultado["duracao"] = video.duration
                    video.audio.write_audiofile(
                        audio_temp,
                        codec="pcm_s16le",
                        ffmpeg_params=["-ac", "1", "-ar", str(AUDIO_SAMPLE_RATE)],
                        verbose=False,
                        logger=None,
                    )
                main_pbar.update(1)

                main_pbar.set_description("Processando áudio")
                audio = AudioSegment.from_wav(audio_temp)
                audio = check_audio_quality(audio)
                main_pbar.update(1)

                main_pbar.set_description("Dividindo por silêncio")
                chunks = split_on_silence(
                    audio,
                    min_silence_len=300,
                    silence_thresh=audio.dBFS - 16,
                    keep_silence=500,
                )
                if not chunks:
                    chunks = [
                        audio[i : i + DEFAULT_CHUNK_LENGTH_MS]
                        for i in range(0, len(audio), DEFAULT_CHUNK_LENGTH_MS)
                    ]
                main_pbar.update(1)

                main_pbar.set_description("Transcrevendo chunks")
                recognizer = sr.Recognizer()
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=MAX_PARALLEL_WORKERS
                ) as executor:
                    futures = [
                        executor.submit(
                            process_chunk, chunk, recognizer, i, tmp_dir, language
                        )
                        for i, chunk in enumerate(chunks)
                    ]
                    results = [
                        future.result(timeout=60)
                        for future in tqdm(futures, desc="Transcrevendo", leave=False)
                    ]
                main_pbar.update(1)

                main_pbar.set_description("Finalizando")
                texto_final = " ".join(filter(None, results)).strip()
                resultado["texto"] = (
                    texto_final or "Não foi possível transcrever o áudio."
                )
                main_pbar.update(1)

    except Exception as e:
        resultado["texto"] = f"Erro ao processar {video_path}: {e}"

    return resultado


def salvar_resultado(
    video_path: str, resultado: Dict, salvar_srt: bool = False
) -> List[str]:
    base = os.path.splitext(os.path.basename(video_path))[0]
    arquivos = []
    txt_path = f"{base}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        # f.write(f"# Duração do vídeo: {timedelta(seconds=int(resultado['duracao']))}\n")
        f.write(resultado["texto"])
    arquivos.append(txt_path)

    if salvar_srt:
        srt_path = f"{base}.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            lines = resultado["texto"].split(". ")
            for i, line in enumerate(lines):
                f.write(f"{i + 1}\n")
                f.write(f"00:00:{i:02d},000 --> 00:00:{i + 1:02d},000\n")
                f.write(line.strip() + "\n\n")
        arquivos.append(srt_path)

    return arquivos


def validar_arquivo(path: str) -> bool:
    return os.path.exists(path) and any(
        path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS
    )


def main():
    parser = argparse.ArgumentParser(
        description="Video to Text Transcriber with Google Speech Recognition"
    )
    parser.add_argument("videos", nargs="+", help="Caminhos para os arquivos de vídeo")
    parser.add_argument(
        "--lang", default="pt-BR", help="Idioma da transcrição (default: pt-BR)"
    )
    parser.add_argument(
        "--srt", action="store_true", help="Exportar transcrição em formato .srt também"
    )

    args = parser.parse_args()
    video_paths = [v for v in args.videos if validar_arquivo(v)]

    if not video_paths:
        print("Nenhum arquivo válido foi fornecido.")
        sys.exit(1)

    for video in video_paths:
        resultado = transcrever_video(video, language=args.lang)
        arquivos = salvar_resultado(video, resultado, salvar_srt=args.srt)
        for arq in arquivos:
            print(f"✓ Arquivo salvo: {arq}")


if __name__ == "__main__":
    main()
