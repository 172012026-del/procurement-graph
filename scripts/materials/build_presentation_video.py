"""Render the local presentation to a 1080p MP4 with Windows offline narration."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import os
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def main():
    if os.name!='nt':
        raise SystemExit('Offline narration uses Windows SAPI; provide an equivalent local narrator on other systems')
    for tool in ['pdftoppm','ffmpeg','ffprobe']:
        if not shutil.which(tool):
            raise SystemExit('Missing presentation tool: '+tool)
    runtime=ROOT/'.cache/materials/video'
    runtime.mkdir(parents=True,exist_ok=True)
    source=ROOT/'docs/materials/presentation-narration.json'
    records=json.loads(source.read_text('utf-8'))
    subprocess.run(['pdftoppm','-png','-scale-to-x','1920','-scale-to-y','1080',
                    str(ROOT/'deliverables/presentation.pdf'),str(runtime/'slide')],cwd=ROOT,check=True)
    images=sorted(runtime.glob('slide-*.png'))
    if len(images)!=len(records):
        raise ValueError('Narration count differs from PDF slide count')
    def quote(value):
        return "'"+str(value).replace("'","''")+"'"
    program=f'''$ErrorActionPreference='Stop'
$voice=New-Object -ComObject SAPI.SpVoice
$voices=$voice.GetVoices()
for($i=0;$i -lt $voices.Count;$i++){{if($voices.Item($i).GetDescription() -match 'Huihui|Chinese'){{$voice.Voice=$voices.Item($i);break}}}}
$voice.Rate=0
$records=Get-Content -LiteralPath {quote(source)} -Raw -Encoding UTF8 | ConvertFrom-Json
foreach($record in $records){{
  $stream=New-Object -ComObject SAPI.SpFileStream
  $wave=Join-Path {quote(runtime)} ('speech-'+$record.slide+'.wav')
  $stream.Open($wave,3,$false)
  $voice.AudioOutputStream=$stream
  $voice.Speak($record.narration,0) | Out-Null
  $stream.Close()
}}
'''
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(program.encode('utf-16le')).decode()],cwd=ROOT,check=True)
    clips=[]
    for image,record in zip(images,records):
        wave=runtime/f"speech-{record['slide']}.wav"
        duration=float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(wave)],capture_output=True,text=True,check=True).stdout)+.7
        clip=runtime/f"segment-{record['slide']:02d}.mp4"
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-i',str(image),'-i',str(wave),
                        '-vf','scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
                        '-c:v','libx264','-preset','ultrafast','-crf','24','-r','15','-pix_fmt','yuv420p',
                        '-c:a','aac','-b:a','96k','-af','apad','-t',str(duration),str(clip)],cwd=ROOT,check=True)
        clips.append(clip)
    listing=runtime/'concat.txt'
    listing.write_text(''.join("file '"+clip.as_posix().replace("'","'\\''")+"'\n" for clip in clips),encoding='utf-8')
    output=ROOT/'deliverables/presentation.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(output)],cwd=ROOT,check=True)
    metadata=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type,width,height','-show_entries','format=duration','-of','json',str(output)],capture_output=True,text=True,check=True).stdout)
    assert float(metadata['format']['duration'])<=600
    assert any(row.get('width')==1920 and row.get('height')==1080 for row in metadata['streams'])
    assert any(row['codec_type']=='audio' for row in metadata['streams'])
    print(json.dumps({'output':str(output),'duration':metadata['format']['duration'],'resolution':'1920x1080','slides':len(records),'offline_narration':True}))


if __name__=='__main__':
    main()
