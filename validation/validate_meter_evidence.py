"""Actual-model checks on independent arrangements; results include failures.

Uses the separately authored regression-test synthesizer with additional seeds
and tempos. Generated media stay in ignored build/. No model transcription.
"""
import base64
import io
import json
from pathlib import Path
import sys
import numpy as np
import mido
import soundfile as sf
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'upstream'),str(ROOT/'tests')]
from test_rhythm_evidence import arrangement
from test_rhythm_edges import performance,events_in_seconds
from muscriptor.utils.rhythm import detect,Timeline,retime
OUT=ROOT/'build/vgm-final-validation/meter-evidence'
OUT.mkdir(parents=True,exist_ok=True)

cases=[
 ('swing-132',[(4,4,[1]*4,10,132)],dict(swing=True,sr=24000,seed=917)),
 ('compound-6-8-168',[(6,8,[3,3],10,168)],dict(sr=22050,seed=346)),
 ('compound-9-8-108',[(9,8,[3]*3,10,108)],dict(sr=44100,seed=61)),
 ('compound-12-8-192',[(12,8,[3]*4,10,192)],dict(sr=16000,seed=81)),
 ('odd-7-8-3-2-2',[(7,8,[3,2,2],10,144)],dict(sr=22050,seed=115)),
 ('changing-meter-and-tempo',[(4,4,[1]*4,6,108),(6,8,[3,3],6,144),(7,8,[2,3,2],6,144)],dict(sr=22050,seed=111)),
]
report=[]
for name,sections,kwargs in cases:
 signal,truth,expected_segments=arrangement(sections,**kwargs);sr=kwargs['sr'];duration=len(signal)/sr
 folder=OUT/name;folder.mkdir(exist_ok=True)
 sf.write(folder/'reference.wav',signal,sr,subtype='PCM_16')
 detection=detect(torch.tensor(signal[None,:],dtype=torch.float32),sr)
 timeline=Timeline({},detection,duration);grid=timeline.display_grid()
 beats=np.array(grid['beats']);beats=beats[(beats>=truth[0]-.05)&(beats<=truth[-1]+.05)]
 forward=np.min(abs(truth[:,None]-beats),axis=1) if len(beats) else np.array([999.])
 backward=np.min(abs(beats[:,None]-truth),axis=1) if len(beats) else np.array([999.])
 events=[(t,mido.Message(kind,note=60+i%12)) for i,t in enumerate(truth) for t,kind in [(float(t),'note_on'),(float(t+.07),'note_off')]]
 raw=performance(events);result=retime(raw,timeline);data=base64.b64decode(result['data']);(folder/'Auto.mid').write_bytes(data)
 before,after=events_in_seconds(raw),events_in_seconds(data)
 assert [e[1] for e in before]==[e[1] for e in after]
 error=max(abs(a[0]-b[0]) for a,b in zip(before,after));assert error<.001
 signatures=[];seconds=0
 for m in mido.MidiFile(file=io.BytesIO(data)):
  seconds+=m.time
  if m.type=='time_signature':signatures.append((seconds,m.numerator,m.denominator))
 meter_pass=all(any(abs(at-t)<.03 and (n,d)==(nn,dd) for t,nn,dd in signatures) for at,n,d in expected_segments)
 record=dict(case=name,pulse_pass=bool(np.percentile(forward,95)<=.05 and np.percentile(backward,95)<=.05),
     meter_events_pass=meter_pass,pulse_error_ms_p95=float(np.percentile(forward,95)*1000),
     extra_pulse_error_ms_p95=float(np.percentile(backward,95)*1000),note_error_ms=error*1000,
     detected_meter_segments=detection.meter_segments,summary=result['summary'])
 report.append(record);print(json.dumps(record),flush=True)
 (folder/'detection.json').write_text(json.dumps(vars(detection)))
(OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
if not all(r['pulse_pass'] and r['meter_events_pass'] for r in report):
 raise SystemExit('Some independent cases failed; see results.json')
